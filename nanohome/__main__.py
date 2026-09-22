"""Command line entry point.

Three ways in, in increasing order of nerdiness::

    python start.py               # start the home screen and open the browser
    python -m nanohome            # the same thing
    python -m nanohome doctor     # show which apps are on this computer, and stop
"""

from __future__ import annotations

import argparse
import sys

from . import APP_NAME, __version__, discover, registry, store


def _doctor() -> int:
    print()
    print("  %s %s — the apps on this computer" % (APP_NAME, __version__))
    print("  " + "-" * 62)
    print("  Python %s" % sys.version.split()[0])
    print("  Your settings live in: %s" % store.data_dir())
    print()

    result = discover.scan(store.load_settings())
    print("  %s" % discover.sentence(result))
    print()
    for item in result["apps"]:
        if item["found"]:
            detail = item["folder"]
            if item["missing_pieces"]:
                detail += "   (missing: %s)" % ", ".join(item["missing_pieces"])
            mark = "yes"
        else:
            mark, detail = "no ", "not on this computer — %s" % item["repo"]
        print("  [%s] %-11s %s" % (mark, item["name"], detail))
    print()
    print("  Projects with no window of their own (they run in a terminal):")
    for item in result["companions"]:
        print("    %-12s %s" % (item["name"], item["tagline"]))
    print()
    print("  Folders searched")
    for folder in result["searched"]:
        print("    %s" % folder)
    print()
    print("  Nothing is installed by any of this: nanoHome only starts what is already")
    print("  here, only when you press Start, and only stops what it started itself.")
    print()
    return 0


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        prog="nanohome",
        description="%s — %s" % (APP_NAME, "one window for every nano app."),
        epilog="Run it with no arguments and a browser window opens.",
    )
    parser.add_argument("command", nargs="?", default="run", choices=["run", "doctor", "version"])
    parser.add_argument("--port", type=int, default=8764, help="which port to use (default 8764)")
    parser.add_argument("--host", default="127.0.0.1", help="address to listen on (default: this computer only)")
    parser.add_argument("--no-browser", action="store_true", help="do not open a browser window")
    parser.add_argument("--version", action="store_true", help="print the version and stop")
    args = parser.parse_args(argv)

    if args.version or args.command == "version":
        print("%s %s" % (APP_NAME, __version__))
        return 0
    if args.command == "doctor":
        return _doctor()

    from .server import create_app

    app = create_app()
    try:
        app.serve(host=args.host, port=args.port, open_browser=not args.no_browser)
    except OSError as exc:
        print("\n  Could not start on %s:%d (%s).\n  Try a different port: --port 8774\n"
              % (args.host, args.port, exc))
        return 1
    finally:
        if store.load_settings().get("stop_children_on_exit", True):
            from . import supervisor
            stopped = supervisor.stop_all()
            if stopped:
                print("\n  Stopped: %s" % ", ".join(stopped))
    return 0


if __name__ == "__main__":
    sys.exit(main())
