"""Checklist templates stored as JSON files in the extension's user folder."""

import json
import os
import re
import shutil

import bpy

PACKAGE = __package__
SHIPPED_DIR = os.path.join(os.path.dirname(__file__), "default_templates")
SEED_MARKER = ".seeded"


def templates_dir():
    try:
        path = bpy.utils.extension_path_user(PACKAGE, path="templates", create=True)
    except (ValueError, AttributeError):
        # Loaded as a legacy add-on / from a script: fall back to the config folder.
        path = bpy.utils.user_resource('CONFIG', path="checklist_tool_templates", create=True)
    return path


def ensure_defaults():
    """Copy shipped templates once, so users can delete defaults without them returning."""
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
    slug = re.sub(r"[^A-Za-z0-9_-]+", "_", name.strip()).strip("_").lower()
    return slug or "template"


def list_templates():
    """Return [(stem, display_name, description)] sorted by display name."""
    folder = templates_dir()
    result = []
    for fn in os.listdir(folder):
        if not fn.endswith(".json"):
            continue
        stem = fn[:-5]
        try:
            data = load(stem)
        except Exception:
            continue
        result.append((stem, data.get("name", stem), data.get("description", "")))
    result.sort(key=lambda t: t[1].lower())
    return result


def _sanitize(data):
    items = []
    for it in data.get("items", []):
        if isinstance(it, str):
            it = {"name": it}
        items.append({
            "name": str(it.get("name", "Task")),
            # "section" is the pre-1.2 key; still accepted.
            "category": str(it.get("category", it.get("section", ""))),
            "note": str(it.get("note", "")),
        })
    return {
        "name": str(data.get("name", "Untitled")),
        "description": str(data.get("description", "")),
        "items": items,
    }


def load(stem):
    with open(os.path.join(templates_dir(), stem + ".json"), encoding="utf-8") as f:
        return _sanitize(json.load(f))


def save(name, description, items):
    stem = slugify(name)
    data = _sanitize({"name": name, "description": description, "items": items})
    with open(os.path.join(templates_dir(), stem + ".json"), "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2)
    return stem


def delete(stem):
    path = os.path.join(templates_dir(), stem + ".json")
    if os.path.exists(path):
        os.remove(path)


def apply(checklist, data, replace=True):
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
    return [
        {"name": it.name, "category": it.category, "note": it.note}
        for it in checklist.items
    ]


# Dynamic enum: Blender requires the returned strings to stay referenced.
_enum_cache = []


def enum_items(self, context):
    _enum_cache.clear()
    try:
        for i, (stem, name, desc) in enumerate(list_templates()):
            _enum_cache.append((stem, name, desc or name, i))
    except Exception:
        pass
    if not _enum_cache:
        _enum_cache.append(('NONE', "No templates", "Save a checklist as a template first", 0))
    return _enum_cache
