# Checklist Tool

[![Blender](https://img.shields.io/badge/dynamic/toml?url=https%3A%2F%2Fraw.githubusercontent.com%2Fmttfntn%2Fchecklist-tool-blender%2Fmain%2Fchecklist_tool%2Fblender_manifest.toml&query=%24.blender_version_min&label=Blender&color=E87D0D&logo=blender&logoColor=white)](https://www.blender.org/download/)
[![Release](https://img.shields.io/github/v/release/mttfntn/checklist-tool-blender)](https://github.com/mttfntn/checklist-tool-blender/releases/latest)
[![Tests](https://github.com/mttfntn/checklist-tool-blender/actions/workflows/ci.yml/badge.svg)](https://github.com/mttfntn/checklist-tool-blender/actions/workflows/ci.yml)
[![License](https://img.shields.io/github/license/mttfntn/checklist-tool-blender)](LICENSE)
[![Language](https://img.shields.io/github/languages/top/mttfntn/checklist-tool-blender)](checklist_tool/__init__.py)

A Blender 5.3 add-on that keeps a **manual project checklist inside each .blend
file**, in the 3D Viewport sidebar (**N › Checklist**). Tasks have a category,
so you can search them, filter by category, sort them and hide what is done.
Checklists start from reusable **templates** (plain JSON files), and every new
file can start with your default template already filled in.

For maintainers: [HANDOVER.md](HANDOVER.md) (people) and [AGENTS.md](AGENTS.md)
(AI assistants).

## Using it

```
Checklist                         3/11
General Project
[██████░░░░░░░░░] 3 / 11 done
[🔍 Search tasks                    ]
▾ Filter                  Scene, hiding done
     Category  [ Scene  (2/3)      ▾]
         Sort  [ Category          ▾]
               ☑ Hide Done
     [ ✕ Clear Filters ]
┌────────────────────────────────┐ [+]
│ ☐ Rename default objects       │ [−]
└────────────────────────────────┘
Showing 1 of 11 tasks
▸ Task
▸ Templates
```

- **Tasks:** tick the box when a task is done. Double-click a task to rename
  it. **+** adds a task and **−** removes the selected one. The **Task**
  section edits the selected task's name, category and note.
- **Progress:** the bar and the panel header show how many tasks are done.
- **Search:** matches the task name, category and note as you type.
- **Filter** (foldable; its header lists the active filters when folded):
  - **Category:** All, or one category. Each shows its own done/total, for
    example `Scene (2/3)`. Tasks without a category are listed as
    *Uncategorized*.
  - **Sort:** **Category** (grouped, in the order categories first appear),
    **To Do First** (done tasks at the bottom) or **Name** (A–Z).
  - **Hide Done:** hides ticked tasks (they still count in the progress).
  - **Clear Filters:** shows everything again (the sort is kept).
- **New tasks** go into the category you are filtering on, otherwise into the
  selected task's category.

The checklist is saved inside the .blend file, so ticks travel with the project.

## Templates

The **Templates** section manages reusable checklists:

- **Replace** fills the checklist from the selected template; **Append** adds
  its tasks to the current ones.
- **Save Current** saves the current tasks as a template (name and optional
  description). Saving with the name of an existing template overwrites it.
- 🗑 deletes the selected template file.
- **Set as Default** picks the template for new files, and **Auto-apply on New
  File** turns that on or off. When it is on, File › New (and Blender's startup
  scene) start with that template's tasks. Saved files and files that already
  have tasks are never changed.

Shipped templates: **General Project** (the default), **Game Asset**,
**Animation** and **Lookdev & Render**. They are copied once into your
templates folder; after that you can edit or delete them freely.

Each template is one JSON file in:

```
macOS:   ~/Library/Application Support/Blender/5.3/extensions/.user/user_default/checklist_tool/templates/
Windows: %APPDATA%\Blender Foundation\Blender\5.3\extensions\.user\user_default\checklist_tool\templates\
Linux:   ~/.config/blender/5.3/extensions/.user/user_default/checklist_tool/templates/
```

(also under Preferences › Add-ons › Checklist Tool, with a button to open it)

```json
{
  "name": "Game Asset",
  "description": "Modeling and export prep for real-time assets",
  "items": [
    {"name": "Unwrap UVs", "category": "UV", "note": ""},
    {"name": "Check texel density", "category": "UV", "note": ""}
  ]
}
```

New or edited files show up the next time the dropdown is opened. Copy the
files to share templates with a team or another computer. Applying a template
copies its tasks into the file, so later template edits never change files
that already used it.

## Install

Requires **Blender 5.3**.

1. Download `checklist_tool-<version>.zip` from the
   [latest release](https://github.com/mttfntn/checklist-tool-blender/releases/latest).
2. In Blender: Edit › Preferences › Get Extensions › ▾ (top right) ›
   **Install from Disk...**, pick the zip. It is enabled right away.

Your templates are kept when you update or uninstall the add-on.

## Uninstall

Preferences › Get Extensions (or Add-ons), find Checklist Tool, ▾ ›
**Uninstall**. Checklists already saved in .blend files stay in those files
and come back if you reinstall.

## Known limits

- One checklist per **scene**: a file with several scenes has a separate
  checklist in each.
- Tasks can't be reordered by hand. They keep the order they were added in,
  shown through the Sort options.
- **Category** sort groups categories ignoring letter case ("setup" next to
  "Setup"), while the category filter treats them as two categories.
- Templates don't store the done state.
- **Auto-apply on New File** works once Blender's preferences are saved with the
  add-on enabled (Auto-save Preferences does this when you quit).

## Development

See [HANDOVER.md](HANDOVER.md) for the code layout, tests and releases.

## Contributing

Bug reports, ideas, templates and pull requests are welcome: see
[CONTRIBUTING.md](CONTRIBUTING.md). Open an issue with one of the
[forms](https://github.com/mttfntn/checklist-tool-blender/issues/new/choose); report security problems privately as described
in [SECURITY.md](SECURITY.md).

## License

GPL-3.0-or-later, see [LICENSE](LICENSE). © 2026 Matteo Fontana.
