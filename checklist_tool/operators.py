"""Operators (``checklist.*``): edit tasks, clear filters, manage templates.

Operator docstrings would become tooltips, so the tooltip is ``bl_description``
and internal notes are # comments. Task operators work on the active scene's
checklist and support undo; template operators work on the JSON files
(templates.py) and are not undoable.
"""

import bpy
from bpy.props import EnumProperty, StringProperty
from bpy.types import Operator

from . import templates
from .properties import UNCATEGORIZED, get_prefs


def _data(context):
    """The active scene's CHECKLIST_Data."""
    return context.scene.checklist


# --------------------------------------------------------------------------- items

# Appends a task and selects it. It takes the category being filtered (so it
# stays visible), otherwise the selected task's category.
class CHECKLIST_OT_add(Operator):
    bl_idname = "checklist.add"
    bl_label = "Add Task"
    bl_description = "Add a task (in the filtered category, or the active task's category)"
    bl_options = {'REGISTER', 'UNDO'}

    def execute(self, context):
        data = _data(context)
        if data.filter_category_name == UNCATEGORIZED:
            category = ""
        elif data.filter_category_name:
            category = data.filter_category_name
        elif 0 <= data.active_index < len(data.items):
            category = data.items[data.active_index].category
        else:
            category = ""
        new = data.items.add()
        new.category = category
        data.search = ""  # make sure the new task is visible
        data.active_index = len(data.items) - 1
        return {'FINISHED'}


# Removes the selected task; the selection moves to the next one (or the last).
class CHECKLIST_OT_remove(Operator):
    bl_idname = "checklist.remove"
    bl_label = "Remove Task"
    bl_description = "Remove the active task"
    bl_options = {'REGISTER', 'UNDO'}

    @classmethod
    def poll(cls, context):
        d = _data(context)
        return 0 <= d.active_index < len(d.items)

    def execute(self, context):
        data = _data(context)
        data.items.remove(data.active_index)
        data.active_index = max(0, min(data.active_index, len(data.items) - 1))
        return {'FINISHED'}


# Resets the view filters (search, category, Hide Done); the sort is kept.
class CHECKLIST_OT_clear_filters(Operator):
    bl_idname = "checklist.clear_filters"
    bl_label = "Clear Filters"
    bl_description = "Show all tasks: clear search, category filter and Hide Done"

    def execute(self, context):
        data = _data(context)
        data.search = ""
        data.filter_category_name = ""
        data.hide_done = False
        return {'FINISHED'}


# --------------------------------------------------------------------------- templates

# Loads the template selected in the dropdown into the checklist. Replace asks
# for confirmation (invoke) when the checklist already has tasks.
class CHECKLIST_OT_apply_template(Operator):
    bl_idname = "checklist.apply_template"
    bl_label = "Apply Template"
    bl_description = "Fill the checklist from the selected template"
    bl_options = {'REGISTER', 'UNDO'}

    mode: EnumProperty(items=[
        ('REPLACE', "Replace", "Replace the current tasks"),
        ('APPEND', "Append", "Add the template's tasks to the current ones"),
    ], default='REPLACE')

    @classmethod
    def poll(cls, context):
        return context.window_manager.checklist_template not in {'', 'NONE'}

    def invoke(self, context, event):
        if self.mode == 'REPLACE' and len(_data(context).items):
            return context.window_manager.invoke_confirm(
                self, event, title="Replace Checklist?",
                message="Current tasks will be replaced by the template.", confirm_text="Replace")
        return self.execute(context)

    def execute(self, context):
        stem = context.window_manager.checklist_template
        try:
            data = templates.load(stem)
        except Exception as exc:
            self.report({'ERROR'}, f"Cannot load template: {exc}")
            return {'CANCELLED'}
        templates.apply(_data(context), data, replace=(self.mode == 'REPLACE'))
        self.report({'INFO'}, f"Applied template '{data['name']}' ({len(data['items'])} tasks)")
        return {'FINISHED'}


# Writes the current tasks (without done state) to <slug>.json, overwriting a
# template with the same slug, and selects it in the dropdown.
class CHECKLIST_OT_save_template(Operator):
    bl_idname = "checklist.save_template"
    bl_label = "Save as Template"
    bl_description = "Save the current tasks as a reusable template"

    name: StringProperty(name="Name")
    description: StringProperty(name="Description")

    @classmethod
    def poll(cls, context):
        return len(_data(context).items) > 0

    def invoke(self, context, event):
        if not self.name:
            self.name = _data(context).template_name or "My Template"
        return context.window_manager.invoke_props_dialog(self, confirm_text="Save")

    def execute(self, context):
        if not self.name.strip():
            self.report({'ERROR'}, "Template name is empty")
            return {'CANCELLED'}
        stem = templates.save(self.name, self.description, templates.items_from_checklist(_data(context)))
        context.window_manager.checklist_template = stem
        _data(context).template_name = self.name
        self.report({'INFO'}, f"Saved template '{self.name}'")
        return {'FINISHED'}


# Deletes the selected template file after a confirmation.
class CHECKLIST_OT_delete_template(Operator):
    bl_idname = "checklist.delete_template"
    bl_label = "Delete Template"
    bl_description = "Delete the selected template file"

    @classmethod
    def poll(cls, context):
        return context.window_manager.checklist_template not in {'', 'NONE'}

    def invoke(self, context, event):
        return context.window_manager.invoke_confirm(
            self, event, title="Delete Template?",
            message="The template file will be removed from disk.", confirm_text="Delete")

    def execute(self, context):
        templates.delete(context.window_manager.checklist_template)
        return {'FINISHED'}


# Stores the selected template as the one used for new files and marks the
# preferences as changed, so Auto-save Preferences keeps it.
class CHECKLIST_OT_set_default_template(Operator):
    bl_idname = "checklist.set_default_template"
    bl_label = "Set as Default"
    bl_description = "Use the selected template for every new file"

    @classmethod
    def poll(cls, context):
        return context.window_manager.checklist_template not in {'', 'NONE'}

    def execute(self, context):
        prefs = get_prefs(context)
        prefs.default_template = context.window_manager.checklist_template
        context.preferences.is_dirty = True
        self.report({'INFO'}, f"Default template: {prefs.default_template}")
        return {'FINISHED'}


# Opens the templates folder in the system file browser.
class CHECKLIST_OT_open_templates_folder(Operator):
    bl_idname = "checklist.open_templates_folder"
    bl_label = "Open Templates Folder"
    bl_description = "Open the folder holding the template JSON files"

    def execute(self, context):
        bpy.ops.wm.path_open(filepath=templates.templates_dir())
        return {'FINISHED'}


classes = (
    CHECKLIST_OT_add, CHECKLIST_OT_remove, CHECKLIST_OT_clear_filters, CHECKLIST_OT_apply_template,
    CHECKLIST_OT_save_template, CHECKLIST_OT_delete_template,
    CHECKLIST_OT_set_default_template, CHECKLIST_OT_open_templates_folder,
)


def register():
    for cls in classes:
        bpy.utils.register_class(cls)


def unregister():
    for cls in reversed(classes):
        bpy.utils.unregister_class(cls)
