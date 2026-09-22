"""“I do not know which one I need.”

A person who does not know what these apps are cannot pick one from a list of
names. So instead of a list, nanoHome asks two small questions — *what have you
got?* and *what would you like to happen?* — and answers with one app and a
reason, in the second person.

The table below is the whole recommendation engine. It is a table rather than a
model on purpose: it can be read, argued with, and changed in a minute.
"""

from __future__ import annotations

from . import registry

# (what you have, what you want) → the app, and why it is the right one.
CHOICES = {
    ("spreadsheet", "understand"): (
        "nanolearn",
        "You have a spreadsheet and want to understand it. nanoLearn is the one: it "
        "reads your columns, guesses what you want predicted, and tells you honestly "
        "whether there is a real pattern in there or not.",
    ),
    ("spreadsheet", "answer"): (
        "nanolearn",
        "Drop the spreadsheet into nanoLearn, say which column matters, and it will "
        "answer questions about new rows — and give you a file of guesses.",
    ),
    ("spreadsheet", "ai"): (
        "nanolaama",
        "For asking an AI things in your own words, nanoLaama is the app. Keep the "
        "spreadsheet open beside it and paste in whatever you need help with.",
    ),
    ("document", "understand"): (
        "nanodoc",
        "Drag the document into nanoDoc and ask it questions in your own words. Every "
        "answer comes with the page it came from, so you can check it.",
    ),
    ("document", "listen"): (
        "nanosay",
        "nanoSay reads your document out loud using the voice already on this computer, "
        "following along sentence by sentence — and can save it as a recording.",
    ),
    ("document", "ai"): (
        "nanodoc",
        "nanoDoc is the one for documents: ask it things and it answers from the pages "
        "you gave it, rather than from the internet.",
    ),
    ("media", "understand"): (
        "nanowrap",
        "nanoWrap puts buttons on the tools already on your computer — it can tell you "
        "how big a file really is, and make copies in other formats.",
    ),
    ("media", "make"): (
        "nanowrap",
        "nanoWrap is the app for this: shrink a video so it can be sent, turn a video "
        "into an MP3, or make one PDF out of a pile of photos.",
    ),
    ("media", "listen"): (
        "nanowrap",
        "Take the sound out of the video with nanoWrap — it makes an MP3 you can play "
        "anywhere.",
    ),
    ("nothing", "make"): (
        "nonoforge",
        "You want to make something. nonoForge gives you a card to pick, asks two "
        "questions, and writes a real app into a folder — with a file explaining every "
        "part of it.",
    ),
    ("nothing", "understand"): (
        "nonoforge",
        "Start with nonoForge: make one small thing, look at the files it writes, and "
        "you will understand more than any tutorial would tell you.",
    ),
    ("nothing", "ai"): (
        "nanolaama",
        "nanoLaama is the front door: talk to an AI running on your own computer, with "
        "no account and nothing sent anywhere.",
    ),
    ("nothing", "listen"): (
        "nanosay",
        "nanoSay will read anything you paste into it, using the voice already on this "
        "computer. It is the quickest way to see one of these apps do something.",
    ),
}

QUESTIONS = (
    {
        "name": "have",
        "question": "What have you got?",
        "options": [
            {"value": "spreadsheet", "label": "A spreadsheet or a list of numbers"},
            {"value": "document", "label": "A document, a PDF or a web page"},
            {"value": "media", "label": "Photos, video or sound files"},
            {"value": "nothing", "label": "Nothing in particular"},
        ],
    },
    {
        "name": "want",
        "question": "What would you like to happen?",
        "options": [
            {"value": "understand", "label": "I want to understand it"},
            {"value": "answer", "label": "I want something that answers questions"},
            {"value": "make", "label": "I want to make something"},
            {"value": "listen", "label": "I want to listen to it"},
            {"value": "ai", "label": "I want to use an AI"},
        ],
    },
)


def recommend(have: str, want: str) -> dict:
    """One app, and the reason, in plain words.

    Unknown answers fall back to the closest thing rather than an error: a person
    who clicked the wrong thing should get help, not a complaint.
    """
    key = (str(have or "").strip().lower(), str(want or "").strip().lower())
    app_id, why = CHOICES.get(key, (None, ""))
    if app_id is None:
        # Fall back on the part of the question we do understand.
        for (has, wants), (candidate, reason) in CHOICES.items():
            if has == key[0] or wants == key[1]:
                app_id, why = candidate, reason
                break
    if app_id is None:
        app_id, why = "nanolaama", (
            "Nothing here fits exactly, so start with nanoLaama: it is the simplest of "
            "the apps and it will answer questions while you decide."
        )
    entry = registry.app(app_id) or {}
    return {
        "app_id": app_id,
        "name": entry.get("name", app_id),
        "emoji": entry.get("emoji", "✨"),
        "tagline": entry.get("tagline", ""),
        "why": why,
        "you_can": entry.get("you_can", []),
        "repo": entry.get("repo", ""),
    }


def questions() -> list:
    return [dict(question) for question in QUESTIONS]
