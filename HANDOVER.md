# Handover: Checklist Tool

## What it is

A Blender 5.3 extension that keeps a manual checklist inside each .blend file,
shown in the 3D Viewport sidebar (N › Checklist). Tasks have a name, a done
box, a category and a note. Users can search them, filter by category, sort
them and hide done tasks. Checklists start from templates: JSON files in the
extension's user folder that users can save, edit, share and delete. When
**Auto-apply on New File** is on, a new file gets the default template's tasks.

It is not a fork: there is no upstream project. Author: Matteo Fontana.
Repository: <https://github.com/mttfntn/checklist-tool-blender> (public).

## What you need

- **Blender 5.3**, the only supported version (manifest `blender_version_min`
  5.3.0, `blender_version_max` 5.4.0, which is exclusive). The code uses
  `layout.panel()` and the `invoke_confirm(title=..., message=...)` options,
  both newer than 4.2.
- **Python 3.9+** to run `tests/run_blender.py`, `tests/compare_probes.py` and
  `tools/build_package.py`. The add-on itself only uses Blender's Python.
- `gh` (GitHub CLI) only for release work.

## How the code is organized

| File | What it holds |
|---|---|
| `checklist_tool/__init__.py` | Registers the modules and adds the `load_post` handler `_on_load_post` (new file → default template). |
| `checklist_tool/properties.py` | `CHECKLIST_Item` (one task) and `CHECKLIST_Data` (`Scene.checklist`: tasks + view state), the category filter enum (`categories`, `_category_items/_get/_set`), `CHECKLIST_Preferences`, `get_prefs`, and `WindowManager.checklist_template` (the template dropdown). |
| `checklist_tool/templates.py` | Template files: `templates_dir`, `ensure_defaults` (seed once), `list_templates` (cached index), `load`/`save`/`delete`, `_sanitize`, `apply`, `items_from_checklist`, `enum_items` (dropdown items). |
| `checklist_tool/operators.py` | `checklist.add`, `remove`, `clear_filters`, `apply_template`, `save_template`, `delete_template`, `set_default_template`, `open_templates_folder`. |
| `checklist_tool/ui.py` | `CHECKLIST_UL_items` (list; filtering and sorting), `CHECKLIST_PT_main` (progress, search, Filter section, list), `CHECKLIST_PT_task`, `CHECKLIST_PT_templates`; helpers `task_visible`, `_sort_key`, `filters_active`. |
| `checklist_tool/default_templates/*.json` | The four shipped templates. |
| `checklist_tool/blender_manifest.toml` | Extension manifest (id, version, supported Blender, license). |
| `tests/run_blender.py` | Starts headless Blender with a throwaway profile containing the add-on, and runs a script in it. |
| `tests/test_checklist.py` | The test suite (144 checks). |
| `tests/probe_behaviour.py`, `tests/compare_probes.py` | Old/new behaviour comparison. |
| `tests/check_installed_package.py` | Checks a built zip after installing it in a scratch profile. |
| `tools/build_package.py` | Builds `dist/checklist_tool-<version>.zip` (adds LICENSE). |
| `.github/workflows/ci.yml` | Tests, build, install check; on a `v*` tag also the release. |

## How the main feature works

1. **Data.** `bpy.types.Scene.checklist` is a `CHECKLIST_Data` pointer, so the
   checklist is saved in the .blend file, one per scene. It holds `items`
   (`CHECKLIST_Item`: `name`, `done`, `category`, `note`), `active_index`,
   `template_name` and the view state: `search`, `hide_done`, `sort_mode`
   (`CATEGORY`, `TODO_FIRST`, `NAME`) and `filter_category_name`.
2. **Category filter.** `filter_category_name` is a plain string ("" = all,
   `UNCATEGORIZED` = tasks without a category). The UI shows it as the dynamic
   enum `filter_category`. `_category_items` builds the menu (with done/total
   per category), and `_category_get`/`_category_set` map between the string
   and the enum index. If a category disappears, the filter reads as "All" but
   keeps hiding everything until the user picks another one.
3. **Showing the list.** `CHECKLIST_UL_items.filter_items` returns one flag per
   task from `task_visible` (search in name, category and note, ignoring case;
   category; hide done) and a display order from `_sort_key`. Sorting never
   changes the stored order. The panel's "Showing N of M" counter uses the same
   `task_visible`.
4. **Templates.** The JSON files live in `templates_dir()`, which is
   `bpy.utils.extension_path_user(__package__, "templates")`. When the add-on
   is loaded as a legacy add-on, it falls back to
   `<config>/checklist_tool_templates`. `ensure_defaults()` copies the shipped
   files once and writes a `.seeded` marker. `list_templates()` caches each
   file's name and description by (mtime, size), so redraws don't re-parse the
   JSON. `apply()` copies tasks into the scene (Replace clears first).
5. **New files.** `_on_load_post` runs after every load. It fills the checklist
   only if `auto_apply` is on, the file was never saved (`bpy.data.filepath` is
   empty), the checklist is empty and the default template loads.

## How to make a change

1. Read the relevant module (the table above) and its tests.
2. Change the code. For operators, panels and lists, put the tooltip in
   `bl_description` and internal notes in `#` comments.
3. Add or update checks in `tests/test_checklist.py`. A bug fix needs a check
   that fails without it.
4. Run both test modes, and the old/new comparison if behaviour could change
   (next section).
5. Update the README if users will notice the change.

## How to run the tests

From the repo root (macOS shown; elsewhere pass `--blender PATH` or set `BLENDER`):

```
python3 tests/run_blender.py              # loaded as an extension
python3 tests/run_blender.py --legacy     # loaded as a legacy add-on (templates_dir fallback)
```

Each ends with `144 checks, 0 failed` and exits 1 on any failure. Blender runs
with `--background --factory-startup` and every `BLENDER_USER_*` folder inside
a temporary profile, so your real profile and open sessions are never touched.

**Old/new comparison:**

```
git worktree add /tmp/ct_old HEAD                     # or any older commit
python3 tests/run_blender.py --addon-root /tmp/ct_old tests/probe_behaviour.py -- old.json
python3 tests/run_blender.py tests/probe_behaviour.py -- new.json
python3 tests/compare_probes.py old.json new.json     # "0 difference(s)" when nothing changed
```

The probe is seeded, so two runs of the same code give 0 differences (checked:
100,093 recorded values).

**Built package:**

```
python3 tools/build_package.py
export BLENDER_USER_RESOURCES=/tmp/ctp BLENDER_USER_CONFIG=/tmp/ctp/config BLENDER_USER_SCRIPTS=/tmp/ctp/scripts BLENDER_USER_EXTENSIONS=/tmp/ctp/extensions
blender -b --factory-startup --command extension install-file --repo user_default --enable dist/checklist_tool-*.zip
blender -b --python-exit-code 1 --python tests/check_installed_package.py    # "PROBLEMS: none"
```

CI runs all of this except the comparison, on Linux with Blender 5.3.0.

## How to make a release

1. Bump `version` in `checklist_tool/blender_manifest.toml`. The README badges
   are live (shields.io and GitHub), so never hard-code a version in them.
   The download-size badge reads `.github/release-size.json` on `main`; after each release CI updates it with a bot commit on `main`, so pull before your next change.
2. Run the tests, commit, push to `main` and wait for green CI.
3. Create an **annotated** tag; its message becomes the release notes:
   `git tag -a v1.2.3 -m "Checklist Tool 1.2.3" -m "- what changed"`, then
   `git push origin v1.2.3`.
4. CI checks that the tag matches the manifest version, then tests, builds and
   publishes the GitHub release with the zip attached.
5. Install the new zip in your Blender (README › Install).

## Bringing in updates from the original project

Not applicable: this project is not a fork. If Blender changes its API, the
places most likely to need work are listed under *Things to know*.

## Things to know

- **Dynamic enums.** Blender keeps raw pointers to the strings an items
  callback returns. `_enum_cache` (templates) and `_category_enum_cache`
  (categories) keep them referenced. Blender calls the items callback itself
  whenever the value is read or set, so `_category_get`/`_category_set` only
  use `_category_keys` and never rebuild the list.
- **Background mode.** There, an operator's `report({'ERROR'}, ...)` is raised
  as `RuntimeError`. The tests catch it for the blank-name save.
- **`read_homefile` reloads the preferences**, so in a test it disables an
  add-on that was enabled without saved preferences. The new-file test
  re-enables it.
- **Templates folder.** Uninstalling or upgrading the extension keeps the
  `.user` folder, so templates survive. Deleting `.seeded` re-copies any
  missing shipped template on the next start.
- **Old files.** The unreleased 1.1.0 had a `MANUAL` sort mode. Files saved
  with it show an empty Sort field until a sort is picked, but the list still
  sorts by category.
- **Draw code** only reads data. `filter_items` runs on every redraw (0.7 ms for
  300 tasks). `enum_items` runs on every redraw of the Templates panel: it does
  one `scandir` and parses only changed files (0.04 ms for 4 templates, 0.18 ms
  for 44).
- **The id `checklist_tool` must never change.** Installed copies would stop
  upgrading in place, and the templates folder would move.

## Known limits

- One checklist per scene. No manual reordering; tasks keep the order they
  were added in.
- Category sort ignores letter case; the category filter does not.
- Saving a template whose name gives the same file name as another one (for
  example "Game  Asset" and "Game Asset") overwrites that template without
  asking.
- A template file that is not valid JSON is skipped silently (nothing is
  printed).
- The panel itself is checked by drawing into a fake layout in the tests (every
  property, operator and layout call is validated). The look in a real window
  was checked by hand.
