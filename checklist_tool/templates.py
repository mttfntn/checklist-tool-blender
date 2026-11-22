"""Checklist templates: JSON files in the extension's user folder.

A template is one file, ``<slug>.json``::

    {"name": "Game Asset", "description": "...",
     "items": [{"name": "Unwrap UVs", "category": "UV", "note": ""}, ...]}

The shipped templates (``default_templates/``) are copied into the user
folder once (see ``ensure_defaults``). After that the user folder is the only
source: the Templates panel lists it, Save writes to it, Delete removes from
it. ``apply`` copies a template's tasks into a scene's checklist, so later
template edits never change existing .blend files.
"""

import json
import os
import re
import shutil

import bpy

PACKAGE = __package__
SHIPPED_DIR = os.path.join(os.path.dirname(__file__), "default_templates")
SEED_MARKER = ".seeded"


def templates_dir():
    """Folder holding the template files (created if missing).

    Installed as an extension it is
    ``<user extensions>/.user/user_default/checklist_tool/templates`` (kept on
    upgrade/uninstall of the package itself). Loaded any other way it falls
    back to ``<user config>/checklist_tool_templates``.
    """
    try:
        path = bpy.utils.extension_path_user(PACKAGE, path="templates", create=True)
    except (ValueError, AttributeError):
        path = bpy.utils.user_resource('CONFIG', path="checklist_tool_templates", create=True)
    return path


def ensure_defaults():
    """Copy the shipped templates into the user folder, only the first time.

    A marker file records that seeding happened, so a default the user deleted
    does not come back on the next start.
    """
    folder = templates_dir()
    marker = os.path.join(folder, SEED_MARKER)
    if os.path.exists(marker):
        return
    if os.path.isdir(SHIPPED_DIR):
        for fn in os.listdir(SHIPPED_DIR):
            if fn.endswith(".json") and not os.path.exists(os.path.join(folder, fn)):
                shutil.copy2(os.path.join(SHIPPED_DIR, fn), os.path.join(folder, fn))
    with open(marker, "w") as f:
        f.write("default templates copied\n")


def slugify(name):
    """File name (without .json) for a template name: "Game Asset" -> "game_asset"."""
    slug = re.sub(r"[^A-Za-z0-9_-]+", "_", name.strip()).strip("_").lower()
    return slug or "template"


# path -> ((mtime_ns, size), (name, description) or None for unreadable files).
# The Templates dropdown asks for the list on every redraw; parsing every JSON
# file each time is avoided by re-reading only files whose mtime or size changed.
_index = {}


def list_templates():
    """Return [(stem, display_name, description)] sorted by display name.

    Files that are not valid templates are skipped.
    """
    folder = templates_dir()
    result = []
    seen = set()
    with os.scandir(folder) as entries:
        for entry in entries:
            if not entry.name.endswith(".json"):
                continue
            stem = entry.name[:-5]
            seen.add(entry.path)
            try:
                st = entry.stat()
                key = (st.st_mtime_ns, st.st_size)
            except OSError:
                continue
            cached = _index.get(entry.path)
            if cached is None or cached[0] != key:
                try:
                    data = load(stem)
                    meta = (data["name"], data["description"])
                except Exception:  # not JSON, not a dict, a folder...: not a template
                    meta = None
                cached = _index[entry.path] = (key, meta)
            if cached[1] is not None:
                result.append((stem, *cached[1]))
    for path in [p for p in _index if p not in seen]:
        del _index[path]
    result.sort(key=lambda t: t[1].lower())
    return result


def _sanitize(data):
    """Normalise a parsed template: fixed keys, strings only, unknown keys dropped.

    Accepts plain strings as items and the pre-1.2 key "section" for "category".
    """
    items = []
    for it in data.get("items", []):
        if isinstance(it, str):
            it = {"name": it}
        items.append({
            "name": str(it.get("name", "Task")),
            "category": str(it.get("category", it.get("section", ""))),
            "note": str(it.get("note", "")),
        })
    return {
        "name": str(data.get("name", "Untitled")),
        "description": str(data.get("description", "")),
        "items": items,
    }


def load(stem):
    """Read and sanitise ``<stem>.json``. Raises on a missing or invalid file."""
    with open(os.path.join(templates_dir(), stem + ".json"), encoding="utf-8") as f:
        return _sanitize(json.load(f))


def save(name, description, items):
    """Write a template (overwriting one with the same slug); returns its stem."""
    stem = slugify(name)
    data = _sanitize({"name": name, "description": description, "items": items})
    with open(os.path.join(templates_dir(), stem + ".json"), "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2)
    return stem


def delete(stem):
    """Remove ``<stem>.json`` if it exists."""
    path = os.path.join(templates_dir(), stem + ".json")
    if os.path.exists(path):
        os.remove(path)


def apply(checklist, data, replace=True):
    """Copy a loaded template's tasks into a CHECKLIST_Data (replace or append)."""
    if replace:
        checklist.items.clear()
    for it in data["items"]:
        new = checklist.items.add()
        new.name = it["name"]
        new.category = it["category"]
        new.note = it["note"]
    checklist.template_name = data["name"]
    if replace:
        checklist.active_index = 0


def items_from_checklist(checklist):
    """The checklist's tasks as template items (the done state is not saved)."""
    return [
        {"name": it.name, "category": it.category, "note": it.note}
        for it in checklist.items
    ]


# Dynamic enum: Blender keeps raw pointers to these strings, so Python must
# keep them referenced until the next call.
_enum_cache = []


def enum_items(self, context):
    """Items callback of WindowManager.checklist_template (the Templates dropdown)."""
    _enum_cache.clear()
    try:
        for i, (stem, name, desc) in enumerate(list_templates()):
            _enum_cache.append((stem, name, desc or name, i))
    except Exception:  # unreadable folder: show the placeholder instead of failing the draw
        pass
    if not _enum_cache:
        _enum_cache.append(('NONE', "No templates", "Save a checklist as a template first", 0))
    return _enum_cache
