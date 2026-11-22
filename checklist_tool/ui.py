"""Sidebar UI in the 3D Viewport (N > Checklist).

CHECKLIST_PT_main      progress, search bar, collapsible Filter section, task list
  CHECKLIST_PT_task    fields of the selected task (sub-panel)
  CHECKLIST_PT_templates  template dropdown and template operators (sub-panel)
CHECKLIST_UL_items     the task list; filter_items applies search / category /
                       hide done (task_visible) and the sort order (_sort_key).

Draw code only reads data. Panel and list classes use # comments, because
their docstrings would become tooltips.
"""

import bpy
from bpy.types import Panel, UIList

from .properties import UNCATEGORIZED, get_prefs


def task_visible(data, it):
    """True if task `it` passes the search, category and Hide Done filters.

    Used by the list and by the "Showing N of M tasks" counter, so both agree.
    """
    if data.hide_done and it.done:
        return False
    cat = data.filter_category_name
    if cat:
        if cat == UNCATEGORIZED:
            if it.category.strip():
                return False
        elif it.category.strip() != cat:
            return False
    needle = data.search.strip().lower()
    if needle and not any(needle in s.lower() for s in (it.name, it.category, it.note)):
        return False
    return True


def _sort_key(mode, items):
    """Key function (index, task) -> sortable value for the sort mode.

    Sorting only changes the display order (UIList), never the stored order.
    """
    if mode == 'TODO_FIRST':
        return lambda i, it: (it.done, i)
    if mode == 'NAME':
        return lambda i, it: (it.name.lower(), i)
    # CATEGORY: categories in first-appearance order, uncategorized last,
    # stored order kept inside each category. Grouping ignores letter case
    # ("setup" joins "Setup"); the category filter does not.
    first = {}
    for i, it in enumerate(items):
        first.setdefault(it.category.strip().lower(), i)
    return lambda i, it: (not it.category.strip(), first[it.category.strip().lower()], i)


def filters_active(data):
    """True if any filter hides tasks (search, category or Hide Done)."""
    return bool(data.search.strip() or data.filter_category_name or data.hide_done)


# Task list. Built-in name filtering is replaced by the panel's own search bar.
class CHECKLIST_UL_items(UIList):
    bl_idname = "CHECKLIST_UL_items"

    def draw_item(self, context, layout, data, item, icon, active_data, active_propname, index):
        row = layout.row(align=True)
        row.prop(item, "done", text="")
        name = row.row()
        name.active = not item.done
        name.prop(item, "name", text="", emboss=False)
        if item.note:
            row.label(text="", icon='TEXT')
        if item.category and not data.filter_category_name:
            cat = row.row()
            cat.active = False
            cat.alignment = 'RIGHT'
            cat.label(text=item.category)

    def draw_filter(self, context, layout):
        layout.label(text="Use Search and Filter above the list", icon='INFO')

    def filter_items(self, context, data, propname):
        items = getattr(data, propname)
        flag = self.bitflag_filter_item
        flags = [flag if task_visible(data, it) else 0 for it in items]

        key = _sort_key(data.sort_mode, items)
        ranked = sorted(range(len(items)), key=lambda i: key(i, items[i]))
        order = [0] * len(items)
        for pos, i in enumerate(ranked):
            order[i] = pos
        return flags, order


# Main panel; header shows done/total.
class CHECKLIST_PT_main(Panel):
    bl_label = "Checklist"
    bl_idname = "CHECKLIST_PT_main"
    bl_space_type = 'VIEW_3D'
    bl_region_type = 'UI'
    bl_category = "Checklist"

    def draw_header_preset(self, context):
        data = context.scene.checklist
        done = sum(it.done for it in data.items)
        self.layout.label(text=f"{done}/{len(data.items)}")

    def draw(self, context):
        layout = self.layout
        data = context.scene.checklist
        total = len(data.items)
        done = sum(it.done for it in data.items)

        if data.template_name:
            layout.label(text=data.template_name, icon='PRESET')

        if total:
            text = "All done" if done == total else f"{done} / {total} done"
            if hasattr(layout, "progress"):
                layout.progress(factor=done / total, type='BAR', text=text)
            else:
                layout.label(text=text)

        # Search bar
        try:
            layout.prop(data, "search", text="", icon='VIEWZOOM', placeholder="Search tasks")
        except TypeError:  # 'placeholder' needs a newer Blender
            layout.prop(data, "search", text="", icon='VIEWZOOM')

        # Filter section (collapsible)
        header, body = layout.panel("CHECKLIST_filter", default_closed=False)
        row = header.row()
        row.label(text="Filter", icon='FILTER')
        if filters_active(data):
            hint = []
            if data.filter_category_name:
                hint.append("Uncategorized" if data.filter_category_name == UNCATEGORIZED
                            else data.filter_category_name)
            if data.hide_done:
                hint.append("hiding done")
            if hint:
                sub = row.row()
                sub.active = False
                sub.alignment = 'RIGHT'
                sub.label(text=", ".join(hint))
        if body:
            col = body.column()
            col.use_property_split = True
            col.use_property_decorate = False
            col.prop(data, "filter_category")
            col.prop(data, "sort_mode")
            col.prop(data, "hide_done")
            if filters_active(data):
                body.operator("checklist.clear_filters", icon='X')

        # List
        row = layout.row()
        row.template_list("CHECKLIST_UL_items", "", data, "items", data, "active_index",
                          rows=6 if total > 4 else 4)
        col = row.column(align=True)
        col.operator("checklist.add", icon='ADD', text="")
        col.operator("checklist.remove", icon='REMOVE', text="")

        if not total:
            box = layout.box()
            box.label(text="Empty checklist", icon='INFO')
            box.label(text="Apply a template below or add tasks.")
        elif filters_active(data):
            shown = sum(task_visible(data, it) for it in data.items)
            sub = layout.row()
            sub.active = False
            sub.label(text=f"Showing {shown} of {total} tasks")


# Selected task's fields (shown when a task is selected).
class CHECKLIST_PT_task(Panel):
    bl_label = "Task"
    bl_idname = "CHECKLIST_PT_task"
    bl_space_type = 'VIEW_3D'
    bl_region_type = 'UI'
    bl_category = "Checklist"
    bl_parent_id = "CHECKLIST_PT_main"

    @classmethod
    def poll(cls, context):
        d = context.scene.checklist
        return 0 <= d.active_index < len(d.items)

    def draw(self, context):
        layout = self.layout
        layout.use_property_split = True
        layout.use_property_decorate = False
        d = context.scene.checklist
        item = d.items[d.active_index]
        layout.prop(item, "name")
        layout.prop(item, "category")
        layout.prop(item, "note")


# Template dropdown, Replace / Append, Save / Delete, default for new files.
class CHECKLIST_PT_templates(Panel):
    bl_label = "Templates"
    bl_idname = "CHECKLIST_PT_templates"
    bl_space_type = 'VIEW_3D'
    bl_region_type = 'UI'
    bl_category = "Checklist"
    bl_parent_id = "CHECKLIST_PT_main"

    def draw(self, context):
        layout = self.layout
        wm = context.window_manager
        prefs = get_prefs(context)

        layout.prop(wm, "checklist_template", text="")
        row = layout.row(align=True)
        row.operator("checklist.apply_template", text="Replace", icon='IMPORT').mode = 'REPLACE'
        row.operator("checklist.apply_template", text="Append", icon='ADD').mode = 'APPEND'

        row = layout.row(align=True)
        row.operator("checklist.save_template", text="Save Current", icon='FILE_TICK')
        row.operator("checklist.delete_template", text="", icon='TRASH')

        layout.separator()
        if prefs:
            col = layout.column(align=True)
            is_default = prefs.default_template == wm.checklist_template
            col.operator("checklist.set_default_template",
                         icon='SOLO_ON' if is_default else 'SOLO_OFF',
                         text="Default for New Files" if is_default else "Set as Default")
            col.prop(prefs, "auto_apply", text="Auto-apply on New File")


classes = (CHECKLIST_UL_items, CHECKLIST_PT_main, CHECKLIST_PT_task, CHECKLIST_PT_templates)


def register():
    for cls in classes:
        bpy.utils.register_class(cls)


def unregister():
    for cls in reversed(classes):
        bpy.utils.unregister_class(cls)
