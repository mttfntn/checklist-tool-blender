"""Checklist Tool: per-file manual checklists with reusable JSON templates.

Modules:
    properties  data stored in each scene (tasks + view state) and preferences
    templates   template JSON files: list, load, save, delete, apply
    operators   checklist.* operators (tasks, filters, templates)
    ui          the 3D Viewport sidebar panels (N > Checklist) and task list

This file registers them and adds one load_post handler that fills the
checklist of a brand-new file from the default template.
"""

import bpy
from bpy.app.handlers import persistent

from . import operators, properties, templates, ui
from .properties import get_prefs


@persistent
def _on_load_post(*_args):
    """Fill a new, never-saved file's empty checklist from the default template.

    Runs after every file load (File > New, startup, Open). Saved files, files
    that already have tasks, auto_apply off, or a missing default template:
    nothing happens.
    """
    prefs = get_prefs()
    if not prefs or not prefs.auto_apply or bpy.data.filepath:
        return
    scene = bpy.context.scene or (bpy.data.scenes[0] if bpy.data.scenes else None)
    if scene is None or len(scene.checklist.items):
        return
    try:
        data = templates.load(prefs.default_template)
    except Exception:  # default template deleted or invalid: leave the file alone
        return
    templates.apply(scene.checklist, data, replace=True)


# Registration order: properties first (operators and panels use them).
modules = (properties, operators, ui)


def register():
    for m in modules:
        m.register()
    try:
        templates.ensure_defaults()
    except Exception as exc:
        print(f"[Checklist Tool] could not seed templates: {exc}")
    bpy.app.handlers.load_post.append(_on_load_post)


def unregister():
    # Remove by name, so a handler left by an older copy of the module goes too.
    lst = bpy.app.handlers.load_post
    for h in [h for h in lst if getattr(h, "__name__", "") == _on_load_post.__name__]:
        lst.remove(h)
    for m in reversed(modules):
        m.unregister()
