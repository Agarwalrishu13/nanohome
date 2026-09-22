"""The nano apps nanoHome knows about, and what each one is for.

Every entry answers the question a person actually has — *what would I use this
for?* — in the same plain language the apps themselves use. The ports are only a
preference: nanoHome passes ``--port`` when it starts something, so a port being
busy is never a reason to fail.
"""

from __future__ import annotations

import sys

# The five things every nano app can be told when it starts. It is the same
# command for all of them, which is the whole reason a home screen can exist.
LAUNCH_FLAGS = ("--port", "--no-browser")

APPS = (
    {
        "id": "nanolaama",
        "name": "nanoLaama",
        "emoji": "🧠",
        "tagline": "Talk to an AI on your own computer",
        "what": "A friendly front door to a local AI. No account, no internet, no key.",
        "you_can": [
            "Ask questions and get answers written on this machine",
            "Drop in a model file and have it run offline",
            "Keep every conversation in your own folder",
        ],
        "port": 8760,
        "package": "nanolaama",
        "repo": "https://github.com/Agarwalrishu13/nanolaama",
    },
    {
        "id": "nanolearn",
        "name": "nanoLearn",
        "emoji": "📊",
        "tagline": "Drop a spreadsheet, get an answer machine",
        "what": "Machine learning as a question about your data, not a programming exercise.",
        "you_can": [
            "Find out which column predicts what you care about",
            "See honestly whether there is a real signal or just noise",
            "Get a file of guesses for rows it has never seen",
        ],
        "port": 8761,
        "package": "nanolearn",
        "repo": "https://github.com/Agarwalrishu13/nanolearn",
    },
    {
        "id": "nonoforge",
        "name": "nonoForge",
        "emoji": "🃏",
        "tagline": "Make a working project without coding",
        "what": "Pick a card, answer two questions, press one button — get a real app on your computer.",
        "you_can": [
            "Make a website, a form, or a search over your own notes",
            "Get a folder with a START-HERE file explaining every part",
            "Change it later by opening the files it made",
        ],
        "port": 8762,
        "package": "nonoforge",
        "repo": "https://github.com/Agarwalrishu13/nonoforge",
    },
    {
        "id": "nanodoc",
        "name": "nanoDoc",
        "emoji": "📚",
        "tagline": "Ask a document questions",
        "what": "Drag in a PDF or a report and ask it things in your own words.",
        "you_can": [
            "Get answers with the page they came from",
            "Search inside every document you have dropped in",
            "Read a summary of something long",
        ],
        "port": 8763,
        "package": "nanodoc",
        "repo": "https://github.com/Agarwalrishu13/nanodoc",
    },
    {
        "id": "nanowrap",
        "name": "nanoWrap",
        "emoji": "🧰",
        "tagline": "The programs on your computer, with buttons",
        "what": "Finds the powerful tools already on your machine and puts a friendly page on top of them.",
        "you_can": [
            "Shrink a video so it can be sent",
            "Turn photos into one PDF, or a video into an MP3",
            "Pack a pile of files into one zip",
        ],
        "port": 8765,
        "package": "nanowrap",
        "repo": "https://github.com/Agarwalrishu13/nanowrap",
    },
    {
        "id": "nanosay",
        "name": "nanoSay",
        "emoji": "🔊",
        "tagline": "Have anything read out loud",
        "what": "The voice already inside your computer, reading your documents, PDFs and pages.",
        "you_can": [
            "Listen to a document with the sentence highlighted",
            "Save a recording you can play anywhere",
            "Ask the local AI for a short version first",
        ],
        "port": 8766,
        "package": "nanosay",
        "repo": "https://github.com/Agarwalrishu13/nanosay",
    },
    {
        "id": "nanodesk",
        "name": "nanoDesk",
        "emoji": "🖥",
        "tagline": "Let the computer do the clicking",
        "what": "Runs the boring, repetitive things on this machine, step by step, where you can watch.",
        "you_can": [
            "Automate a chore you do every day",
            "Keep a log of what was done",
            "Stop it at any moment",
        ],
        "port": 8782,
        "package": "nanodesk",
        "repo": "https://github.com/Agarwalrishu13/nanodesk",
    },
)

# Things that are real and useful but have no window of their own.
COMPANIONS = (
    {
        "id": "nanollama.c",
        "name": "nanollama.c",
        "emoji": "⚙️",
        "tagline": "The engine under nanoLaama, written in C",
        "what": "A complete way to run a model in about 1400 lines of C with nothing to install.",
        "repo": "https://github.com/Agarwalrishu13/nanollama.c",
    },
    {
        "id": "nanobrain",
        "name": "nanoBrain",
        "emoji": "🧬",
        "tagline": "Train a small AI model from nothing",
        "what": "Builds a model from scratch on your own computer, with its own tokenizer. It runs in a "
                "terminal, takes hours, and is a project rather than a tool.",
        "repo": "https://github.com/Agarwalrishu13/nanobrain",
    },
    {
        "id": "nanorl",
        "name": "nanoRL",
        "emoji": "🎯",
        "tagline": "Teach a model by rewarding it",
        "what": "Reinforcement learning experiments, for when the basics are not the interesting part any more.",
        "repo": "https://github.com/Agarwalrishu13/nanorl",
    },
)

_BY_ID = {app["id"]: app for app in APPS}


def all_apps() -> list:
    return [dict(app) for app in APPS]


def companions() -> list:
    return [dict(item) for item in COMPANIONS]


def app(app_id: str) -> dict | None:
    found = _BY_ID.get(app_id)
    return dict(found) if found else None


def ids() -> list:
    return [app["id"] for app in APPS]


def launch_argv(folder, app_id: str, port: int, has_start_py: bool) -> list:
    """The command that starts an app, identical for every one of them.

    ``--no-browser`` matters here: the browser is nanoHome's job, so the app
    should not open a second window behind its back.
    """
    entry = app(app_id) or {}
    if has_start_py:
        base = [sys.executable, "start.py"]
    else:
        base = [sys.executable, "-m", str(entry.get("package") or app_id)]
    return [*base, "--port", str(int(port)), "--no-browser"]
