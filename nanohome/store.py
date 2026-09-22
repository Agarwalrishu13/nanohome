"""Where nanoHome keeps its settings: somewhere small.

The apps themselves keep their own folders (``~/.nanolaama`` and so on). This
folder holds one thing only — where nanoHome should *look* for the apps, and
what it remembers between visits.
"""

from __future__ import annotations

import json
import os
import threading
from pathlib import Path

APP_DIR_NAME = ".nanohome"
_lock = threading.Lock()

DEFAULT_SETTINGS = {
    "search_folders": [],      # extra places to look, on top of the obvious ones
    "stop_children_on_exit": True,
    "open_browser_when_started": True,
    "known_folders": {},       # app id → the folder it was last found in
}


def data_dir() -> Path:
    """The one folder nanoHome owns. Point it elsewhere with NANOHOME_DATA."""
    override = os.environ.get("NANOHOME_DATA")
    path = Path(override) if override else Path.home() / APP_DIR_NAME
    path.mkdir(parents=True, exist_ok=True)
    return path


def _settings_path() -> Path:
    return data_dir() / "settings.json"


def load_settings() -> dict:
    with _lock:
        settings = dict(DEFAULT_SETTINGS)
        try:
            with open(_settings_path(), "r", encoding="utf-8") as handle:
                stored = json.load(handle)
            if isinstance(stored, dict):
                settings.update({key: stored[key] for key in DEFAULT_SETTINGS if key in stored})
        except (OSError, json.JSONDecodeError):
            pass
        return settings


def save_settings(patch: dict) -> dict:
    settings = load_settings()
    for key, value in (patch or {}).items():
        if key not in DEFAULT_SETTINGS:
            continue
        if key == "search_folders" and isinstance(value, list):
            settings[key] = [str(item) for item in value if str(item).strip()][:20]
        elif isinstance(DEFAULT_SETTINGS[key], bool):
            settings[key] = bool(value)
        elif key == "known_folders" and isinstance(value, dict):
            settings[key] = {str(k): str(v) for k, v in list(value.items())[:40]}
    with _lock:
        tmp = _settings_path().with_suffix(".tmp")
        tmp.write_text(json.dumps(settings, indent=2), encoding="utf-8")
        os.replace(tmp, _settings_path())
    return settings


def remember_folder(app_id: str, folder: str) -> None:
    """Keep a note of where an app was found, so the next look is quicker."""
    settings = load_settings()
    known = dict(settings.get("known_folders") or {})
    known[app_id] = str(folder)
    save_settings({"known_folders": known})


def add_search_folder(folder: str) -> dict:
    settings = load_settings()
    folders = list(settings.get("search_folders") or [])
    folder = str(Path(folder).expanduser())
    if folder and folder not in folders:
        folders.append(folder)
    return save_settings({"search_folders": folders})


def forget_folder(folder: str) -> dict:
    settings = load_settings()
    folders = [item for item in (settings.get("search_folders") or []) if item != folder]
    return save_settings({"search_folders": folders})
