"""Finding the nano apps on this computer.

There is no registry, no package manager and nothing to install, so nanoHome
does what a person would do: it looks in the obvious places. If an app is not
where it expected, it says which folders it looked in, and lets you add one.

The search is deliberately shallow (three folders deep) and skips the folders
that would make it slow — a home directory can hold a hundred thousand files,
and a home screen that takes a minute to appear is worse than one that admits it
did not look everywhere.
"""

from __future__ import annotations

import os
from pathlib import Path

from . import registry

MAX_DEPTH = 3
SKIP_NAMES = {
    "node_modules", ".git", ".svn", "__pycache__", ".venv", "venv", "env",
    "AppData", "Library", ".cache", ".npm", ".gradle", "site-packages",
    "Windows", "Program Files", "Program Files (x86)", "ProgramData",
    "$RECYCLE.BIN", "System Volume Information", ".Trash", "OneDriveTemp",
    "Applications", ".local", "dist", "build", "target", "bin", "obj",
    ".idea", ".vscode", ".next", ".cache", "Temp", "tmp",
}


def obvious_roots() -> list:
    """The places a person would look first."""
    home = Path.home()
    here = Path(__file__).resolve().parent.parent          # the nanoHome folder
    roots = [here, here.parent]
    for name in ("GITHUB", "github", "Desktop", "Downloads", "Documents", "Projects", "repos", "src"):
        candidate = home / name
        if candidate.is_dir():
            roots.append(candidate)
    # A nested layout like Desktop/GITHUB/<app> is common, so go one deeper.
    for root in list(roots):
        for name in ("GITHUB", "github", "Projects", "repos", "projects"):
            candidate = root / name
            if candidate.is_dir():
                roots.append(candidate)
    roots.append(home)

    unique: list = []
    seen = set()
    for root in roots:
        try:
            resolved = str(root.resolve())
        except OSError:
            continue
        if resolved not in seen and root.is_dir():
            seen.add(resolved)
            unique.append(root)
    return unique


def candidate_roots(settings: dict | None = None) -> list:
    """Everything to search: the obvious places, then anything you added, then
    anywhere an app was found last time."""
    settings = settings or {}
    roots = []
    seen = set()

    def add(path):
        try:
            candidate = Path(str(path)).expanduser()
        except (TypeError, ValueError):
            return
        if not candidate.is_dir():
            return
        try:
            key = str(candidate.resolve())
        except OSError:
            return
        if key not in seen:
            seen.add(key)
            roots.append(candidate)

    for known in (settings.get("known_folders") or {}).values():
        add(Path(known).parent if Path(known).name in registry.ids() else known)
    for folder in settings.get("search_folders") or []:
        add(folder)
    for root in obvious_roots():
        add(root)
    return roots


def _looks_like_the_app(folder: Path, package: str) -> bool:
    """True when this folder is the top of that app."""
    inner = folder / package
    return (inner / "__init__.py").is_file() or (inner / "server.py").is_file()


def _folders_below(root: Path, max_depth: int = MAX_DEPTH):
    """Walk down a little way, skipping the heavy corners of a disk."""
    try:
        entries = sorted(os.scandir(root), key=lambda item: item.name.lower())
    except (OSError, PermissionError):
        return
    depth = 0
    level = [root]
    while level and depth <= max_depth:
        following = []
        for folder in level:
            try:
                children = sorted(os.scandir(folder), key=lambda item: item.name.lower())
            except (OSError, PermissionError):
                continue
            for child in children:
                try:
                    if not child.is_dir(follow_symlinks=False):
                        continue
                except OSError:
                    continue
                name = child.name
                if name.startswith(".") or name in SKIP_NAMES:
                    continue
                path = Path(child.path)
                yield path
                following.append(path)
        level = following
        depth += 1


def look_in(roots: list, max_depth: int = MAX_DEPTH) -> dict:
    """Find every nano app under these folders. Returns {app_id: folder}."""
    found: dict = {}
    wanted = {app["package"]: app["id"] for app in registry.all_apps()}
    for root in roots:
        if len(found) == len(wanted):
            break
        # The root itself might be the folder of one app.
        candidates = [Path(root)] + list(_folders_below(Path(root), max_depth=max_depth))
        for folder in candidates:
            name = folder.name.lower()
            for package, app_id in wanted.items():
                if app_id in found:
                    continue
                if name != package:
                    continue
                if _looks_like_the_app(folder, package):
                    found[app_id] = folder
    return found


def scan(settings: dict | None = None) -> dict:
    """Look, and describe what was found — and what was not."""
    settings = settings if settings is not None else {}
    roots = candidate_roots(settings)
    found = look_in(roots)

    apps = []
    for entry in registry.all_apps():
        folder = found.get(entry["id"])
        item = dict(entry)
        item["found"] = folder is not None
        item["folder"] = str(folder) if folder else ""
        item["has_start_py"] = bool(folder and (folder / "start.py").is_file())
        item["missing_pieces"] = [] if not folder else _missing_pieces(folder, entry["package"])
        apps.append(item)

    return {
        "apps": apps,
        "found_count": len(found),
        "searched": [str(root) for root in roots],
        "companions": registry.companions(),
    }


def _missing_pieces(folder: Path, package: str) -> list:
    """What is in the folder — enough to say 'this looks half-downloaded'."""
    missing = []
    if not (folder / package / "__init__.py").is_file():
        missing.append("%s/__init__.py" % package)
    if not (folder / "start.py").is_file() and not (folder / package / "__main__.py").is_file():
        missing.append("start.py")
    return missing


def sentence(result: dict) -> str:
    """One honest line about what was found."""
    count = result.get("found_count", 0)
    total = len(result.get("apps", []))
    if count == 0:
        return ("I did not find any of the nano apps on this computer. Put this folder next to "
                "the others, or add the folder they are in using “Add a folder”.")
    if count == total:
        return "All %d nano apps are on this computer." % total
    return "%d of the %d nano apps are on this computer." % (count, total)
