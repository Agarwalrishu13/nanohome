<div align="center">

# nanoHome

**One window for every nano app on this computer.** It finds them, explains
them, and starts them for you.

There are seven apps in this family, each in its own folder, each started a
different way. That is fine for the person who wrote them and hopeless for
everybody else. nanoHome is the missing front door: it goes looking, shows one
card per app explaining what it is *for*, and starts the one you press.

[![license](https://img.shields.io/badge/license-MIT-blue.svg)](LICENSE)
[![python](https://img.shields.io/badge/python-3.9+-58a6ff.svg)]()
[![dependencies](https://img.shields.io/badge/required%20deps-0-f0883e.svg)]()
[![tests](https://img.shields.io/badge/tests-53%20passing-3ddc97.svg)]()

</div>

---

## What this is, in one paragraph

A launcher is easy to write badly: a list of names, a button, and a mystery when
nothing happens. nanoHome is written around the three things that actually go
wrong. **It only claims an app is running when it is answering** — every nano app
answers `/api/health`, so nanoHome waits for a real reply and opens the page only
when there is a page to open. **It says what went wrong in words** — a port
already taken, a half-downloaded folder, a missing package, Python not on the
PATH all produce a sentence about what to do next instead of a traceback. And
**it only ever stops what it started** — an app you launched yourself is left
strictly alone. Plus, for anybody who cannot tell these apps apart: two questions
(*what have you got?* / *what would you like to happen?*) and one clear answer.

---

## Use it

1. Install Python if you do not have it — [python.org/downloads](https://www.python.org/downloads/).
2. Download this repo and unzip it **next to the other nano apps**.
3. **Windows:** double-click `run.bat`. **macOS / Linux:** `./run.sh`.
4. Your browser opens at `http://127.0.0.1:8764`, listing what it found.

If an app is somewhere else, add that folder on the page itself — nanoHome
remembers it and looks there from then on.

<details>
<summary>Prefer the command line? (you do not need to)</summary>

```bash
python start.py                        # start and open the browser
python -m nanohome doctor              # show which apps are on this computer
python -m nanohome --port 9000 --no-browser
```

</details>

---

## What you get

| on the page | what it does |
|---|---|
| **One card per app** | What it is called, what it is *for*, three things you could do with it, whether it is here, and where its folder is. |
| **Start / Open / Stop** | Start it, open the page once it has answered, stop it again. The app's own output is one click away under *"What it said"*. |
| **Two questions** | *"I do not know which one I need"* → two dropdowns → one app, and a paragraph explaining why that one. |
| **Add a folder** | If something was not found, tell it where to look. It also lists every folder it searched, so "I could not find it" is never a shrug. |
| **Stop everything** | One button, for when you are finished. |

### Things it does that you would not expect from a toy

- **A port is never a reason to fail.** If 8760 is taken, nanoHome picks the next
  free one and passes `--port` to the app. You are never asked about ports.
- **Windows port squatters are actually detected.** On Windows a program can
  *bind* a port another program is already listening on without any error, and
  then never receive a single visitor — the kind of bug that makes a launcher say
  "started!" and show you nothing. nanoHome tests a port by asking it a question,
  not by trying to bind it.
- **It knows the difference between "already running" and "somebody else".**
  If the app is already up, nanoHome says so and does not start a second copy. If
  a *different* program is on that port, it says which one.
- **It stops what it started.** Children are stopped when nanoHome closes (unless
  you turn that off), so three servers are not left quietly occupying three ports
  after the window is gone.
- **It is honest about what it cannot launch.** nanoBrain, nanoRL and nanollama.c
  are real and useful, and they run in a terminal. They are listed separately with
  a link, instead of being silently missing or pretending to be startable.

---

## What it does not do, honestly

- **It does not download or install the other apps.** Start with
  [nonoforge](https://github.com/Agarwalrishu13/nonoforge) if you want the app
  that *makes* things; nanoHome assumes the apps are already on the disk.
- **It looks in the obvious places, three folders deep.** Your home folder,
  Desktop, Downloads, Documents, a few common project folder names, the folder
  nanoHome itself is in — then stops. Searching an entire home directory would
  take a minute and make the page feel broken. If it did not find yours, add the
  folder; that takes five seconds and only has to be done once.
- **It cannot start the projects with no window** (nanoBrain, nanoRL,
  nanollama.c). They are not web apps, so there is nothing to open.
- **It does not understand what the apps do.** The descriptions are written by
  hand in `registry.py`, not guessed — which also means a brand-new app will not
  appear until somebody adds it there.
- **It does not keep apps running for you in the background.** Close nanoHome's
  window with the default settings and the apps it started stop too.

---

## Where your files live

```
~/.nanohome/
  settings.json    folders to search, and what it remembers between visits
```

The apps keep their own folders (`~/.nanolaama`, `~/.nanolearn` and so on);
nanoHome does not touch them.

---

## The rest of the family

| app | what it is for | nanoHome can start it |
|---|---|---|
| [nanoLaama](https://github.com/Agarwalrishu13/nanolaama) | talk to an AI on your own computer | yes |
| [nanoLearn](https://github.com/Agarwalrishu13/nanolearn) | drop a spreadsheet, get an answer machine | yes |
| [nonoForge](https://github.com/Agarwalrishu13/nonoforge) | make a whole project without coding | yes |
| [nanoDoc](https://github.com/Agarwalrishu13/nanodoc) | ask a document questions | yes |
| [nanoWrap](https://github.com/Agarwalrishu13/nanowrap) | the programs on your computer, with buttons | yes |
| [nanoSay](https://github.com/Agarwalrishu13/nanosay) | have anything read out loud | yes |
| [nanoDesk](https://github.com/Agarwalrishu13/nanodesk) | let the computer do the clicking | yes |
| [nanoBrain](https://github.com/Agarwalrishu13/nanobrain) | train a small model from scratch | no window — terminal only |
| [nanollama.c](https://github.com/Agarwalrishu13/nanollama.c) | the C engine under nanoLaama | no window — terminal only |
| [nanoRL](https://github.com/Agarwalrishu13/nanorl) | teach a model by rewarding it | no window — terminal only |

---

## Tests

```bash
python -m unittest discover tests -v
```

53 tests. The interesting ones start **real programs**: a small app is written
into a temporary folder that behaves exactly like the others — takes `--port`,
answers `/api/health` — and the tests find it with the same search that looks at
your computer, start it, wait for it to answer, read its output, check the port
is busy, stop it, and check the port is free again. There is also a broken app
that falls over on purpose, to check the explanation, and a squatter on a port
that must never be chosen. Nothing in the tests starts a real nano app.

MIT licensed. No dependencies. `python start.py` is the whole install.
