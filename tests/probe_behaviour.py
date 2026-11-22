"""Record the add-on's observable behaviour as JSON, for old/new comparisons.

    python3 tests/run_blender.py tests/probe_behaviour.py -- new.json
    python3 tests/run_blender.py --addon-root OLD_COPY tests/probe_behaviour.py -- old.json
    python3 tests/compare_probes.py old.json new.json

Seeded random scenarios (same seed = same inputs on every copy) cover:
the visible list for every sort / hide-done / category / search combination,
category menu labels, panel draw output, random operator sequences, template
name slugs and parsing, and the new-file handler.
"""

import importlib
import json
import os
import random
import sys
import traceback
import types

import addon_utils
import bpy

MOD = os.environ.get("CT_MODULE", "bl_ext.user_default.checklist_tool")
OUT = sys.argv[sys.argv.index("--") + 1] if "--" in sys.argv and len(sys.argv) > sys.argv.index("--") + 1 else "probe.json"
SEED = 1234
CATS = ["Setup", "Scene", "scene", "Shading", "Output", "", "  ", "UV ", "Lighting"]
WORDS = ["save", "apply", "camera", "UV", "bake", "render", "check", "export", "light", "rig", "name", "final"]
SEARCHES = ["", "a", "save", "UV", "scene", "  render ", "zzz", "Note"]


class Recorder:
    def __init__(self, log):
        self.__dict__["log"] = log

    def __getattr__(self, name):
        log = self.log

        def call(*args, **kw):
            entry = [name]
            if name in ("prop", "prop_search"):
                entry.append(args[1])
            elif name == "operator":
                entry.append(args[0])
            elif name == "template_list":
                entry.append(args[0])
            elif name == "panel":
                entry.append(args[0])
            for k in sorted(kw):
                entry.append(f"{k}={kw[k]}")
            log.append(entry)
            if name == "operator":
                return types.SimpleNamespace()
            if name == "panel":
                return Recorder(log), Recorder(log)
            return Recorder(log)
        return call

    def __setattr__(self, name, value):
        self.log.append(["set", name, repr(value)])


def draw(cls):
    log = []
    cls.draw(types.SimpleNamespace(layout=Recorder(log)), bpy.context)
    return log


def visible(ui, d):
    fake = types.SimpleNamespace(bitflag_filter_item=1 << 30, filter_name="", use_filter_invert=False)
    flags, order = ui.CHECKLIST_UL_items.filter_items(fake, bpy.context, d, "items")
    idx = list(range(len(d.items)))
    if order:
        idx.sort(key=lambda i: order[i])
    return [i for i in idx if flags[i]]


def random_tasks(rng, n):
    rows = []
    for _ in range(n):
        name = " ".join(rng.choice(WORDS) for _ in range(rng.randint(1, 3))).capitalize()
        rows.append((name, rng.choice(CATS), rng.random() < 0.4, rng.choice(["", "", "Note: " + rng.choice(WORDS)])))
    return rows


def fill(d, rows):
    d.items.clear()
    for name, cat, done, note in rows:
        it = d.items.add()
        it.name, it.category, it.done, it.note = name, cat, done, note
    d.active_index = 0


def state(d):
    return {
        "items": [[i.name, i.category, i.done, i.note] for i in d.items],
        "active": d.active_index, "template": d.template_name, "search": d.search,
        "cat": d.filter_category_name, "hide": d.hide_done, "sort": d.sort_mode,
    }


def safe(fn):
    try:
        return fn()
    except Exception as exc:
        return "EXC " + type(exc).__name__ + ": " + str(exc).splitlines()[0]


def probe_views(ct, rng):
    ui, P = ct.ui, ct.properties
    d = bpy.context.scene.checklist
    out = []
    for scenario in range(60):
        rows = random_tasks(rng, rng.randint(0, 14))
        fill(d, rows)
        rec = {"rows": rows, "menu": [list(i) for i in P._category_items(d, bpy.context)], "views": {}}
        keys = [P.ALL] + [k for k in P.categories(d)] + ["Missing"]
        for sort in ("CATEGORY", "TODO_FIRST", "NAME"):
            for hide in (False, True):
                for key in keys:
                    for search in SEARCHES:
                        d.sort_mode, d.hide_done, d.search = sort, hide, search
                        d.filter_category_name = "" if key == P.ALL else key
                        rec["views"][f"{sort}|{hide}|{key}|{search}"] = [
                            visible(ui, d), d.filter_category, ui.filters_active(d)]
        d.sort_mode, d.hide_done, d.search, d.filter_category_name = "CATEGORY", False, "", ""
        out.append(rec)
    return out


def probe_draw(ct, rng):
    ui = ct.ui
    d = bpy.context.scene.checklist
    out = []
    for scenario in range(25):
        fill(d, random_tasks(rng, rng.randint(0, 8)))
        d.active_index = rng.randint(-1, max(0, len(d.items)))
        d.hide_done = rng.random() < 0.5
        d.search = rng.choice(SEARCHES)
        d.filter_category_name = rng.choice(["", "Scene", "Missing", ct.properties.UNCATEGORIZED])
        d.template_name = rng.choice(["", "General Project"])
        rec = {"main": safe(lambda: draw(ui.CHECKLIST_PT_main)),
               "templates": safe(lambda: draw(ui.CHECKLIST_PT_templates)),
               "task_poll": ui.CHECKLIST_PT_task.poll(bpy.context)}
        if rec["task_poll"]:
            rec["task"] = safe(lambda: draw(ui.CHECKLIST_PT_task))
        header = []
        ui.CHECKLIST_PT_main.draw_header_preset(types.SimpleNamespace(layout=Recorder(header)), bpy.context)
        rec["header"] = header
        rows = []
        for i, it in enumerate(d.items):
            log = []
            ui.CHECKLIST_UL_items.draw_item(types.SimpleNamespace(), bpy.context, Recorder(log), d, it, 0, d, "active_index", i)
            rows.append(log)
        rec["rows"] = rows
        out.append(rec)
    d.search, d.filter_category_name, d.hide_done = "", "", False
    return out


def probe_operators(ct, rng):
    wm = bpy.context.window_manager
    d = bpy.context.scene.checklist
    out = []
    for scenario in range(40):
        fill(d, random_tasks(rng, rng.randint(0, 6)))
        d.search, d.filter_category_name, d.hide_done = "", "", False
        steps = []
        for _ in range(12):
            op = rng.choice(["add", "remove", "apply_r", "apply_a", "clear", "filter", "search", "select", "hide"])
            if op == "add":
                r = safe(lambda: bpy.ops.checklist.add('EXEC_DEFAULT'))
            elif op == "remove":
                r = safe(lambda: bpy.ops.checklist.remove('EXEC_DEFAULT'))
            elif op in ("apply_r", "apply_a"):
                wm.checklist_template = rng.choice(["general_project", "game_asset", "animation", "lookdev_render"])
                r = safe(lambda: bpy.ops.checklist.apply_template(
                    'EXEC_DEFAULT', mode='REPLACE' if op == "apply_r" else 'APPEND'))
            elif op == "clear":
                r = safe(lambda: bpy.ops.checklist.clear_filters('EXEC_DEFAULT'))
            elif op == "filter":
                d.filter_category_name = rng.choice(["", "Setup", "Scene", ct.properties.UNCATEGORIZED, "Nope"])
                r = d.filter_category_name
            elif op == "search":
                d.search = rng.choice(SEARCHES)
                r = d.search
            elif op == "hide":
                d.hide_done = not d.hide_done
                r = d.hide_done
            else:
                d.active_index = rng.randint(-2, len(d.items) + 1)
                r = d.active_index
            steps.append([op, r if isinstance(r, (str, int, bool)) else sorted(r), state(d)])
        out.append(steps)
    d.search, d.filter_category_name, d.hide_done = "", "", False
    return out


def probe_templates(ct, rng):
    T = ct.templates
    folder = T.templates_dir()
    out = {"list": T.list_templates(), "loaded": {s: T.load(s) for s, _, _ in T.list_templates()}}
    chars = "abcXYZ 09_-/\\&*.éß  "
    out["slugs"] = {}
    for _ in range(300):
        raw = "".join(rng.choice(chars) for _ in range(rng.randint(0, 12)))
        out["slugs"][raw] = T.slugify(raw)
    variants = [
        {}, {"name": 5}, {"items": ["a", {"name": "b"}, {"section": "S"}, {"category": "C", "section": "S"},
                                       {"name": "n", "note": 3, "auto_check": "X"}]},
        {"name": "N", "description": "D", "items": []},
    ]
    out["sanitize"] = []
    for i, v in enumerate(variants):
        with open(os.path.join(folder, f"probe_{i}.json"), "w") as f:
            json.dump(v, f)
        out["sanitize"].append(safe(lambda: T.load(f"probe_{i}")))
    out["list_with_probes"] = T.list_templates()
    out["enum"] = [list(x) for x in T.enum_items(None, bpy.context)]
    for i in range(len(variants)):
        T.delete(f"probe_{i}")
    stem = T.save("Probe Save", "d", [{"name": "x", "category": "y", "note": "z"}])
    out["saved"] = [stem, T.load(stem)]
    T.delete(stem)
    return out


def probe_handler(ct):
    out = []
    prefs = ct.properties.get_prefs()
    d = bpy.context.scene.checklist
    for auto in (True, False):
        for default in ("general_project", "game_asset", "nope"):
            for pre in (0, 2):
                fill(d, [("pre", "", False, "")] * pre)
                prefs.auto_apply, prefs.default_template = auto, default
                ct._on_load_post()
                out.append([auto, default, pre, state(d)])
    prefs.auto_apply, prefs.default_template = True, "general_project"
    return out


def main():
    result = {}
    try:
        addon_utils.enable(MOD, default_set=True)
        ct = importlib.import_module(MOD)
        rng = random.Random(SEED)
        for name, fn in (("views", probe_views), ("draw", probe_draw), ("operators", probe_operators),
                         ("templates", probe_templates)):
            result[name] = fn(ct, rng)
        result["handler"] = probe_handler(ct)
    except Exception:
        result["crash"] = traceback.format_exc()
    with open(OUT, "w", encoding="utf-8") as f:
        json.dump(result, f, indent=1, sort_keys=True, default=str)
    print("probe written:", OUT, {k: len(v) for k, v in result.items()})
    sys.stdout.flush()
    os._exit(1 if "crash" in result else 0)


main()
