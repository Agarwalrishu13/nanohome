"""Tests for nanoHome.

The interesting ones start *real programs* and watch them come up: a made-up
app that behaves like the others, put in a temporary folder, found by the same
search that looks at your computer, started, health-checked and stopped. If
that works, the real apps work.

Nothing in here starts the real nano apps, and nothing binds a port that is
already in use.
"""

import json
import os
import shutil
import socket
import sys
import tempfile
import threading
import time
import unittest
import urllib.error
import urllib.request
from pathlib import Path

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

_TMP = tempfile.mkdtemp(prefix="nanohome-tests-")
os.environ["NANOHOME_DATA"] = _TMP

from nanohome import discover, guide, registry, store, supervisor  # noqa: E402
from nanohome.httpbase import free_port  # noqa: E402
from nanohome.server import create_app  # noqa: E402

# A tiny app that behaves like a nano app: it takes --port and --no-browser,
# answers /api/health with its own name, and stops when it is asked to.
FAKE_APP = '''\
import argparse, json, sys
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

NAME = APP_NAME_ONLY


class Handler(BaseHTTPRequestHandler):
    def log_message(self, fmt, *args):
        sys.stderr.write("fake app: " + (fmt % args) + "\\n")

    def do_GET(self):
        if self.path != "/api/health":
            self.send_error(404)
            return
        body = json.dumps({"ok": True, "app": NAME, "version": "9.9"}).encode()
        self.send_response(200)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)


def main(argv=None):
    parser = argparse.ArgumentParser()
    parser.add_argument("--port", type=int, default=8700)
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--no-browser", action="store_true")
    parser.add_argument("command", nargs="?", default="run")
    args = parser.parse_args(argv)
    sys.stderr.write("fake app listening on %d\\n" % args.port)
    ThreadingHTTPServer((args.host, args.port), Handler).serve_forever()


if __name__ == "__main__":
    main()
'''

# An app that falls over immediately, the way a broken one does.
BROKEN_APP = '''\
import argparse, sys


def main(argv=None):
    parser = argparse.ArgumentParser()
    parser.add_argument("--port", type=int, default=8700)
    parser.add_argument("--no-browser", action="store_true")
    parser.add_argument("command", nargs="?", default="run")
    args = parser.parse_args(argv)
    sys.stderr.write("Traceback (most recent call last):\\n")
    sys.stderr.write("OSError: [Errno 98] Address already in use\\n")
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
'''


def make_app_tree(root: Path, name: str, package: str, source: str = FAKE_APP) -> Path:
    """A folder laid out exactly like a real nano app."""
    folder = root / name
    (folder / package).mkdir(parents=True, exist_ok=True)
    (folder / package / "__init__.py").write_text('"""a made-up app for testing."""\n', encoding="utf-8")
    (folder / package / "__main__.py").write_text(
        source.replace("APP_NAME_ONLY", repr(name.title().replace(" ", ""))), encoding="utf-8")
    (folder / "start.py").write_text(
        "import os, sys\n"
        "sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))\n"
        "from %s.__main__ import main\n" % package
        + "if __name__ == '__main__':\n    raise SystemExit(main() or 0)\n",
        encoding="utf-8")
    return folder


def wait_for(check, seconds: float = 30):
    deadline = time.time() + seconds
    while time.time() < deadline:
        value = check()
        if value:
            return value
        time.sleep(0.25)
    return None


# ==========================================================================
# The catalogue
# ==========================================================================
class TestRegistry(unittest.TestCase):
    def test_every_app_is_finished(self):
        for entry in registry.all_apps():
            with self.subTest(app=entry["id"]):
                for key in ("id", "name", "emoji", "tagline", "what", "you_can", "port",
                            "package", "repo"):
                    self.assertIn(key, entry)
                self.assertTrue(entry["you_can"], "say what it is for")
                self.assertTrue(entry["repo"].startswith("https://github.com/"))

    def test_ids_and_ports_do_not_collide(self):
        ids = registry.ids()
        self.assertEqual(len(ids), len(set(ids)))
        ports = [entry["port"] for entry in registry.all_apps()]
        self.assertEqual(len(ports), len(set(ports)), "two apps must not want the same port")

    def test_the_fake_apps_in_the_tests_are_not_in_the_catalogue(self):
        self.assertNotIn("fakeapp", registry.ids())

    def test_the_command_is_the_same_for_every_app(self):
        for entry in registry.all_apps():
            with self.subTest(app=entry["id"]):
                argv = registry.launch_argv(Path("."), entry["id"], entry["port"], True)
                self.assertEqual(argv[1], "start.py")
                self.assertEqual(argv[-3:], ["--port", str(entry["port"]), "--no-browser"])

    def test_an_app_without_start_py_is_run_as_a_module(self):
        argv = registry.launch_argv(Path("."), "nanolearn", 8761, False)
        self.assertEqual(argv[1:3], ["-m", "nanolearn"])

    def test_the_projects_without_a_window_are_listed_too(self):
        names = [item["name"] for item in registry.companions()]
        self.assertIn("nanoBrain", names)
        self.assertIn("nanollama.c", names)

    def test_asking_for_an_app_that_does_not_exist(self):
        self.assertIsNone(registry.app("nothing-like-this"))


# ==========================================================================
# Finding them
# ==========================================================================
class TestDiscovery(unittest.TestCase):
    def setUp(self):
        self.root = Path(tempfile.mkdtemp(prefix="nanohome-find-"))

    def tearDown(self):
        shutil.rmtree(self.root, ignore_errors=True)

    def test_it_finds_an_app_in_a_folder(self):
        make_app_tree(self.root, "nanolearn", "nanolearn")
        found = discover.look_in([self.root])
        self.assertIn("nanolearn", found)
        self.assertEqual(found["nanolearn"].name, "nanolearn")

    def test_it_finds_apps_kept_in_the_same_folder_as_each_other(self):
        make_app_tree(self.root, "nanolaama", "nanolaama")
        make_app_tree(self.root, "nanosay", "nanosay")
        found = discover.look_in([self.root])
        self.assertEqual(sorted(found), ["nanolaama", "nanosay"])

    def test_it_finds_one_nested_a_few_folders_deep(self):
        deeper = self.root / "Projects" / "2026" / "experiments"
        deeper.mkdir(parents=True)
        make_app_tree(deeper, "nanodoc", "nanodoc")
        found = discover.look_in([self.root])
        self.assertIn("nanodoc", found)

    def test_it_does_not_descend_into_the_heavy_corners_of_a_disk(self):
        buried = self.root / "node_modules" / "deep" / "deeper"
        buried.mkdir(parents=True)
        make_app_tree(buried, "nanodesk", "nanodesk")
        found = discover.look_in([self.root])
        self.assertNotIn("nanodesk", found, "node_modules must never be searched")

    def test_a_folder_with_the_name_but_no_app_is_not_an_app(self):
        (self.root / "nanowrap").mkdir()
        self.assertEqual(discover.look_in([self.root]), {})

    def test_it_says_which_folders_it_looked_in(self):
        settings = {"search_folders": [str(self.root)]}
        result = discover.scan(settings)
        self.assertIn(str(self.root), result["searched"])
        roots = [Path(item).resolve() for item in discover.candidate_roots(settings)]
        self.assertIn(self.root.resolve(), roots,
                      "the folder I added must be one of the places searched")
        self.assertTrue(discover.sentence(result))

    def test_a_half_downloaded_app_is_reported_as_incomplete(self):
        """A folder with the right name but no package inside is not an app."""
        folder = self.root / "nanowrap"
        (folder / "nanowrap").mkdir(parents=True)
        self.assertEqual(discover.look_in([self.root]), {})

        # An app without start.py can still be run as a module, so nothing is
        # missing — the launcher handles both shapes.
        complete = make_app_tree(self.root, "nanosay", "nanosay")
        (complete / "start.py").unlink()
        self.assertEqual(discover._missing_pieces(complete, "nanosay"), [])

        # With neither start.py nor a package, there is nothing to start.
        shutil.rmtree(complete / "nanosay")
        (complete / "start.py").write_text("#", encoding="utf-8")
        missing = discover._missing_pieces(complete, "nanosay")
        self.assertIn("nanosay/__init__.py", missing)

    def test_it_reports_what_it_found_and_what_it_did_not(self):
        make_app_tree(self.root, "nanolaama", "nanolaama")
        result = discover.scan({"search_folders": [str(self.root)]})
        item = next(entry for entry in result["apps"] if entry["id"] == "nanolaama")
        self.assertTrue(item["found"])
        self.assertTrue(item["folder"].endswith("nanolaama"))
        self.assertEqual(len(result["apps"]), len(registry.all_apps()),
                         "every known app gets a card, found or not")
        self.assertGreaterEqual(result["found_count"], 1)
        self.assertIn("nano app", discover.sentence(result))

    def test_it_reports_nothing_found_when_nothing_is_there(self):
        empty = Path(tempfile.mkdtemp(prefix="nanohome-empty-"))
        try:
            found = discover.look_in([empty])
            self.assertEqual(found, {})
        finally:
            shutil.rmtree(empty, ignore_errors=True)
        result = {"found_count": 0, "apps": []}
        self.assertIn("did not find", discover.sentence(result))

    def test_the_obvious_places_are_sensible(self):
        roots = discover.obvious_roots()
        self.assertTrue(roots)
        self.assertIn(Path.home() / "Desktop" if (Path.home() / "Desktop").is_dir() else roots[0], roots)


# ==========================================================================
# The two questions
# ==========================================================================
class TestGuide(unittest.TestCase):
    def test_every_combination_of_answers_gives_a_real_app(self):
        for question in guide.questions():
            for option in question["options"]:
                for other in guide.questions()[0]["options"]:
                    answers = {"have": option["value"], "want": other["value"]}
                    with self.subTest(**answers):
                        answer = guide.recommend(answers["have"], answers["want"])
                        self.assertIn(answer["app_id"], registry.ids())
                        self.assertTrue(answer["why"])
                        self.assertEqual(answer["name"], registry.app(answer["app_id"])["name"])

    def test_a_spreadsheet_gets_nanolearn(self):
        answer = guide.recommend("spreadsheet", "understand")
        self.assertEqual(answer["app_id"], "nanolearn")
        self.assertIn("spreadsheet", answer["why"].lower())

    def test_a_document_to_listen_to_gets_nanosay(self):
        self.assertEqual(guide.recommend("document", "listen")["app_id"], "nanosay")

    def test_making_something_gets_nonoforge(self):
        self.assertEqual(guide.recommend("nothing", "make")["app_id"], "nonoforge")

    def test_nonsense_answers_still_help(self):
        answer = guide.recommend("a potato", "sing to me")
        self.assertIn(answer["app_id"], registry.ids())
        self.assertTrue(answer["why"])

    def test_the_questions_are_answerable(self):
        for question in guide.questions():
            with self.subTest(question=question["name"]):
                self.assertGreaterEqual(len(question["options"]), 2)
                for option in question["options"]:
                    self.assertTrue(option["label"])


# ==========================================================================
# Starting, watching and stopping, for real
# ==========================================================================
class TestSupervisor(unittest.TestCase):
    def setUp(self):
        self.root = Path(tempfile.mkdtemp(prefix="nanohome-run-"))
        self.port = free_port(8790)
        registry.APPS = registry.APPS        # untouched; the fake app is registered below
        self.added = []

    def tearDown(self):
        supervisor.stop_all()
        for app_id in self.added:
            registry._BY_ID.pop(app_id, None)
        shutil.rmtree(self.root, ignore_errors=True)

    def register(self, app_id: str, folder: Path):
        """Add a made-up app to the catalogue for the length of one test."""
        entry = {
            "id": app_id, "name": app_id.title(), "emoji": "🧪",
            "tagline": "a made-up app", "what": "for testing",
            "you_can": ["be started"], "port": self.port, "package": app_id,
            "repo": "https://github.com/Agarwalrishu13/nanohome",
        }
        registry.APPS = (*registry.APPS, entry)
        registry._BY_ID[app_id] = entry
        self.added.append(app_id)
        # Discovery finds it through the settings, exactly like a real one.
        store.save_settings({"search_folders": [str(self.root)]})
        return entry

    def test_it_starts_a_real_app_and_waits_until_it_answers(self):
        folder = make_app_tree(self.root, "fakeapp", "fakeapp")
        self.register("fakeapp", folder)
        outcome = supervisor.start("fakeapp")
        self.assertNotIn("error", outcome, outcome)
        self.assertEqual(outcome["state"], "starting")

        ready = wait_for(lambda: supervisor.status("fakeapp")
                         if supervisor.status("fakeapp")["state"] == "running" else None)
        self.assertIsNotNone(ready, "the app never became ready: %s" % supervisor.logs("fakeapp"))
        self.assertEqual(ready["url"], "http://127.0.0.1:%d/api/health" % ready["port"])

        # The app really is answering over HTTP.
        with urllib.request.urlopen(ready["url"], timeout=5) as response:
            payload = json.loads(response.read().decode("utf-8"))
        self.assertTrue(payload["ok"])
        self.assertIn("Fakeapp", payload["app"])

        stopped = supervisor.stop("fakeapp")
        self.assertIn("stopped", stopped["message"])
        time.sleep(0.6)
        self.assertFalse(supervisor.port_is_busy(ready["port"]), "the port should be free again")

    def test_an_app_that_falls_over_is_explained_in_words(self):
        folder = make_app_tree(self.root, "brokenapp", "brokenapp", source=BROKEN_APP)
        self.register("brokenapp", folder)
        supervisor.start("brokenapp")
        failed = wait_for(lambda: supervisor.status("brokenapp")
                          if supervisor.status("brokenapp")["state"] == "failed" else None)
        self.assertIsNotNone(failed, "it should have failed")
        self.assertIn("port", failed["error"].lower())
        self.assertNotIn("Traceback", failed["error"])

    def test_it_will_not_start_something_it_cannot_find(self):
        outcome = supervisor.start("nanobrain")     # real id, never on a test machine
        self.assertIn("error", outcome)

    def test_an_app_it_did_not_start_is_left_alone(self):
        """A server somebody else started must not be killed by nanoHome."""
        folder = make_app_tree(self.root, "outsideapp", "outsideapp")
        self.register("outsideapp", folder)
        import subprocess
        port = free_port(self.port + 20)
        process = subprocess.Popen([sys.executable, "start.py", "--port", str(port), "--no-browser"],
                                   cwd=str(folder), stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        try:
            self.assertTrue(wait_for(lambda: supervisor.who_is_on(port)["answers"]))
            # nanoHome notices it is already running, and does not start a second one.
            outcome = supervisor.start("outsideapp", port)
            self.assertEqual(outcome["state"], "running")
            self.assertIn("already running", outcome["message"])
            answer = supervisor.stop("outsideapp")
            self.assertIn("left it alone", answer["message"])
            self.assertTrue(process.poll() is None, "it should still be running")
        finally:
            process.terminate()
            process.wait(timeout=10)

    def test_a_port_used_by_something_else_is_not_stolen(self):
        """On Windows, a program can bind a port another program is already
        listening on without any error — and then never see a visitor. The only
        reliable test is to ask the port whether anybody answers."""
        import http.server
        handler = type("Squatter", (http.server.BaseHTTPRequestHandler,), {
            "do_GET": lambda self: self.send_error(404),
            "log_message": lambda self, *args: None,
        })
        server = http.server.ThreadingHTTPServer(("127.0.0.1", 0), handler)
        busy_port = server.server_address[1]
        thread = threading.Thread(target=server.serve_forever, daemon=True)
        thread.start()
        try:
            self.assertTrue(supervisor.port_is_busy(busy_port))
            self.assertNotEqual(supervisor.free_port(busy_port), busy_port,
                                "a port with somebody answering on it must never be chosen")
            self.assertGreater(supervisor.free_port(busy_port), busy_port)
            # And it is not mistaken for one of our apps.
            self.assertFalse(supervisor.who_is_on(busy_port)["answers"])
        finally:
            server.shutdown()
            server.server_close()

    def test_logs_are_kept_and_can_be_read_from_a_cursor(self):
        folder = make_app_tree(self.root, "logapp", "logapp")
        self.register("logapp", folder)
        supervisor.start("logapp")
        wait_for(lambda: supervisor.status("logapp")["state"] == "running")
        first = supervisor.logs("logapp")
        self.assertTrue(first["lines"])
        self.assertIn("--port", first["lines"][0])
        again = supervisor.logs("logapp", since=first["cursor"])
        self.assertEqual(again["lines"], [])
        supervisor.stop("logapp")

    def test_the_page_sees_a_stopped_app_as_stopped(self):
        self.assertEqual(supervisor.status("nanolaama")["state"], "stopped")
        self.assertEqual(supervisor.logs("nanolaama")["lines"], [])


# ==========================================================================
# What went wrong, in words
# ==========================================================================
class TestDiagnosis(unittest.TestCase):
    def test_a_busy_port(self):
        sentence = supervisor.diagnose(["OSError: [Errno 98] Address already in use"], "nanoSay", 8766)
        self.assertIn("8766", sentence)
        self.assertIn("port", sentence.lower())

    def test_a_missing_package(self):
        sentence = supervisor.diagnose(["ModuleNotFoundError: No module named 'requests'"],
                                      "nanoLearn", 8761)
        self.assertIn("requests", sentence)

    def test_its_own_files_being_missing(self):
        sentence = supervisor.diagnose(["ModuleNotFoundError: No module named 'nanolearn'"],
                                      "nanoLearn", 8761)
        self.assertIn("could not find its own files", sentence)

    def test_python_not_being_there(self):
        sentence = supervisor.diagnose(["python is not recognized as an internal or external command"],
                                      "nanoWrap", 8765)
        self.assertIn("Python", sentence)

    def test_something_nobody_expected(self):
        sentence = supervisor.diagnose(["it went wrong in a way nobody predicted"], "nanoDoc", 8763)
        self.assertIn("nanoDoc", sentence)
        self.assertIn("went wrong in a way nobody predicted", sentence)

    def test_nothing_at_all(self):
        sentence = supervisor.diagnose([], "nanoDesk", 8782)
        self.assertIn("did not manage to start", sentence)

    def test_server_log_noise_is_not_mistaken_for_a_reason(self):
        lines = ["127.0.0.1 - - [12/Mar/2026] \"GET /api/health HTTP/1.1\" 200 -",
                 "GET /style.css 200", "real reason: the file was not found"]
        self.assertEqual(supervisor._last_interesting(lines), "real reason: the file was not found")


# ==========================================================================
# The whole app, over HTTP
# ==========================================================================
class ServerCase(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.app = create_app()
        cls.port = free_port(8797)
        cls.base = "http://127.0.0.1:%d" % cls.port
        cls.thread = threading.Thread(
            target=cls.app.serve, kwargs={"host": "127.0.0.1", "port": cls.port,
                                          "open_browser": False, "quiet": True},
            daemon=True)
        cls.thread.start()
        deadline = time.time() + 20
        while time.time() < deadline:
            try:
                with urllib.request.urlopen(cls.base + "/api/health", timeout=2) as response:
                    if json.loads(response.read().decode("utf-8")).get("ok"):
                        return
            except Exception:
                time.sleep(0.15)
        raise AssertionError("nanoHome never came up")

    @classmethod
    def tearDownClass(cls):
        cls.app.stop()

    def get(self, path):
        try:
            with urllib.request.urlopen(self.base + path, timeout=30) as response:
                return json.loads(response.read().decode("utf-8"))
        except urllib.error.HTTPError as exc:
            return json.loads(exc.read().decode("utf-8"))

    def post(self, path, payload):
        request = urllib.request.Request(
            self.base + path, data=json.dumps(payload or {}).encode("utf-8"),
            headers={"Content-Type": "application/json"}, method="POST")
        try:
            with urllib.request.urlopen(request, timeout=60) as response:
                return json.loads(response.read().decode("utf-8"))
        except urllib.error.HTTPError as exc:
            return json.loads(exc.read().decode("utf-8"))


class TestApi(ServerCase):
    def test_it_says_hello(self):
        self.assertTrue(self.get("/api/health")["ok"])

    def test_the_first_paint_has_everything(self):
        state = self.get("/api/state")
        for key in ("apps", "companions", "searched", "sentence", "questions", "python"):
            self.assertIn(key, state)
        self.assertEqual(len(state["apps"]), len(registry.all_apps()))
        for item in state["apps"]:
            self.assertIn("found", item)
            self.assertIn("state", item)
            self.assertIn("folder", item)

    def test_it_found_the_apps_that_are_really_here(self):
        """This repository sits next to nanowrap and nanosay, so those must be found."""
        state = self.get("/api/state")
        found = {item["id"] for item in state["apps"] if item["found"]}
        self.assertIn("nanowrap", found)
        self.assertIn("nanosay", found)

    def test_a_start_request_for_an_app_that_is_not_there_is_refused(self):
        answer = self.post("/api/start", {"id": "nanobrain"})
        self.assertIn("error", answer)

    def test_a_start_request_for_an_unknown_app_is_refused(self):
        answer = self.post("/api/start", {"id": "definitely-not-an-app"})
        self.assertIn("error", answer)

    def test_stopping_something_that_is_not_running_says_so(self):
        answer = self.post("/api/stop", {"id": "nanolaama"})
        self.assertIn("error", answer)

    def test_stopping_everything_when_nothing_is_running(self):
        answer = self.post("/api/stop-all", {})
        self.assertIn("Nothing", answer["message"])

    def test_logs_for_an_app_that_never_started(self):
        answer = self.get("/api/logs/nanolaama")
        self.assertEqual(answer["lines"], [])
        self.assertEqual(answer["state"], "stopped")

    def test_the_guide_answers_over_http(self):
        answer = self.post("/api/guide", {"have": "spreadsheet", "want": "understand"})
        self.assertEqual(answer["app_id"], "nanolearn")
        self.assertIn(answer["app_id"], registry.ids())

    def test_the_guide_can_be_answered_at_all(self):
        state = self.get("/api/state")
        names = [question["name"] for question in state["questions"]]
        self.assertEqual(names, ["have", "want"])

    def test_looking_again_says_what_it_found(self):
        answer = self.post("/api/scan", {})
        self.assertIn("message", answer)
        self.assertIn("apps", answer)

    def test_folders_can_be_added_and_removed(self):
        folder = tempfile.mkdtemp(prefix="nanohome-extra-")
        added = self.post("/api/settings", {"add_folder": folder})
        self.assertIn(folder, added["settings"]["search_folders"])
        removed = self.post("/api/settings", {"forget_folder": folder})
        self.assertNotIn(folder, removed["settings"]["search_folders"])

    def test_settings_are_remembered(self):
        self.post("/api/settings", {"stop_children_on_exit": False})
        self.assertFalse(self.get("/api/state")["settings"]["stop_children_on_exit"])
        self.post("/api/settings", {"stop_children_on_exit": True})

    def test_revealing_an_app_that_is_not_here_says_so(self):
        answer = self.post("/api/reveal", {"id": "nanobrain"})
        self.assertIn("error", answer)

    def test_revealing_an_unknown_app_is_refused(self):
        self.assertIn("error", self.post("/api/reveal", {"id": "nope"}))

    def test_the_about_page_lists_every_project(self):
        about = self.get("/api/about")
        self.assertTrue(about["offline"])
        names = [item["name"] for item in about["siblings"]]
        for expected in ("nanoLaama", "nanoLearn", "nanoWrap", "nanoSay", "nanoBrain"):
            self.assertIn(expected, names)


if __name__ == "__main__":
    unittest.main(verbosity=2)
