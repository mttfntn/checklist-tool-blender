# Contributing to Checklist Tool

Thanks for helping! Bug reports, ideas and pull requests are all welcome.

## Reporting a bug or suggesting a feature

Open an [issue](https://github.com/mttfntn/checklist-tool-blender/issues/new/choose) and pick a form:

- **Bug report:** say which Blender version and add-on version you use, the template and filter settings involved, and the steps to reproduce.
- **Feature request:** describe what you're trying to do, not only the solution you have in mind.

First, check whether someone has already opened an issue for the same thing, and read the README's [known limits](https://github.com/mttfntn/checklist-tool-blender#known-limits).

## Sharing a template

Templates are plain JSON files (format in the [README](README.md#templates)). To suggest one for the shipped set, open a feature request and attach the `.json` file.

## Changing the code

[HANDOVER.md](HANDOVER.md) explains how the add-on is organised and the pitfalls already found. Read it before a larger change.

1. **Fork** the repository and create a branch for your change.
2. You need **Blender 5.3** (the only supported version) and Python 3 to run the helper scripts.
3. Run the tests from the repo root. They start a separate, headless Blender with a throwaway profile, so your own add-ons and preferences stay out of it:

   ```
   python3 tests/run_blender.py
   python3 tests/run_blender.py --legacy
   ```

   Expected result: `144 checks, 0 failed` (or more) for each. Never run the tests inside the Blender session you work in.
4. **If you fix a bug,** add a check to `tests/test_checklist.py` that fails without your fix.
5. **If you change behaviour on purpose,** compare with the previous version (HANDOVER.md, "How to run the tests") and explain every difference in the pull request.
6. **Open a pull request.** The template has a short checklist. CI runs the tests in both load modes, builds the extension and installs the built zip on Blender 5.3.

### Style

- **Operators, panels and lists:** their docstrings become tooltips, so use `#` comments for internal notes and `bl_description` for the tooltip.
- Draw code must not change data.
- Keep commits small, with messages that explain what changed and how you checked it.

## License

Checklist Tool is GPL-3.0-or-later. By contributing, you agree that your contribution is released under the same license.
