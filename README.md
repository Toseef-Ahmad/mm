# mm

**Decide what's next. Never when.**

[![ci](https://github.com/Toseef-Ahmad/mm/actions/workflows/ci.yml/badge.svg)](https://github.com/Toseef-Ahmad/mm/actions/workflows/ci.yml)
[![python](https://img.shields.io/badge/python-3.11%2B-blue)](https://www.python.org/downloads/)
[![deps](https://img.shields.io/badge/dependencies-none-brightgreen)](pyproject.toml)
[![license](https://img.shields.io/badge/license-MIT-blue)](LICENSE)

A terminal scheduler for people who stall by choosing. One queue, a real
interrupt stack, and **gates** that make the work you said mattered the only
legal first move. No clocks, no calendar, no web app.

```console
$ mm status
  3 habit(s) due → queued

  interrupt  1/5
  →  3  Deep practice

  queue  2/14   gate open — only gate items selectable
     1  CS302
     2  Walk — one loop outside, no phone  · gate-locked

  quick  0/50
     —

$ mm add -p "prod is down"
  ! interrupt  4  prod is down

$ mm
  →  4  prod is down   interrupt

$ mm done
  ✓ done  4  prod is down
  →  3  Deep practice   interrupt
```

The interrupt was handled and the stack unwound to exactly where you were. The
walk is visible but `gate-locked` — it cannot be started until CS302 is closed.
You never chose; you just answered `mm`.

---

## Install

Python 3.11+. **Zero dependencies** — the whole thing is standard library.

```bash
pipx install git+https://github.com/Toseef-Ahmad/mm.git
mm init          # writes an annotated ~/.mm/mm.toml
mm               # what to do right now
```

Or from a clone, if you want the `mm(1)` manual and a live-editable checkout:

```bash
git clone https://github.com/Toseef-Ahmad/mm.git
cd mm && ./install.sh    # ~/bin/mm -> this clone, plus man mm
```

Data lives in `~/.mm`. Point it elsewhere with `MM_HOME=~/.mm-work`.

---

## The ritual

```bash
mm            # what to do right now
mm done       # finished — the next thing appears
```

That is the whole thing. There is no third step.

---

## Why it exists

Most productivity tools add decisions. Every list you keep is a choice you have
to make again tomorrow. mm removes the choice and keeps the mechanism:

- The **interrupt stack** (LIFO) is for genuine urgency. It preempts everything,
  then unwinds like a call stack — so an interruption cannot quietly become your
  new plan.
- The **main queue** (FIFO) is default work. While a **gate** is open, non-gate
  work is unreachable. This is the anti-procrastination mechanism: there is no
  legal first move except the thing you said mattered.
- The **quick queue** is sub-one-minute trivia. It never auto-surfaces mid-task.
- **Capacity** stops the day from growing past your energy. Overflow parks in a
  backlog and comes back when there is room.

mm does not care *when* you work. You own the clock.

### What it is not

Not a calendar, not a team tracker, not a pomodoro timer, not a service. It never
phones home, and every file it writes is plain JSON or TOML you can read and edit.

---

## Habits: the only object you configure

Anything you return to is the same thing — a book, a course, a walk, meditation.
Declare it once in `~/.mm/mm.toml` and mm injects it whenever it is **due**. You
never re-add it by hand.

```toml
[[habits]]
name = "CS302"
type = "book"          # free-form search tag
repeat = 1             # 1 = daily; 3 = every 3rd day
position = "queue"     # queue | stack | quick
gate = true            # nothing else is reachable until this closes
order = 1              # 1 = front of the queue (weight is the fallback)
```

`repeat = 3` is a gap, not a broken streak — the two days it was never due do not
reset the counter. Miss a **due** day and it is marked missed.

When the calendar day rolls over, mm drops yesterday's unfinished copies, marks
those due dates missed, and injects one fresh copy per due habit. The same habit
is never queued twice.

```bash
mm habit add Walking --type fitness --repeat 1
mm habit set CS302 order 1        # front of the queue
mm habit set CS302 order none     # back to weight ordering
mm habit set CS302 repeat 3
mm habit list -t book
mm habit miss Walking             # today didn't happen — streak resets
mm habit log CS302                # the honest history
```

You own the list in `mm.toml`; mm owns the history in `~/.mm/habits.json`.

Full annotated config: [`mm/data/mm.toml`](mm/data/mm.toml) — exactly what
`mm init` writes.

Habits cover almost everything. If you want a rotating or weekday-driven source
that compiles into the queue on `mm onboard`, `[tracks]` still exists — see
`man mm`.

---

## Obsidian daily notes, both directions

If you already track habits as checkbox properties in an Obsidian daily note,
mm can share that list instead of competing with it. Tick the box in Obsidian
and the item leaves your queue; run `mm done` and the box gets ticked. Untick it
and the habit comes back. New habits on either side grow the mapping, and mm
registers the properties as checkbox types in the vault so Obsidian renders them
as real checkboxes.

```toml
[obsidian]
enabled = true
vault = "/path/to/YourVault"
folder = "20 Journal/Personal"
template = "80 System/Templates/Daily Journal Template.md"

[[habits]]
name = "CS302"
obsidian = "cs302"     # the note property; a slug of the name if omitted
```

Sync runs on `mm`, `mm status`, and `mm done`. For live updates while you work
in Obsidian:

```bash
mm obsidian sync
mm obsidian watch              # live, in the foreground
mm obsidian autostart on       # background, across logins (macOS)
mm obsidian autostart status
```

**How it avoids fighting you.** A note property reading `false` is ambiguous: it
could mean you unticked the box, or that mm closed the item and has not written
the note yet. Guess wrong and `mm done` undoes itself. So mm keeps a shadow of
the values both sides last agreed on in `~/.mm/obsidian.json`, and only a genuine
change counts as an edit. Your ticks always win; mm never clobbers a box you just
touched.

`autostart` needs one grant: macOS hides Desktop and Documents from background
agents, so add the Python interpreter it names to **System Settings → Privacy &
Security → Full Disk Access**. It refuses to report success until it has actually
seen the watcher running — until then, `mm obsidian watch` in a terminal works
as-is.

---

## Daily loop

```bash
mm onboard              # optional: seed today from tracks
mm                      # same as mm next
mm done
mm block "waiting on CI"
mm add -p "real fire"   # interrupt
mm add -q "email Sam"   # trivia, flushed later
mm stats                # honest numbers, no cheerleading
mm undo                 # reverse the last mutation
```

Stuck testing, or leftover gates blocking a new day?

```bash
mm reset                     # clear today's onboard lock — queue stays put
mm reset --park-gates        # also suspend leftover gates
mm resume --all              # bring parked items back
mm onboard --force           # seed anyway
mm rules strict off          # turn the leftover-gate lock off
```

`mm reset` does **not** park the queue. That used to be the default and it felt
like the tool had frozen. Parking is now explicit.

---

## Commands

| Command | Effect |
|---|---|
| `mm init [--force]` | Write a starter `~/.mm/mm.toml` |
| `mm` / `mm next` / `mm peek` | What to do (peek = no timer) |
| `mm done [id]` | Finish and advance |
| `mm add "task"` · `-p` · `-q` | Queue / interrupt / quick |
| `mm block ["reason"]` · `mm unblock <id> [--front]` | Stuck → move on |
| `mm suspend [id]` · `mm resume [id\|--all]` | Park / restore |
| `mm move <id> queue\|stack\|quick [--front]` | Reclassify |
| `mm rm` · `mm edit` · `mm note` · `mm find` | Fix / annotate / search |
| `mm undo` | Reverse the last mutation |
| `mm status` · `mm stats` · `mm review` · `mm session` · `mm archive [today]` | See state |
| `mm flush-quick` | Surface the quick queue at a checkpoint |
| `mm habit …` | `add` `set` `list [-t type]` `find` `log` `miss` `rm` |
| `mm obsidian sync` · `watch` · `autostart on\|off\|status` | Daily-note sync |
| `mm book …` | `add` `progress` `done` `list` `sync [--prune]` `daily` `rm` |
| `mm onboard [-n N] [--force] [--again]` · `mm reset` | Seed today from tracks |
| `mm rules show` · `validate` · `strict on\|off` | Preview / check / lock |
| `mm capacity` · `mm backlog [--promote]` | Limits / overflow |
| `mm start` · `mm stop` · `mm log` · `mm export` | Session / dump |

`man mm` (or `mm help`) is the full manual.

---

## Architecture

Small modules, one job each — closer to a Unix tool than a framework.

```
mm/
  cli.py      argparse only
  ops.py      verbs (done, block, onboard, reset, …)
  model.py    queue physics (gates, selection, rewards)
  config.py   TOML/JSON load, compile tracks, capacity
  habits.py   repeating items: due/miss/streak, injection
  obsidian.py daily-note frontmatter ↔ habits
  books.py    rotation source with optional page targets
  state.py    atomic JSON persistence + lock
  paths.py    ~/.mm layout; tests call use_home()
  util.py     time, color, file lock
```

State mm owns: `~/.mm/state.json`, `habits.json`, `books.json`, `obsidian.json`.
Yours: `mm.toml`, `books_config.json`.

Want a new kind of work? Add a habit. Do not add a command if `type` + `repeat` +
`position` + `gate` can say it.

---

## Tests

```bash
python3 -m unittest discover -s tests -v
```

Stdlib only. Each test runs against an isolated temp directory, so nothing ever
touches your real `~/.mm`.

---

## Contributing

The bar is **minimal and correct**. See [CONTRIBUTING.md](CONTRIBUTING.md) — the
short version is that a new command needs a reason the habit model cannot cover,
and behaviour changes come with a test.

Changes per release: [CHANGELOG.md](CHANGELOG.md).

## License

[MIT](LICENSE)
