# AGENTS.md: Checklist Tool

Blender 5.3 extension. It keeps a manual checklist per scene (saved in the
.blend file) in the 3D Viewport sidebar (N › Checklist), with search, a
category filter, sort and hide done. Tasks come from JSON templates in the
extension user folder; a new file can get the default template on load.
Humans: see HANDOVER.md.

## Commands (repo root; macOS Blender is found automatically, else `--blender PATH` / `BLENDER=`)

```
python3 tests/run_blender.py                       # 144 checks, must end "0 failed" (extension load)
python3 tests/run_blender.py --legacy              # same suite, legacy add-on load (templates_dir fallback)
python3 tests/run_blender.py --addon-root OLD tests/probe_behaviour.py -- old.json
python3 tests/run_blender.py tests/probe_behaviour.py -- new.json
python3 tests/compare_probes.py old.json new.json  # 0 differences unless behaviour changed on purpose
python3 tools/build_package.py                     # -> dist/checklist_tool-<ver>.zip (+ LICENSE)
# scratch-profile install check:
export BLENDER_USER_RESOURCES=<tmp> BLENDER_USER_CONFIG=<tmp>/config BLENDER_USER_SCRIPTS=<tmp>/scripts BLENDER_USER_EXTENSIONS=<tmp>/extensions
blender -b --factory-startup --command extension install-file --repo user_default --enable dist/checklist_tool-*.zip
blender -b --python-exit-code 1 --python tests/check_installed_package.py   # "PROBLEMS: none"
```

## Architecture

- `properties.py`
  - `CHECKLIST_Item`: `name`, `done`, `category`, `note`.
  - `CHECKLIST_Data` (`Scene.checklist`): `items`, `active_index`, `template_name`, `search`, `hide_done`,
    `sort_mode` (CATEGORY | TODO_FIRST | NAME), `filter_category_name` (str: "" = all, `UNCATEGORIZED` = no
    category), `filter_category` (dynamic enum over it: `_category_items` / `_category_get` / `_category_set`,
    with `_category_keys` = [ALL, *categories]).
  - `CHECKLIST_Preferences` (`bl_idname = __package__`): `auto_apply`, `default_template` (file stem).
    `get_prefs()` returns None when not enabled.
  - `WindowManager.checklist_template`: enum, items = `templates.enum_items`.
- `templates.py`: `templates_dir()` = `extension_path_user(__package__, "templates")`, falling back to
  `<config>/checklist_tool_templates`. `ensure_defaults()` seeds `default_templates/` once (`.seeded` marker).
  `list_templates()` -> [(stem, name, description)], with a cache `_index` keyed by (mtime_ns, size).
  Also `load`/`save`/`delete`, `_sanitize` (accepts the legacy "section" key and string items) and `apply`.
- `operators.py`: `checklist.add` (category = filtered category, else the active task's; UNCATEGORIZED -> ""),
  `remove`, `clear_filters`, `apply_template` (REPLACE|APPEND), `save_template`, `delete_template`,
  `set_default_template`, `open_templates_folder`.
- `ui.py`: `CHECKLIST_UL_items.filter_items` = flags from `task_visible()` + order from `_sort_key()`.
  `CHECKLIST_PT_main` (progress, search, `layout.panel("CHECKLIST_filter")`, list, +/-), sub-panels
  `CHECKLIST_PT_task` and `CHECKLIST_PT_templates`.
- `__init__.py`: registers properties -> operators -> ui, then `ensure_defaults()` and the `load_post`
  handler `_on_load_post` (only for a never-saved file with an empty checklist when `auto_apply` is on).
- Data flow: a template JSON is read by `load`/`_sanitize`, then `apply` puts it into `Scene.checklist.items`.
  The UIList then runs `filter_items` (task_visible + _sort_key) and the panels draw it. Save goes the other
  way: `items_from_checklist` then `save` writes the JSON.

## Rules

- Never run anything in the user's open Blender or real profile. Use `tests/run_blender.py` (factory
  startup, temporary `BLENDER_USER_*`) and a scratch profile for install checks.
- Supported: Blender 5.3 only (manifest min 5.3.0, max 5.4.0). CI downloads exactly `BLENDER_VERSION` in
  `ci.yml`.
- Operator, panel and UIList docstrings become tooltips: use `bl_description` + `#` comments. Module and
  function docstrings are fine.
- Draw code only reads data.
- Bug fix -> add a check in `tests/test_checklist.py` that fails without it. Behaviour change -> run the
  probe comparison and explain every difference.
- Never change the extension id `checklist_tool` (in-place upgrades, templates folder).

## Pitfalls found in this project

- Blender calls a dynamic enum's items callback on every get/set of the value. Don't rebuild the items
  list inside get/set (it was done twice per read before 1.2.1). Strings returned to Blender must stay
  referenced (module-level caches).
- Background mode turns `report({'ERROR'})` into `RuntimeError`.
- `bpy.ops.wm.read_homefile()` reloads preferences, so an add-on enabled without saved prefs gets disabled.
- PropertyGroup classes are not reachable as `bpy.types.CHECKLIST_Data`: use
  `Scene.bl_rna.properties["checklist"].fixed_type`.
- `UILayout` methods are not Python attributes of `bpy.types.UILayout`: check them with
  `UILayout.bl_rna.functions`.
- A safety hook in the agent environment refuses `rm -rf` with variables or globs: use explicit paths or
  fresh folders.
- Screenshots of the user's Blender (`screen.screenshot_area`) come back 1x1 when its window is minimized
  or a timer runs them. UI is verified headlessly with a fake layout instead.

## How changes were verified (wrap-up, 2026-11-22)

- Baseline (1.2.0, before the cleanup) on the new suite: 135 checks, 1 failed. The failure was a real bug:
  `add` while filtering Uncategorized took the active task's category, so the new task was hidden at once.
- After: 144/144 in both load modes. The old code on the same final suite: 143/144 (the same bug).
- Probe old vs new: 100,093 values, 13 differences, all traced to that fix (one `add` step and the later
  steps that carry the task). Identical in extension and legacy mode. Old vs old: 0 differences.
- Template dropdown refresh: 0.191 -> 0.040 ms (4 templates), 2.058 -> 0.176 ms (44), 0 files opened.
  Category enum read: list rebuilt 2x -> 1x.
- AST scan: no unused functions, classes or imports, no constant conditions, no commented-out code; all 15
  classes registered. Removed a stale `# noqa: F401`, `.DS_Store` and an old build zip.
- Built zip installed in a scratch profile: `check_installed_package.py` reported "PROBLEMS: none".

## Release checklist

1. Bump `version` in `checklist_tool/blender_manifest.toml`. README badges are live: never hard-code
   versions. The download-size badge reads `.github/release-size.json` on `main`; after each release CI updates it with a bot commit on `main`, so pull before your next change.
2. Run both test modes. Commit and push `main`. Wait for green CI.
3. `git tag -a vX.Y.Z -m "Checklist Tool X.Y.Z" -m "<notes>"`, then `git push origin vX.Y.Z`. CI checks
   tag == manifest version, tests, builds and publishes the release with the zip. The notes come from the
   tag message.

## Git

- Remote: `origin` https://github.com/mttfntn/checklist-tool-blender.git (public, not a fork).
- Branch: `main` only (keep it that way: no extra branches; CI commits `.github/release-size.json` to `main` after each release). Tags: `vX.Y.Z` (annotated).
- Ignored: `__pycache__/`, `*.pyc`, `dist/`, `*.zip`, `.DS_Store`.
- Not shipped in the zip: everything outside `checklist_tool/` (docs, tests, tools); LICENSE is added by
  the build script.
- Community files: `.github/ISSUE_TEMPLATE/` (forms, blank issues off), `.github/pull_request_template.md`,
  `CONTRIBUTING.md`, `SECURITY.md`. Keep their test command and check count in step with the suite.
