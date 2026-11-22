"""Checklist Tool: per-file manual checklists with reusable JSON templates."""

import bpy
from bpy.app.handlers import persistent

from . import operators, properties, templates, ui  # noqa: F401
from .properties import get_prefs


@persistent
def _on_load_post(*_args):
    """New file (File > New or startup): fill the checklist from the default template."""
    prefs = get_prefs()
    if not prefs or not prefs.auto_apply or bpy.data.filepath:
        return
    scene = bpy.context.scene or (bpy.data.scenes[0] if bpy.data.scenes else None)
    if scene is None or len(scene.checklist.items):
        return
    try:
        data = templates.load(prefs.default_template)
    except Exception:
        return
    templates.apply(scene.checklist, data, replace=True)


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
    lst = bpy.app.handlers.load_post
    for h in [h for h in lst if getattr(h, "__name__", "") == _on_load_post.__name__]:
        lst.remove(h)
    for m in reversed(modules):
        m.unregister()
