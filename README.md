# mm

**Decide what's next. Never when.**

A personal CLI scheduler for people who stall by choosing. One queue, a real interrupt stack, and dominant **gates** so the day's learning cannot be skipped. No clocks, no calendar UI, no web app.

```
mm onboard     # morning: seed today's work from config
mm             # what to do right now
mm done        # finished — next thing appears
```

That is the whole ritual.

---

## Why it exists

Most productivity tools add decisions. mm removes them.

- The **interrupt stack** (LIFO) is for genuine urgency. It preempts everything, then unwinds like a call stack.
- The **main queue** (FIFO) is default work. While a **gate** is open, non-gate work is unreachable. There is no legal first move except the thing you said mattered.
- The **quick queue** is sub-1-minute trivia. It never auto-surfaces mid-task.
- **Capacity** stops the day from growing past your energy. Overflow parks in a backlog and comes back when there is room.

mm does not care *when* you work. You own the clock.

---

## Install

Python 3.11+. Zero pip dependencies.

```bash
git clone https://github.com/Toseef-Ahmad/mm.git
cd mm
./install.sh          # writes ~/bin/mm → this repo
mm init               # starter ~/.mm/mm.toml
mm rules validate
mm onboard
```

`~/bin` must be on your `PATH`. Override the data dir with `MM_HOME=~/.mm-work`.

---

## Config

One file you edit: **`~/.mm/mm.toml`**. (JSON `mm.rules.json` still loads if TOML is absent.)

TOML is the format tools actually ship — Cargo, `pyproject.toml`, ripgrep, GitHub CLI. Sections map 1:1 onto the engine. Four track types cover any learning:

| Type | What it is | Who uses it |
|---|---|---|
| `rotation` | A cycling window over a list | courses, papers, études, kata, languages |
| `weekday` | A Mon–Sun table | weekly topics, review days, rest slots (`""`) |
| `static` | The same items every day | a practice you never skip |
| `list` | Alias of `static` | — |

`dominant = true` makes a track a **gate**. `position` is `gate` (front, blocking), `front`, or `back`. `onboard.order` is the only list that gets queued — a track missing from `order` is silent.

**CS student** — courses as repeating checklists (`mm book add CS302`, no page count), plus a weekday deep-topic.

**Language learner** — a `rotation` over decks or textbooks; `count = 2` means two a day, the rest wait their turn.

**Musician / researcher** — `items = ["Bach invention 4", "etude 12", …]` on a rotation track. Same engine. No new commands.

Books that *do* have a page target still close by reading: `mm done` is refused until `mm book progress` that day. Checklist books (`pages` omitted or `0`) close with `mm done` and stay in rotation until `mm book done <id>`.

```bash
mm book add "Thinking Mathematically"     # daily checklist
mm book add "CLRS" 1292                   # page-tracked
mm book daily 4
mm book sync --prune                      # ~/.mm/books_config.json is the list
```

A books track must be `type = "rotation"` (with `source = "books"`, or just named `books`) so `mm book add` actually feeds onboard. A `static` books track ignores the book list.

Full annotated example: [`examples/mm.toml`](examples/mm.toml).

---

## Daily loop

```bash
mm onboard              # once a morning
mm                      # same as mm next
mm done
mm block "waiting on CI"
mm add -p "real fire"   # interrupt
mm add -q "email Sam"   # trivia, flushed later
mm stats                # honest numbers, no cheerleading
```

Stuck testing, or leftover gates blocking a new day?

```bash
mm reset                     # clear today's onboard lock — queue stays put
mm reset --park-gates        # also suspend leftover gates
mm resume --all              # bring parked items back
mm onboard --force           # seed anyway (testing hatch)
mm onboard --again           # re-seed today
mm rules strict off          # turn the leftover-gate lock off
```

`mm reset` does **not** park the queue. That used to be the default and it felt like the tool had frozen. Parking is now explicit.

---

## Commands

| Command | Effect |
|---|---|
| `mm init [--force]` | Write a starter `~/.mm/mm.toml` |
| `mm onboard [-n N] [--force] [--again]` | Seed today's work from config |
| `mm reset [--park-gates] [--drop-gates]` | Clear onboard lock |
| `mm` / `mm next` / `mm peek` | What to do (peek = no timer) |
| `mm done [id]` | Finish and advance |
| `mm add "task"` · `-p` · `-q` | Queue / interrupt / quick |
| `mm block ["reason"]` · `mm unblock <id> [--front]` | Stuck → move on |
| `mm suspend [id]` · `mm resume [id\|--all]` | Park / restore |
| `mm move <id> queue\|stack\|quick [--front]` | Reclassify |
| `mm rm` · `mm edit` · `mm note` · `mm find` | Fix / annotate / search |
| `mm undo` | Reverse the last mutation |
| `mm status` · `mm stats` · `mm session` · `mm archive [today]` | See state |
| `mm rules show` · `validate` · `strict on\|off` | Preview / check / lock |
| `mm book …` | `add` `progress` `done` `list` `sync [--prune]` `daily` `rm` |
| `mm capacity` · `mm backlog [--promote]` | Limits / overflow |
| `mm start` · `mm stop` · `mm log` · `mm export` | Session / dump |

---

## Architecture

Small modules, one job each — closer to a Unix tool than a framework.

```
mm/
  cli.py      argparse only
  ops.py      verbs (done, block, onboard, reset, …)
  model.py    queue physics (gates, selection, rewards)
  config.py   TOML/JSON load, compile tracks, capacity
  books.py    rotation source with optional page targets
  state.py    atomic JSON persistence + lock
  paths.py    ~/.mm layout; tests call use_home()
  util.py     time, color, file lock
```

Want a new kind of learning? Add a `type` arm in `compile_track`. Do not add a new command if a track can say it.

State the tool owns: `~/.mm/state.json`, `books.json`. You own: `mm.toml`, `books_config.json`.

---

## Tests

```bash
python3 -m unittest tests.test_mm -v
```

Stdlib only. Each test gets an isolated tmpdir. Nothing touches your real `~/.mm`.

---

## Contributing

The bar is **minimal and correct**.

1. A change should make an existing verb clearer, or make tracks express something they couldn't. New commands need a reason the track model cannot cover.
2. Keep the install at Python stdlib. No web app in this repo.
3. Tests in `tests/test_mm.py` for any behaviour change. `python3 -m unittest tests.test_mm -v` must stay green.
4. Config examples in TOML. JSON is compatibility, not the future.

Issues and PRs: [github.com/Toseef-Ahmad/mm](https://github.com/Toseef-Ahmad/mm).

---

## License

MIT
