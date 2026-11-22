"""Headless test suite for the Checklist Tool.

Run from the repo root (never inside your open Blender session):
    python3 tests/run_blender.py
run_blender.py starts Blender with --factory-startup and a throwaway profile
that already contains the add-on as an extension. Prints "N checks, M failed"
and exits 1 on any failure.

Panels are drawn into a recording fake layout, so the UI code runs without a
window; every prop / operator name it uses is checked against the real API.
"""

import importlib
import json
import os
import sys
import traceback
import types

import addon_utils
import bpy

MOD = os.environ.get("CT_MODULE", "bl_ext.user_default.checklist_tool")
RESULTS = []


def check(name, cond, detail=""):
    RESULTS.append((name, bool(cond), detail))
    print(("PASS " if cond else "FAIL ") + name + (("  -- " + str(detail)) if (detail and not cond) else ""))


# ----------------------------------------------------------------- helpers

class FakeLayout:
    """Accepts every UILayout call; records labels, props and operators and
    validates their names against Blender's RNA."""

    def __init__(self, log):
        self.__dict__["log"] = log

    def __getattr__(self, name):
        log = self.log

        def call(*args, **kw):
            if name == "prop":
                data, prop = args[0], args[1]
                if prop not in data.bl_rna.properties:
                    log.append(("BAD-prop", prop))
                log.append(("prop", prop))
            elif name == "operator":
                mod, op = args[0].split(".")
                try:
                    getattr(getattr(bpy.ops, mod), op).get_rna_type()
                except Exception:
                    log.append(("BAD-op", args[0]))
                log.append(("op", args[0], kw.get("text", "")))
                return types.SimpleNamespace()
            elif name == "label":
                log.append(("label", kw.get("text", args[0] if args else "")))
            elif name == "progress":
                log.append(("progress", kw.get("text", "")))
            elif name == "template_list":
                log.append(("list", args[0]))
            elif name == "panel":
                if "panel" not in bpy.types.UILayout.bl_rna.functions:
                    log.append(("BAD-panel",))
                return FakeLayout(log), FakeLayout(log)
            return FakeLayout(log)
        return call

    def __setattr__(self, name, value):
        pass


def draw(cls, context=None):
    log = []
    cls.draw(types.SimpleNamespace(layout=FakeLayout(log)), context or bpy.context)
    return log


def bad(log):
    return [e for e in log if e[0].startswith("BAD")]


def visible_names(ui, data):
    """What the UIList would show, in display order."""
    fake = types.SimpleNamespace(bitflag_filter_item=1 << 30, filter_name="", use_filter_invert=False)
    flags, order = ui.CHECKLIST_UL_items.filter_items(fake, bpy.context, data, "items")
    idx = list(range(len(data.items)))
    if order:
        idx.sort(key=lambda i: order[i])
    return [data.items[i].name for i in idx if flags[i]]


def fill(data, rows):
    """rows: (name, category, done[, note])"""
    data.items.clear()
    for r in rows:
        it = data.items.add()
        it.name, it.category, it.done = r[0], r[1], r[2]
        if len(r) > 3:
            it.note = r[3]
    data.active_index = 0


def reset_view(data):
    data.search = ""
    data.filter_category_name = ""
    data.hide_done = False
    data.sort_mode = 'CATEGORY'


# ----------------------------------------------------------------- tests

def test_registration(ct):
    check("module loaded as " + MOD, ct.__name__ == MOD)
    check("addon in preferences", MOD in bpy.context.preferences.addons)
    data_type = bpy.types.Scene.bl_rna.properties["checklist"].fixed_type
    check("Scene.checklist is CHECKLIST_Data", data_type.identifier == "CHECKLIST_Data", data_type.identifier)
    item_type = data_type.properties["items"].fixed_type
    check("items are CHECKLIST_Item", item_type.identifier == "CHECKLIST_Item", item_type.identifier)
    for cls in ("CHECKLIST_UL_items", "CHECKLIST_PT_main",
                "CHECKLIST_PT_task", "CHECKLIST_PT_templates", "CHECKLIST_OT_add", "CHECKLIST_OT_remove",
                "CHECKLIST_OT_clear_filters", "CHECKLIST_OT_apply_template", "CHECKLIST_OT_save_template",
                "CHECKLIST_OT_delete_template", "CHECKLIST_OT_set_default_template",
                "CHECKLIST_OT_open_templates_folder"):
        check("registered " + cls, hasattr(bpy.types, cls))
    check("Scene.checklist", hasattr(bpy.types.Scene, "checklist"))
    check("WindowManager.checklist_template", hasattr(bpy.types.WindowManager, "checklist_template"))
    n = sum(1 for h in bpy.app.handlers.load_post if getattr(h, "__name__", "") == "_on_load_post")
    check("one load_post handler", n == 1, n)
    for prop in ("search", "hide_done", "sort_mode", "filter_category", "filter_category_name", "template_name"):
        check("data prop " + prop, prop in data_type.properties)
    for prop in ("name", "done", "category", "note"):
        check("item prop " + prop, prop in item_type.properties)
    sorts = [e.identifier for e in data_type.properties["sort_mode"].enum_items]
    check("sort modes", sorts == ['CATEGORY', 'TODO_FIRST', 'NAME'], sorts)


def test_reenable():
    for cycle in range(3):
        addon_utils.disable(MOD, default_set=True)
        check(f"disable {cycle}: Scene.checklist removed", not hasattr(bpy.types.Scene, "checklist"))
        check(f"disable {cycle}: handler removed",
              not any(getattr(h, "__name__", "") == "_on_load_post" for h in bpy.app.handlers.load_post))
        addon_utils.enable(MOD, default_set=True)
        n = sum(1 for h in bpy.app.handlers.load_post if getattr(h, "__name__", "") == "_on_load_post")
        check(f"enable {cycle}: single handler", n == 1, n)
    return importlib.import_module(MOD)


def test_templates_module(ct):
    T = importlib.import_module(MOD + ".templates")
    folder = T.templates_dir()
    check("templates dir inside scratch profile", folder.startswith(os.environ["CT_PROFILE"]), folder)
    want = "checklist_tool_templates" if MOD == "checklist_tool" else os.path.join("checklist_tool", "templates")
    check("templates dir for this load mode", folder.rstrip(os.sep).endswith(want), folder)
    stems = [s for s, _, _ in T.list_templates()]
    check("defaults seeded", stems == ["animation", "game_asset", "general_project", "lookdev_render"], stems)
    check("seed marker written", os.path.exists(os.path.join(folder, T.SEED_MARKER)))
    names = [n for _, n, _ in T.list_templates()]
    check("sorted by display name", names == sorted(names, key=str.lower), names)

    # A deleted default does not come back on the next seeding.
    T.delete("animation")
    T.ensure_defaults()
    check("deleted default stays deleted", "animation" not in [s for s, _, _ in T.list_templates()])
    os.remove(os.path.join(folder, T.SEED_MARKER))
    T.ensure_defaults()
    check("without marker, missing defaults are copied back",
          "animation" in [s for s, _, _ in T.list_templates()])

    for raw, want in (("My Template", "my_template"), ("  Lookdev & Render ", "lookdev_render"),
                      ("a/b\\c", "a_b_c"), ("***", "template"), ("Pre-Viz 2", "pre-viz_2")):
        check(f"slugify {raw!r}", T.slugify(raw) == want, T.slugify(raw))

    stem = T.save("Round Trip", "desc", [{"name": "A", "category": "X", "note": "n"}, {"name": "B"}])
    data = T.load(stem)
    check("save/load roundtrip", data == {"name": "Round Trip", "description": "desc", "items": [
        {"name": "A", "category": "X", "note": "n"}, {"name": "B", "category": "", "note": ""}]}, data)

    with open(os.path.join(folder, "legacy.json"), "w") as f:
        json.dump({"name": "Legacy", "items": [{"name": "Old", "section": "Sec", "auto_check": "UV_MAPS"}, "Plain"]}, f)
    data = T.load("legacy")
    check("legacy 'section' key accepted", data["items"][0]["category"] == "Sec", data)
    check("unknown keys dropped", "auto_check" not in data["items"][0], data)
    check("string items accepted", data["items"][1] == {"name": "Plain", "category": "", "note": ""}, data)

    with open(os.path.join(folder, "broken.json"), "w") as f:
        f.write("{ not json")
    with open(os.path.join(folder, "notes.txt"), "w") as f:
        f.write("ignored")
    stems = [s for s, _, _ in T.list_templates()]
    check("broken JSON skipped", "broken" not in stems, stems)
    check("non-JSON files ignored", "notes" not in stems, stems)
    os.remove(os.path.join(folder, "broken.json"))
    os.remove(os.path.join(folder, "notes.txt"))

    items = T.enum_items(None, bpy.context)
    check("enum lists every template", [i[0] for i in items] == [s for s, _, _ in T.list_templates()], items)
    check("enum values are unique ints", sorted(i[3] for i in items) == list(range(len(items))))

    # The template index is cached by mtime/size: edits from outside Blender must still show.
    path = os.path.join(folder, "legacy.json")
    with open(path, "w") as f:
        json.dump({"name": "Legacy Renamed and longer", "items": []}, f)
    names = {s: n for s, n, _ in T.list_templates()}
    check("external rename picked up", names.get("legacy") == "Legacy Renamed and longer", names)
    st = os.stat(path)
    with open(path, "w") as f:  # same size, newer mtime
        json.dump({"name": "Legacy Renamed and LONGER", "items": []}, f)
    os.utime(path, ns=(st.st_atime_ns, st.st_mtime_ns + 5_000_000))
    names = {s: n for s, n, _ in T.list_templates()}
    check("same-size edit picked up (mtime)", names.get("legacy") == "Legacy Renamed and LONGER", names)
    with open(os.path.join(folder, "later.json"), "w") as f:
        f.write("{ broken")
    check("broken new file skipped", "later" not in [s for s, _, _ in T.list_templates()])
    with open(os.path.join(folder, "later.json"), "w") as f:
        json.dump({"name": "Later fixed", "items": ["x"]}, f)
    check("fixed file picked up", "later" in [s for s, _, _ in T.list_templates()])
    os.remove(os.path.join(folder, "later.json"))
    check("removed file disappears", "later" not in [s for s, _, _ in T.list_templates()])
    os.makedirs(os.path.join(folder, "folder.json"))
    check("folder named *.json skipped", "folder" not in [s for s, _, _ in T.list_templates()])
    os.rmdir(os.path.join(folder, "folder.json"))

    T.delete("legacy")
    T.delete("round_trip")
    T.delete("does_not_exist")  # must not raise
    check("delete missing template is harmless", True)


def test_empty_templates_enum(ct):
    T = importlib.import_module(MOD + ".templates")
    folder = T.templates_dir()
    backup = folder + "_bak"
    os.rename(folder, backup)
    os.makedirs(folder)
    try:
        items = T.enum_items(None, bpy.context)
        check("no templates -> NONE placeholder", [i[0] for i in items] == ['NONE'], items)
        bpy.context.window_manager.checklist_template = 'NONE'
        check("apply poll false without templates", not bpy.ops.checklist.apply_template.poll())
        check("delete poll false without templates", not bpy.ops.checklist.delete_template.poll())
        check("set default poll false without templates", not bpy.ops.checklist.set_default_template.poll())
    finally:
        os.rmdir(folder)
        os.rename(backup, folder)


def test_operators(ct):
    wm = bpy.context.window_manager
    d = bpy.context.scene.checklist
    d.items.clear()
    reset_view(d)

    wm.checklist_template = "general_project"
    r = bpy.ops.checklist.apply_template('EXEC_DEFAULT', mode='REPLACE')
    check("apply replace finished", r == {'FINISHED'}, r)
    check("apply replace count", len(d.items) == 11, len(d.items))
    check("template name set", d.template_name == "General Project", d.template_name)
    check("first task", (d.items[0].name, d.items[0].category) == ("Save file with a project name", "Setup"))
    check("active reset to 0", d.active_index == 0)

    d.active_index = 5
    wm.checklist_template = "game_asset"
    bpy.ops.checklist.apply_template('EXEC_DEFAULT', mode='APPEND')
    check("append adds", len(d.items) == 23, len(d.items))
    check("append keeps active", d.active_index == 5, d.active_index)
    check("append renames template", d.template_name == "Game Asset", d.template_name)

    # add: category from the filter, then from the active task, else empty
    d.filter_category_name = "Output"
    d.search = "zzz"
    bpy.ops.checklist.add('EXEC_DEFAULT')
    check("add uses filtered category", d.items[d.active_index].category == "Output")
    check("add clears search", d.search == "")
    check("add selects new task", d.active_index == len(d.items) - 1)
    check("new task defaults", (d.items[-1].name, d.items[-1].done, d.items[-1].note) == ("New task", False, ""))
    d.filter_category_name = ""
    d.active_index = 0
    bpy.ops.checklist.add('EXEC_DEFAULT')
    check("add uses active task category", d.items[-1].category == "Setup", d.items[-1].category)
    d.filter_category_name = ct.properties.UNCATEGORIZED
    bpy.ops.checklist.add('EXEC_DEFAULT')
    check("add in Uncategorized filter -> empty category", d.items[-1].category == "")
    d.filter_category_name = ""

    n = len(d.items)
    d.active_index = n - 1
    bpy.ops.checklist.remove('EXEC_DEFAULT')
    check("remove last", len(d.items) == n - 1)
    check("remove clamps active", d.active_index == n - 2, d.active_index)
    d.active_index = 0
    first = d.items[1].name
    bpy.ops.checklist.remove('EXEC_DEFAULT')
    check("remove first keeps index 0", d.active_index == 0 and d.items[0].name == first)
    d.active_index = 999
    check("remove poll false for bad index", not bpy.ops.checklist.remove.poll())
    d.active_index = 0

    d.search, d.filter_category_name, d.hide_done = "x", "Setup", True
    bpy.ops.checklist.clear_filters('EXEC_DEFAULT')
    check("clear filters", (d.search, d.filter_category_name, d.hide_done) == ("", "", False))

    # save / delete / default
    T = ct.templates
    check("save poll with tasks", bpy.ops.checklist.save_template.poll())
    try:  # in background mode an ERROR report is raised as RuntimeError
        r = bpy.ops.checklist.save_template('EXEC_DEFAULT', name="   ")
    except RuntimeError as exc:
        r = str(exc)
    check("save with blank name refused", "Template name is empty" in str(r), r)
    check("blank name wrote no file", "" not in [s for s, _, _ in T.list_templates()])
    r = bpy.ops.checklist.save_template('EXEC_DEFAULT', name="Studio Pipeline", description="mine")
    check("save finished", r == {'FINISHED'})
    check("saved file exists", "studio_pipeline" in [s for s, _, _ in T.list_templates()])
    check("saved template selected", wm.checklist_template == "studio_pipeline", wm.checklist_template)
    check("checklist renamed after save", d.template_name == "Studio Pipeline")
    saved = T.load("studio_pipeline")
    check("saved items match", [i["name"] for i in saved["items"]] == [i.name for i in d.items])

    r = bpy.ops.checklist.set_default_template('EXEC_DEFAULT')
    check("set default finished", r == {'FINISHED'}, r)
    check("default pref updated", ct.properties.get_prefs().default_template == "studio_pipeline")

    bpy.ops.checklist.delete_template('EXEC_DEFAULT')
    check("delete removes file", "studio_pipeline" not in [s for s, _, _ in T.list_templates()])
    ct.properties.get_prefs().default_template = "general_project"

    d.items.clear()
    check("save poll false when empty", not bpy.ops.checklist.save_template.poll())
    check("remove poll false when empty", not bpy.ops.checklist.remove.poll())
    bpy.ops.checklist.add('EXEC_DEFAULT')
    check("add into empty list", len(d.items) == 1 and d.items[0].category == "" and d.active_index == 0)

    wm.checklist_template = "general_project"
    check("open folder op registered", bpy.ops.checklist.open_templates_folder.poll())


ROWS = [
    ("Save file", "Setup", True, ""),
    ("Units", "Setup", False, ""),
    ("Collections", "Scene", True, ""),
    ("Rename objects", "Scene", False, "use the naming guide"),
    ("Loose task", "", False, ""),
    ("Apply scale", "Scene", False, ""),
    ("Camera", "Output", False, ""),
    ("Another loose", "  ", True, ""),
    ("Bake", "setup", False, ""),
]


def test_filters(ct):
    ui = ct.ui
    d = bpy.context.scene.checklist
    fill(d, ROWS)
    reset_view(d)
    check("sort CATEGORY (groups case-insensitively)", visible_names(ui, d) == [
        "Save file", "Units", "Bake", "Collections", "Rename objects", "Apply scale", "Camera",
        "Loose task", "Another loose"], visible_names(ui, d))
    d.sort_mode = 'TODO_FIRST'
    check("sort TODO_FIRST", visible_names(ui, d) == [
        "Units", "Rename objects", "Loose task", "Apply scale", "Camera", "Bake",
        "Save file", "Collections", "Another loose"], visible_names(ui, d))
    d.sort_mode = 'NAME'
    check("sort NAME", visible_names(ui, d) == sorted([r[0] for r in ROWS], key=str.lower), visible_names(ui, d))

    d.sort_mode = 'CATEGORY'
    d.hide_done = True
    check("hide done", visible_names(ui, d) == [
        "Units", "Bake", "Rename objects", "Apply scale", "Camera", "Loose task"], visible_names(ui, d))
    d.hide_done = False

    d.filter_category = "Scene"
    check("category enum set stores name", d.filter_category_name == "Scene")
    check("category filter", visible_names(ui, d) == ["Collections", "Rename objects", "Apply scale"])
    d.filter_category_name = ct.properties.UNCATEGORIZED
    check("uncategorized filter (blank and spaces)", visible_names(ui, d) == ["Loose task", "Another loose"])
    d.filter_category_name = "Gone"
    check("stale category name hides all", visible_names(ui, d) == [])
    check("stale category reads as All", d.filter_category == ct.properties.ALL)
    d.filter_category = ct.properties.ALL
    check("All clears name", d.filter_category_name == "")

    d.search = "GUIDE"
    check("search matches note, case-insensitive", visible_names(ui, d) == ["Rename objects"])
    d.search = "output"
    check("search matches category", visible_names(ui, d) == ["Camera"])
    d.search = "  units  "
    check("search trims spaces", visible_names(ui, d) == ["Units"])
    d.search = "camera"
    d.filter_category_name = "Setup"
    check("search AND category", visible_names(ui, d) == [])
    reset_view(d)

    items = ct.properties._category_items(d, bpy.context)
    labels = [i[1] for i in items]
    check("category enum labels", labels == ["All Categories", "Setup  (1/2)", "Scene  (1/3)", "Uncategorized  (1/2)",
                                             "Output  (0/1)", "setup  (0/1)"], labels)
    check("category enum values unique", sorted(i[4] for i in items) == list(range(len(items))))
    # get/set round trip for every category, by identifier and by value.
    for i, key in enumerate(i[0] for i in items):
        d.filter_category = key
        ok = d.filter_category == key and ct.properties._category_get(d) == i
        if not ok:
            break
    check("category get/set round trip", ok, (key, d.filter_category))
    ct.properties._category_set(d, 99)  # out of range: ignored
    check("out-of-range set ignored", d.filter_category == items[-1][0], d.filter_category)
    d.filter_category_name = ""
    check("filters_active false", not ct.ui.filters_active(d))
    d.hide_done = True
    check("filters_active true", ct.ui.filters_active(d))
    reset_view(d)

    d.items.clear()
    check("empty list filter", visible_names(ui, d) == [])
    items = ct.properties._category_items(d, bpy.context)
    check("empty category enum = All only", [i[0] for i in items] == [ct.properties.ALL])


def test_drawing(ct):
    ui = ct.ui
    d = bpy.context.scene.checklist
    for label, setup in (
        ("empty", lambda: d.items.clear()),
        ("filled", lambda: fill(d, ROWS)),
        ("filtered", lambda: (fill(d, ROWS), setattr(d, "filter_category_name", "Scene"), setattr(d, "hide_done", True))),
        ("all done hidden", lambda: (fill(d, [("a", "X", True)]), setattr(d, "hide_done", True))),
    ):
        reset_view(d)
        setup()
        log = []
        for cls in (ui.CHECKLIST_PT_main, ui.CHECKLIST_PT_templates):
            log += draw(cls)
        if ui.CHECKLIST_PT_task.poll(bpy.context):
            log += draw(ui.CHECKLIST_PT_task)
        check(f"draw {label}: names valid", not bad(log), bad(log))
        if label == "filtered":
            check("draw filtered: 'Showing' label",
                  ("label", "Showing 2 of 9 tasks") in log, [e for e in log if e[0] == "label"])
        if label == "empty":
            check("draw empty: hint", ("label", "Empty checklist") in log)
            check("draw empty: no task panel", not ui.CHECKLIST_PT_task.poll(bpy.context))
        if label == "filled":
            check("draw filled: progress", ("progress", "3 / 9 done") in log, [e for e in log if e[0] == "progress"])
    reset_view(d)
    fill(d, ROWS)
    header = []
    ui.CHECKLIST_PT_main.draw_header_preset(types.SimpleNamespace(layout=FakeLayout(header)), bpy.context)
    check("header count", ("label", "3/9") in header, header)
    lst = types.SimpleNamespace()
    for i, it in enumerate(d.items):
        log = []
        ui.CHECKLIST_UL_items.draw_item(lst, bpy.context, FakeLayout(log), d, it, 0, d, "active_index", i)
        if bad(log):
            check("draw_item names", False, bad(log))
            break
    else:
        check("draw_item names", True)
    log = []
    ui.CHECKLIST_UL_items.draw_filter(lst, bpy.context, FakeLayout(log))
    check("draw_filter runs", bool(log))
    prefs = ct.properties.get_prefs()
    log = []
    type(prefs).draw(types.SimpleNamespace(layout=FakeLayout(log), bl_rna=prefs.bl_rna), bpy.context)
    check("preferences draw", not bad(log), bad(log))


def test_new_file_handler(ct):
    prefs = ct.properties.get_prefs()
    prefs.auto_apply = True
    prefs.default_template = "general_project"
    bpy.ops.wm.read_homefile(use_factory_startup=True)
    # read_homefile reloads preferences; make sure the add-on is still on.
    if MOD not in bpy.context.preferences.addons:
        addon_utils.enable(MOD, default_set=True)
        ct = importlib.import_module(MOD)
        prefs = ct.properties.get_prefs()
        d = bpy.context.scene.checklist
        d.items.clear()
        ct._on_load_post()
    d = bpy.context.scene.checklist
    check("new file filled from default", len(d.items) == 11 and d.template_name == "General Project",
          (len(d.items), d.template_name))
    ct._on_load_post()
    check("handler idempotent", len(d.items) == 11)

    d.items.clear()
    prefs.auto_apply = False
    ct._on_load_post()
    check("auto_apply off -> untouched", len(d.items) == 0)
    prefs.auto_apply = True

    prefs.default_template = "missing_template"
    ct._on_load_post()
    check("missing default template -> no crash, empty", len(d.items) == 0)
    prefs.default_template = "general_project"

    path = os.path.join(os.environ["CT_PROFILE"], "saved.blend")
    bpy.ops.wm.save_as_mainfile(filepath=path)
    d = bpy.context.scene.checklist
    ct._on_load_post()
    check("saved file -> untouched", len(d.items) == 0)

    d.items.add().name = "persisted"
    bpy.ops.wm.save_mainfile()
    bpy.ops.wm.open_mainfile(filepath=path)
    d = bpy.context.scene.checklist
    check("checklist saved in .blend", [i.name for i in d.items] == ["persisted"])
    return importlib.import_module(MOD)


def main():
    try:
        addon_utils.enable(MOD, default_set=True)
        ct = importlib.import_module(MOD)
    except Exception:
        check("enable add-on", False, traceback.format_exc())
        ct = None
    if ct:
        for fn in (test_registration, test_templates_module, test_empty_templates_enum,
                   test_operators, test_filters, test_drawing):
            try:
                fn(ct)
            except Exception:
                check(fn.__name__ + " crashed", False, traceback.format_exc())
        try:
            ct = test_new_file_handler(ct)
        except Exception:
            check("test_new_file_handler crashed", False, traceback.format_exc())
        try:
            test_reenable()
        except Exception:
            check("test_reenable crashed", False, traceback.format_exc())
    failed = [r for r in RESULTS if not r[1]]
    print("\n%d checks, %d failed" % (len(RESULTS), len(failed)))
    for name, _, detail in failed:
        print("FAILED:", name, detail)
    sys.stdout.flush()
    os._exit(1 if failed else 0)


main()
