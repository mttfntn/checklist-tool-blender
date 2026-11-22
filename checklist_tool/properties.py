import bpy
from bpy.props import (BoolProperty, CollectionProperty, EnumProperty, IntProperty,
                       PointerProperty, StringProperty)
from bpy.types import AddonPreferences, PropertyGroup

from . import templates

ALL = "__ALL__"
UNCATEGORIZED = "__NONE__"


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
    """Distinct categories in first-appearance order, with (done, total) counts."""
    stats = {}
    for it in data.items:
        key = it.category.strip() or UNCATEGORIZED
        done, total = stats.get(key, (0, 0))
        stats[key] = (done + it.done, total + 1)
    return stats


# Dynamic enum strings must stay referenced while Blender uses them.
_category_enum_cache = []


def _category_items(self, context):
    _category_enum_cache.clear()
    _category_enum_cache.append((ALL, "All Categories", "Show every category", 'NONE', 0))
    for i, (key, (d, t)) in enumerate(categories(self).items(), start=1):
        label = "Uncategorized" if key == UNCATEGORIZED else key
        _category_enum_cache.append((key, f"{label}  ({d}/{t})", f"Show only {label}", 'NONE', i))
    return _category_enum_cache


def _category_get(self):
    current = self.filter_category_name or ALL
    for ident, *_rest, value in _category_items(self, None):
        if ident == current:
            return value
    return 0


def _category_set(self, value):
    for ident, *_rest, v in _category_items(self, None):
        if v == value:
            self.filter_category_name = "" if ident == ALL else ident
            return


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
