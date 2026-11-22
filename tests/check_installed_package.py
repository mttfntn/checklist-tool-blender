"""Check the built extension after installing it into a SCRATCH profile.

With BLENDER_USER_* pointing at a scratch profile:
    blender -b --factory-startup --command extension install-file --repo user_default --enable dist/checklist_tool-X.Y.Z.zip
    blender -b --python-exit-code 1 --python tests/check_installed_package.py
(no --factory-startup on the second call: it must load the scratch preferences
that the install just saved). Exits 1 if the installed extension is missing,
disabled or broken.
"""
import os
import sys
import tomllib

import bpy

MOD = "bl_ext.user_default.checklist_tool"
problems = []
addon = bpy.context.preferences.addons.get(MOD)
if addon is None:
    problems.append("extension not enabled: " + MOD)
else:
    ct = sys.modules[MOD]
    pkg_dir = os.path.dirname(ct.__file__)
    for name in ("auto_apply", "default_template"):
        if name not in addon.preferences.bl_rna.properties:
            problems.append("missing preference " + name)
    for cls in ("CHECKLIST_PT_main", "CHECKLIST_PT_task", "CHECKLIST_PT_templates", "CHECKLIST_UL_items",
                "CHECKLIST_OT_add", "CHECKLIST_OT_apply_template"):
        if not hasattr(bpy.types, cls):
            problems.append("class not registered: " + cls)
    if not hasattr(bpy.types.Scene, "checklist"):
        problems.append("Scene.checklist missing")
    if not any(getattr(h, "__name__", "") == "_on_load_post" for h in bpy.app.handlers.load_post):
        problems.append("load_post handler missing")
    stems = [s for s, _, _ in ct.templates.list_templates()]
    if stems != ["animation", "game_asset", "general_project", "lookdev_render"]:
        problems.append(f"default templates not seeded: {stems}")
    # One real use: apply the default template to the scene.
    data = ct.templates.load(addon.preferences.default_template)
    ct.templates.apply(bpy.context.scene.checklist, data)
    if len(bpy.context.scene.checklist.items) != 11:
        problems.append("applying the default template failed")
    if not os.path.isfile(os.path.join(pkg_dir, "LICENSE")):
        problems.append("LICENSE missing from installed package")
    with open(os.path.join(pkg_dir, "blender_manifest.toml"), "rb") as f:
        manifest = tomllib.load(f)
    print("installed at", pkg_dir, "version", manifest["version"])

print("PROBLEMS:", problems or "none")
sys.stdout.flush()
os._exit(1 if problems else 0)
