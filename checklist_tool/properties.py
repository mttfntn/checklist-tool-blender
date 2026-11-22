"""Data model: the checklist stored in each scene, and the add-on preferences.

``Scene.checklist`` (CHECKLIST_Data) is saved inside the .blend file: the
tasks plus the view state (search, category filter, sort, hide done).
``WindowManager.checklist_template`` is the Templates dropdown selection; it is
UI state only and is not saved in files.

The category filter is stored as a plain string (``filter_category_name``) and
exposed to the UI as a dynamic enum (``filter_category``) through get/set
functions, so it keeps working while categories are added or removed.
"""

import bpy
from bpy.props import (BoolProperty, CollectionProperty, EnumProperty, IntProperty,
                       PointerProperty, StringProperty)
from bpy.types import AddonPreferences, PropertyGroup

from . import templates

# Special filter_category values: "every category" and "tasks with no category".
ALL = "__ALL__"
UNCATEGORIZED = "__NONE__"


# One task. Classes registered with Blender use # comments: their docstrings
# would become the type's description shown in Blender.
class CHECKLIST_Item(PropertyGroup):
    name: StringProperty(name="Task", default="New task")
    done: BoolProperty(name="Done", default=False)
    category: StringProperty(name="Category", description="Group label, e.g. Modeling, Shading, Output")
    note: StringProperty(name="Note")


SORT_ITEMS = [
    ('CATEGORY', "Category", "Group tasks by category, in the order categories first appear", 'OUTLINER_COLLECTION', 2),
    ('TODO_FIRST', "To Do First", "Unchecked tasks on top, checked at the bottom", 'CHECKBOX_DEHLT', 1),
    ('NAME', "Name", "Alphabetical", 'SORTALPHA', 3),
]


def categories(data):
    """Distinct categories in first-appearance order, with (done, total) counts.

    Categories are compared after stripping spaces (case-sensitive); tasks with
    no category are grouped under UNCATEGORIZED.
    """
    stats = {}
    for it in data.items:
        key = it.category.strip() or UNCATEGORIZED
        done, total = stats.get(key, (0, 0))
        stats[key] = (done + it.done, total + 1)
    return stats


def _category_keys(data):
    """Enum identifiers of the category filter; the index is the enum value."""
    return [ALL, *categories(data)]


# Dynamic enum: Blender keeps raw pointers to these strings, so Python must keep
# them referenced. Blender calls the items callback itself whenever the value is
# read or set, so get/set only need the identifiers (_category_keys) and do not
# rebuild this list a second time.
_category_enum_cache = []


def _category_items(self, context):
    """Items callback of filter_category: "All" plus each category with done/total."""
    _category_enum_cache.clear()
    _category_enum_cache.append((ALL, "All Categories", "Show every category", 'NONE', 0))
    for i, (key, (d, t)) in enumerate(categories(self).items(), start=1):
        label = "Uncategorized" if key == UNCATEGORIZED else key
        _category_enum_cache.append((key, f"{label}  ({d}/{t})", f"Show only {label}", 'NONE', i))
    return _category_enum_cache


def _category_get(self):
    """Enum value for filter_category_name; a vanished category reads as All (0)."""
    keys = _category_keys(self)
    current = self.filter_category_name or ALL
    return keys.index(current) if current in keys else 0


def _category_set(self, value):
    """Store the chosen category's identifier ("" for All)."""
    keys = _category_keys(self)
    if 0 <= value < len(keys):
        self.filter_category_name = "" if keys[value] == ALL else keys[value]


# The checklist of one scene: tasks plus view state.
class CHECKLIST_Data(PropertyGroup):
    items: CollectionProperty(type=CHECKLIST_Item)
    active_index: IntProperty(name="Active Task", default=0)
    template_name: StringProperty(name="Template", description="Template this checklist was created from")

    search: StringProperty(name="Search", description="Show only tasks whose name, category or note contains this text",
                           options={'TEXTEDIT_UPDATE'})
    hide_done: BoolProperty(name="Hide Done", description="Hide tasks that are already checked", default=False)
    sort_mode: EnumProperty(name="Sort", description="How tasks are ordered in the list",
                            items=SORT_ITEMS, default='CATEGORY')
    # Stored as a string so the filter survives categories being added/removed.
    filter_category_name: StringProperty()
    filter_category: EnumProperty(name="Category", description="Show only one category",
                                  items=_category_items, get=_category_get, set=_category_set)


# Add-on preferences (shared by all files): new-file template behaviour.
class CHECKLIST_Preferences(AddonPreferences):
    bl_idname = __package__

    auto_apply: BoolProperty(
        name="Apply Default Template to New Files",
        description="When a new file is created (File > New / startup), fill its checklist from the default template",
        default=True,
    )
    default_template: StringProperty(
        name="Default Template",
        description="Template file name (without .json) used for new files",
        default="general_project",
    )

    def draw(self, context):
        layout = self.layout
        layout.prop(self, "auto_apply")
        layout.prop(self, "default_template")
        row = layout.row()
        row.label(text=templates.templates_dir(), icon='FILE_FOLDER')
        row.operator("checklist.open_templates_folder", text="", icon='FILEBROWSER')


def get_prefs(context=None):
    """The add-on's preferences, or None while it is not enabled in Preferences."""
    context = context or bpy.context
    addon = context.preferences.addons.get(__package__)
    return addon.preferences if addon else None


classes = (CHECKLIST_Item, CHECKLIST_Data, CHECKLIST_Preferences)


def register():
    for cls in classes:
        bpy.utils.register_class(cls)
    bpy.types.Scene.checklist = PointerProperty(type=CHECKLIST_Data)
    bpy.types.WindowManager.checklist_template = EnumProperty(
        name="Template",
        description="Checklist template",
        items=templates.enum_items,
    )


def unregister():
    del bpy.types.WindowManager.checklist_template
    del bpy.types.Scene.checklist
    for cls in reversed(classes):
        bpy.utils.unregister_class(cls)
