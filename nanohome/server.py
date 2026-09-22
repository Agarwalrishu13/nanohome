"""Every address the page talks to.

The shape of a session: **look** at what is on this computer → **start** one
thing → **open** it → **stop** it when you are done.

Starting an app takes a few seconds and this page never waits for it: the call
returns at once and the page asks how it is getting on, which is what makes a
slow start look like progress rather than a freeze.
"""

from __future__ import annotations

import atexit
import os
import subprocess
import sys
from pathlib import Path

from . import APP_NAME, __version__, discover, guide, registry, store, supervisor
from .httpbase import App, Error, Json

WEB_DIR = Path(__file__).parent / "web"


def _state() -> dict:
    settings = store.load_settings()
    scan = discover.scan(settings)
    running = supervisor.status()
    for item in scan["apps"]:
        live = running.get(item["id"])
        item["state"] = live["state"] if live else "stopped"
        item["url"] = live["url"] if live else ""
        item["port_in_use"] = live["port"] if live else item["port"]
        item["error"] = live["error"] if live else ""
        item["own"] = live["own"] if live else False
    return {
        "app": APP_NAME,
        "version": __version__,
        "python": sys.version.split()[0],
        "apps": scan["apps"],
        "companions": scan["companions"],
        "found_count": scan["found_count"],
        "searched": scan["searched"],
        "sentence": discover.sentence(scan),
        "settings": settings,
        "questions": guide.questions(),
        "here": str(WEB_DIR.parent),
    }


def create_app() -> App:
    app = App(APP_NAME, WEB_DIR, __version__)

    @app.get("/api/health")
    def health(_request):
        return Json({"ok": True, "app": APP_NAME, "version": __version__})

    @app.get("/api/state")
    def state(_request):
        return Json(_state())

    @app.post("/api/scan")
    def scan(_request):
        """Look again, and say what changed."""
        before = {item["id"]: item["found"] for item in _state()["apps"]}
        result = _state()
        arrived = [item["name"] for item in result["apps"] if item["found"] and not before.get(item["id"])]
        result["message"] = ("Found %s. It is ready to start." % ", ".join(arrived)) if arrived \
            else result["sentence"]
        return Json(result)

    @app.post("/api/start")
    def start(request):
        body = request.json()
        app_id = str(body.get("id", ""))
        port = body.get("port")
        try:
            port = int(port) if port else None
        except (TypeError, ValueError):
            port = None
        if app_id not in registry.ids():
            return Error("There is no app called that.")
        outcome = supervisor.start(app_id, port)
        if "error" in outcome:
            return Error(outcome["error"])
        return Json(outcome)

    @app.post("/api/stop")
    def stop(request):
        app_id = str(request.json().get("id", ""))
        if app_id not in registry.ids():
            return Error("There is no app called that.")
        outcome = supervisor.stop(app_id)
        if "error" in outcome:
            return Error(outcome["error"])
        return Json(outcome)

    @app.post("/api/stop-all")
    def stop_all(_request):
        stopped = supervisor.stop_all()
        if not stopped:
            return Json({"message": "Nothing that nanoHome started is running."})
        return Json({"message": "Stopped: %s." % ", ".join(stopped), "stopped": stopped})

    @app.get("/api/logs/{app_id}")
    def logs(request):
        return Json(supervisor.logs(request.params["app_id"], since=request.q_int("since", 0)))

    @app.post("/api/forget")
    def forget(request):
        app_id = str(request.json().get("id", ""))
        supervisor.forget(app_id)
        return Json({"message": "Cleared."})

    @app.post("/api/reveal")
    def reveal(request):
        """Open an app's folder in the file manager."""
        app_id = str(request.json().get("id", ""))
        entry = registry.app(app_id)
        if not entry:
            return Error("There is no app called that.")
        result = discover.scan(store.load_settings())
        item = next((found for found in result["apps"] if found["id"] == app_id), None)
        if not item or not item["found"]:
            return Error("I have not found %s on this computer." % entry["name"])
        folder = Path(item["folder"])
        try:
            if sys.platform.startswith("win"):
                os.startfile(str(folder))                     # noqa: S606
            elif sys.platform == "darwin":
                subprocess.Popen(["open", str(folder)])
            else:
                subprocess.Popen(["xdg-open", str(folder)])
        except (OSError, AttributeError) as exc:
            return Json({"opened": False, "folder": str(folder),
                         "message": "I could not open a folder window (%s). It is at %s"
                                    % (exc, folder)})
        return Json({"opened": True, "folder": str(folder), "message": "Opened %s" % folder})

    # ------------------------------------------------------------------ guide
    @app.post("/api/guide")
    def guide_answer(request):
        body = request.json()
        return Json(guide.recommend(str(body.get("have", "")), str(body.get("want", ""))))

    # --------------------------------------------------------------- settings
    @app.post("/api/settings")
    def settings(request):
        patch = request.json()
        if not isinstance(patch, dict):
            return Error("Settings must be named values.")
        if patch.get("add_folder"):
            return Json({"settings": store.add_search_folder(str(patch["add_folder"])),
                         "message": "I will look there as well from now on."})
        if patch.get("forget_folder"):
            return Json({"settings": store.forget_folder(str(patch["forget_folder"])),
                         "message": "I will stop looking there."})
        return Json({"settings": store.save_settings(patch)})

    @app.get("/api/about")
    def about(_request):
        return Json({
            "app": APP_NAME,
            "version": __version__,
            "here": str(Path(__file__).resolve().parent.parent),
            "offline": True,
            "what_it_does": "Finds the nano apps on this computer, explains them in plain "
                            "words, and starts them without a terminal.",
            "siblings": [
                {"name": item["name"], "url": item["repo"], "what": item["tagline"]}
                for item in registry.all_apps()
            ] + [
                {"name": item["name"], "url": item["repo"], "what": item["tagline"]}
                for item in registry.companions()
            ],
        })

    # Anything nanoHome started is stopped when nanoHome closes: leaving three
    # servers running after the window is gone is how ports get mysteriously
    # occupied.
    if store.load_settings().get("stop_children_on_exit", True):
        atexit.register(supervisor.stop_all)
    return app
