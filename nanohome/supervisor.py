"""Starting the other apps, keeping an eye on them, and stopping them again.

Three things make this worth doing carefully rather than with ``os.system``:

* **Knowing when it is really ready.** Starting a program takes a moment; the
  window is not ready until it answers on its port. nanoHome waits for that
  answer, so “Open” is never a link to nothing.
* **Saying what went wrong, in words.** An app that refuses to start prints a
  traceback, and a traceback is not an explanation. The last few lines are kept
  and turned into a sentence about ends in a sentence about what to do next.
* **Stopping what it started — and nothing else.** nanoHome only ever stops
  processes it started itself, and it checks that the thing answering on a port
  really is the app it thinks it is.
"""

from __future__ import annotations

import json
import os
import re
import socket
import subprocess
import threading
import time
import urllib.error
import urllib.request
from pathlib import Path

from . import discover, registry, store

CREATE_NO_WINDOW = 0x08000000 if os.name == "nt" else 0
READY_TIMEOUT = 40          # seconds to wait for a newly started app to answer
KEEP_LOG_LINES = 400

_lock = threading.Lock()
_running: dict[str, dict] = {}


# --------------------------------------------------------------------------
# Asking a port who it is
# --------------------------------------------------------------------------
def port_is_busy(port: int) -> bool:
    """True when something on this computer answers on that port.

    Connecting is the only reliable test. On Windows, ``SO_REUSEADDR`` lets a
    program *bind* a port that somebody else is already listening on, without
    any error — the second program then sits there receiving nothing while its
    own log cheerfully says it is listening. Asking the port a question is what
    catches that.
    """
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as probe:
        probe.settimeout(0.35)
        return probe.connect_ex(("127.0.0.1", port)) == 0


def free_port(preferred: int, tries: int = 12) -> int:
    """The first free port at or after `preferred`."""
    for offset in range(tries):
        candidate = preferred + offset
        if port_is_busy(candidate):
            continue
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as probe:
            # Deliberately no SO_REUSEADDR: see port_is_busy above.
            try:
                probe.bind(("127.0.0.1", candidate))
                return candidate
            except OSError:
                continue
    return preferred


def who_is_on(port: int, timeout: float = 1.5) -> dict:
    """Ask whatever is listening on this port what it is.

    Every nano app answers ``/api/health`` with its own name, so this is how
    nanoHome knows whether a port is occupied by *our* app (already running) or
    by something else entirely (a real problem to report).
    """
    url = "http://127.0.0.1:%d/api/health" % port
    try:
        with urllib.request.urlopen(url, timeout=timeout) as response:
            payload = json.loads(response.read().decode("utf-8"))
    except (urllib.error.URLError, OSError, ValueError, json.JSONDecodeError):
        return {"answers": False, "app": "", "url": url}
    return {"answers": True, "app": str(payload.get("app", "")),
            "version": str(payload.get("version", "")), "url": url}


# --------------------------------------------------------------------------
# What happened, in words
# --------------------------------------------------------------------------
_TROUBLE = (
    (re.compile(r"address already in use|only one usage of each socket address", re.I),
     "Something else on this computer is already using port %(port)d. Close whatever it is, "
     "or start this app again — nanoHome will pick a free port."),
    (re.compile(r"modulenotfounderror|importerror", re.I),
     "It could not find something it needs. The folder may have been moved, or only partly "
     "downloaded — try downloading it again next to the other apps."),
    (re.compile(r"syntaxerror", re.I),
     "There is a mistake in the app's own code, so it cannot start. If you downloaded it, "
     "download it again — a file may have been cut short."),
    (re.compile(r"permissionerror|access is denied", re.I),
     "This computer would not let it open a file it needed. Moving the folder somewhere "
     "like your Desktop usually fixes this."),
    (re.compile(r"is not recognized as an internal or external command|python was not found", re.I),
     "Python could not be found. Install it from python.org and tick “Add python.exe to "
     "PATH”, then start nanoHome again."),
)


def diagnose(lines: list, app_name: str, port: int) -> str:
    """One sentence about why an app did not start."""
    joined = "\n".join(str(line) for line in lines[-80:])

    # A missing import is the commonest failure by far, and the answer differs
    # depending on whether the missing piece is the app itself or a package.
    missing = re.search(r"no module named '([^']+)'", joined, re.I)
    if missing:
        name = missing.group(1).split(".")[0]
        if name.lower() in {app["package"].lower() for app in registry.all_apps()}:
            return ("It could not find its own files. The folder may have been moved, or only "
                    "partly downloaded — try downloading it again next to the other apps.")
        return ("It needs a Python package that is not installed on this computer: “%s”. "
                "The app's page on GitHub says how to add it." % name)

    for pattern, sentence in _TROUBLE:
        found = pattern.search(joined)
        if not found:
            continue
        extra = found.group(1) if found.groups() else ""
        return sentence % {"port": port, "extra": extra, "app": app_name}

    tail = _last_interesting(lines)
    if tail:
        return "%s started but stopped. The last thing it said was: “%s”" % (app_name, tail)
    return "%s did not manage to start, and did not say why." % app_name


def _last_interesting(lines: list) -> str:
    """The last line that is not noise from a web server log."""
    noisy = re.compile(r"^(GET|POST|HEAD|HTTP|\s*$|[0-9]{1,3}\.[0-9]{1,3}\.[0-9]{1,3}\.[0-9]{1,3} - -)")
    keep = []
    for line in lines:
        text = str(line).rstrip()
        if not text.strip() or noisy.match(text.strip()):
            continue
        keep.append(text.strip()[:240])
    return keep[-1] if keep else ""


# --------------------------------------------------------------------------
# Starting
# --------------------------------------------------------------------------
def _collect_output(process, entry: dict) -> None:
    """Keep the last few hundred lines the app printed."""
    assert process.stdout is not None
    try:
        for line in process.stdout:
            entry["lines"].append(line.rstrip())
            del entry["lines"][:-KEEP_LOG_LINES]
    except (ValueError, OSError):
        pass
    finally:
        try:
            process.stdout.close()
        except OSError:
            pass


def start(app_id: str, port: int | None = None) -> dict:
    """Start an app and hand back straight away; readiness is watched in the
    background so the page never waits on a slow start."""
    entry = registry.app(app_id)
    if not entry:
        return {"error": "There is no app called that."}

    with _lock:
        current = _running.get(app_id)
        if current and current["state"] in ("running", "starting"):
            return {"state": current["state"], "url": current.get("url", ""),
                    "message": "%s is already running." % entry["name"]}

    folder = _folder_for(app_id)
    if not folder:
        return {"error": "I have not found %s on this computer yet. Press “Look again”, or add "
                         "the folder it is in." % entry["name"]}

    wanted = int(port or entry["port"])
    already = who_is_on(wanted)
    if already["answers"] and already["app"] == entry["name"]:
        with _lock:
            _running[app_id] = _entry(entry, folder, wanted, "running", url=already["url"],
                                      process=None, own=False)
        return {"state": "running", "url": already["url"],
                "message": "%s was already running — I did not start a second copy."
                           % entry["name"]}
    if already["answers"] and already["app"]:
        return {"error": "%s is not the app answering on port %d — %s is. Start %s on another "
                         "port, or close that one first."
                         % (entry["name"], wanted, already["app"], entry["name"])}

    chosen = free_port(wanted)
    has_start = (folder / "start.py").is_file()
    argv = registry.launch_argv(folder, app_id, chosen, has_start)

    record = _entry(entry, folder, chosen, "starting", url="", process=None, own=True)
    record["argv"] = argv
    record["lines"] = ["$ " + " ".join(argv)]
    with _lock:
        _running[app_id] = record

    environment = dict(os.environ)
    environment["NANOHOME_CHILD"] = "1"
    environment["PYTHONUNBUFFERED"] = "1"
    try:
        process = subprocess.Popen(
            argv, cwd=str(folder), stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
            stdin=subprocess.DEVNULL, text=True, bufsize=1, errors="replace",
            env=environment, creationflags=CREATE_NO_WINDOW,
        )
    except OSError as exc:
        with _lock:
            record["state"] = "failed"
            record["error"] = ("Python would not start it (%s). Is Python installed?" % exc)
        return {"error": record["error"]}

    record["process"] = process
    store.remember_folder(app_id, str(folder))
    threading.Thread(target=_collect_output, args=(process, record), daemon=True).start()
    threading.Thread(target=_watch_ready, args=(entry, record, process, chosen), daemon=True).start()
    return {"state": "starting", "port": chosen,
            "message": "Starting %s…" % entry["name"]}


def _entry(entry: dict, folder: Path, port: int, state: str, url: str, process, own: bool) -> dict:
    return {
        "id": entry["id"],
        "name": entry["name"],
        "folder": str(folder),
        "port": port,
        "url": url,
        "state": state,            # starting | running | failed | stopped
        "own": own,                # True when nanoHome started it
        "process": process,
        "lines": [],
        "error": "",
        "started": time.time(),
        "argv": [],
    }


def _watch_ready(entry: dict, record: dict, process, port: int) -> None:
    """Wait until the app answers, or until it is clear it never will."""
    deadline = time.time() + READY_TIMEOUT
    while time.time() < deadline:
        if record.get("state") != "starting":
            return
        if process.poll() is not None:
            # It exited. Say what happened, in words.
            time.sleep(0.3)                      # let the last of its output arrive
            record["state"] = "failed"
            record["error"] = diagnose(record["lines"], entry["name"], port)
            return
        answer = who_is_on(port, timeout=1.0)
        if answer["answers"] and answer["app"] == entry["name"]:
            record["state"] = "running"
            record["url"] = answer["url"]
            record["lines"].append("%s is ready at %s" % (entry["name"], answer["url"]))
            _remember(record)
            return
        time.sleep(0.4)

    if process.poll() is None:
        # Still alive but silent: it may simply be a slow starter, so say that
        # rather than calling it a failure.
        record["state"] = "running-slow"
        record["url"] = "http://127.0.0.1:%d" % port
        record["lines"].append("It is taking longer than usual to answer.")
    else:
        record["state"] = "failed"
        record["error"] = ("%s started, but did not answer within %d seconds."
                           % (entry["name"], READY_TIMEOUT))


def _remember(record: dict) -> None:
    with _lock:
        _running[record["id"]] = record


def _folder_for(app_id: str) -> Path | None:
    """Where the app is: what discovery found last time, or a fresh look."""
    settings = store.load_settings()
    known = (settings.get("known_folders") or {}).get(app_id)
    if known:
        candidate = Path(known)
        entry = registry.app(app_id) or {}
        if (candidate / str(entry.get("package")) / "__init__.py").is_file():
            return candidate
    result = discover.scan(settings)
    for item in result["apps"]:
        if item["id"] == app_id and item["found"]:
            return Path(item["folder"])
    return None


# --------------------------------------------------------------------------
# Stopping
# --------------------------------------------------------------------------
def stop(app_id: str) -> dict:
    """Stop an app — but only one nanoHome started itself."""
    with _lock:
        record = _running.get(app_id)
    if not record:
        return {"error": "That app is not running."}
    entry = registry.app(app_id) or {}
    if not record.get("own") or not record.get("process"):
        with _lock:
            _running.pop(app_id, None)
        return {"message": "%s was started outside nanoHome, so I have left it alone. "
                           "Close its window to stop it." % entry.get("name", app_id)}

    process = record["process"]
    _end(process)
    record["state"] = "stopped"
    record["url"] = ""
    record["ending"] = time.time()
    return {"message": "%s has stopped." % entry.get("name", app_id)}


def _end(process) -> None:
    """Ask it to leave, then insist."""
    if process.poll() is not None:
        return
    try:
        process.terminate()
    except OSError:
        return
    for _ in range(30):
        if process.poll() is not None:
            return
        time.sleep(0.1)
    try:
        process.kill()
    except OSError:
        pass


def stop_all() -> list:
    stopped = []
    with _lock:
        ids = [app_id for app_id, record in _running.items()
               if record.get("own") and record.get("state") in ("running", "starting", "running-slow")]
    for app_id in ids:
        outcome = stop(app_id)
        if "message" in outcome:
            stopped.append(app_id)
    return stopped


# --------------------------------------------------------------------------
# What the page asks for
# --------------------------------------------------------------------------
def status(app_id: str | None = None) -> dict:
    with _lock:
        if app_id:
            record = _running.get(app_id)
            return _public(record) if record else {"id": app_id, "state": "stopped"}
        return {key: _public(record) for key, record in _running.items()}


def _public(record: dict) -> dict:
    if not record:
        return {}
    return {
        "id": record["id"],
        "name": record["name"],
        "state": record["state"],
        "port": record["port"],
        "url": record["url"],
        "own": record["own"],
        "error": record.get("error", ""),
        "seconds": round(time.time() - record.get("started", time.time()), 1),
    }


def logs(app_id: str, since: int = 0) -> dict:
    with _lock:
        record = _running.get(app_id)
    if not record:
        return {"lines": [], "cursor": 0, "state": "stopped"}
    lines = list(record["lines"])
    start = max(0, min(int(since), len(lines)))
    return {"lines": lines[start:], "cursor": len(lines), "state": record["state"],
            "error": record.get("error", ""), "entry": _public(record)}


def forget(app_id: str) -> None:
    """Drop a finished app from the list so it stops being shown."""
    with _lock:
        record = _running.get(app_id)
        if record and record.get("state") in ("stopped", "failed"):
            _running.pop(app_id, None)
