# mm

**A box you put items into. Nothing repeats.** Live page: [mm.tafil.app](https://mm.tafil.app/).

[![ci](https://github.com/Toseef-Ahmad/mm/actions/workflows/ci.yml/badge.svg)](https://github.com/Toseef-Ahmad/mm/actions/workflows/ci.yml)
[![python](https://img.shields.io/badge/python-3.11%2B-blue)](https://www.python.org/downloads/)
[![deps](https://img.shields.io/badge/dependencies-none-brightgreen)](pyproject.toml)
[![license](https://img.shields.io/badge/license-MIT-blue)](LICENSE)

A terminal queue for your attention. Put the work in the queue so you are
not holding it in your head. `mm` shows one task. If something more
important comes up, `mm add -p` stacks it; when you `mm done`, you are
back on the queue. Small nags go to quick (`mm add -q`) and do not jump
the line. A gap in the work is when a feed takes the hour: `mm` already
has the next thing. An idea during the work goes behind it with
`mm add`, and you stay on what you were doing.

If you want CS302 today, you type `mm add "CS302"`. Tomorrow it is not
there unless you add it again.

No config file. No daily seed. No habits, tracks, or gates.

```console
$ mm add "CS302"
  + queued  1  CS302

$ mm
  →  1  CS302   0m00s active

$ mm add -p "prod is down"
  ! interrupt  2  prod is down

$ mm
  →  2  prod is down   interrupt

$ mm done
  ✓ done  2  prod is down
  →  1  CS302   0m12s active
```

The interrupt unwound. The queue is exactly what you typed.

---

## Install

Python 3.11+. **Zero dependencies** — standard library only.

macOS and Linux:

```bash
git clone https://github.com/Toseef-Ahmad/mm.git
cd mm && ./install.sh    # ~/bin/mm -> this clone, plus man mm
```

Windows — Command Prompt, PowerShell, or a double-click. Three separate lines, because Windows PowerShell 5 does not accept `&&`:

```bat
git clone https://github.com/Toseef-Ahmad/mm.git
cd mm
install.cmd
```

That puts `mm` on your user PATH (`%USERPROFILE%\bin\mm.cmd`). Open a new terminal, then `mm add "CS302"`. If Python 3.11+ is missing, the installer downloads it with winget. The full manual is `mm help`.

Git Bash can use `./install.sh`. It runs the same Windows installer. A fresh machine can paste this into PowerShell:

```powershell
irm https://raw.githubusercontent.com/Toseef-Ahmad/mm/master/install.ps1 | iex
```

Or `pipx install git+https://github.com/Toseef-Ahmad/mm.git`.

State is one file: `~/.mm/state.json` (on Windows, `%USERPROFILE%\.mm\state.json`). Point it elsewhere with `MM_HOME`.
If you used an older mm, wipe `~/.mm` yourself — leftover toml/habits files
are ignored.

---

## The ritual

```bash
mm add "…"    # put work in the box
mm            # what to do right now
mm done       # finished — the next thing appears
```

That is the whole thing.

---

## Three containers

- **Queue** (FIFO) — `mm add "task"`. Default work.
- **Interrupt stack** (LIFO) — `mm add -p "fire"`. Preempts the queue, then unwinds.
- **Quick** (batched) — `mm add -q "email Sam"`. Never auto-surfaces. Flush with `mm flush-quick`.

Blocked and suspended items are skipped. Nothing is injected.

---

## Commands

| Command | Effect |
|---|---|
| `mm` / `mm next` / `mm peek` | What to do (peek = no timer) |
| `mm add "task"` · `-p` · `-q` | Queue / interrupt / quick |
| `mm done [id]` | Finish and advance |
| `mm block ["reason"]` · `mm unblock <id> [--front]` | Stuck → move on |
| `mm suspend [id]` · `mm resume [id\|--all]` | Park / restore |
| `mm move <id> queue\|stack\|quick [--front]` | Reclassify |
| `mm rm` · `mm edit` · `mm note` · `mm find` | Fix / annotate / search |
| `mm undo` | Reverse the last mutation |
| `mm status` · `mm stats` | See state |
| `mm flush-quick` | Clear the quick queue at a checkpoint |
| `mm archive [today]` · `mm export` · `mm log` | History / dump |

`man mm` (or `mm help`) is the full manual.

---

## Architecture

```
mm/
  cli.py      argparse only
  ops.py      verbs
  model.py    items + stack-then-queue selection
  state.py    atomic JSON + undo snapshots
  paths.py    ~/.mm layout; tests call use_home()
  util.py     time, color, file lock
```

One file of state. File lock. Atomic save. Undo snapshots. No pip deps.

---

## Tests

```bash
python3 -m unittest discover -s tests -v
```

Each test uses an isolated temp directory. Nothing touches your real `~/.mm`.

---

## Contributing

The bar is **minimal and correct**. See [CONTRIBUTING.md](CONTRIBUTING.md).
Changes per release: [CHANGELOG.md](CHANGELOG.md).

## License

[MIT](LICENSE)
