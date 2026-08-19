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
./install.sh          # writes ~/bin/mm → this repo, and man mm
man mm                # the manual
mm init               # starter ~/.mm/mm.toml
mm rules validate
mm onboard
```

`~/bin` must be on your `PATH`. Override the data dir with `MM_HOME=~/.mm-work`.

---

## Config

One file you edit: **`~/.mm/mm.toml`**. (JSON `mm.rules.json` still loads if TOML is absent.)

### Habits

Everything you return to is the same object — a book, a walk, a course, meditation. MM reads `[[habits]]` on load and injects whatever is **due** into `queue`, `stack`, or `quick`. You do not re-add them by hand.

```toml
[[habits]]
name = "CS302"
type = "book"          # search tag — book, course, fitness, mind, …
repeat = 1             # 1 = daily; 3 = every 3rd day
enabled = 1
archived = 0
position = "queue"     # queue | stack | quick
gate = true
weight = 1
```

`repeat = 3` is a gap, not a broken streak. The two days it was never due do not reset the counter. Miss a **due** day and it is marked missed.

When the calendar day rolls over, MM drops yesterday's unfinished copies, marks those due-days **missed** (streak resets), and injects a **fresh** due set from `[[habits]]`. A habit you closed yesterday keeps its streak and still appears once today. Same habit is never queued twice.

Queue position is **`order`** (1 = front). Habits without `order` fall back to **weight** (higher first).

```bash
mm habit set Exercise order 1
```

```bash
mm habit add Walking --type fitness --repeat 1
mm habit set CS302 position stack
mm habit set CS302 repeat 3
mm habit list -t book
mm habit find fitness
mm habit miss Walking          # today didn't happen — streak resets
mm habit log CS302
```

Progress (streak, missed, last done) lives in `~/.mm/habits.json`. You own the list; mm owns the history.

### Obsidian daily notes

MM can share the same habit list with an Obsidian daily note. Toggle a property in the note or `mm done` — both sides update. New habits in either place grow the mapping.

```toml
[obsidian]
enabled = true
vault = "/path/to/Professional_notes_from_scratch"
folder = "20 Journal/Personal"
template = "80 System/Templates/Daily Journal Template.md"

[[habits]]
name = "CS302"
obsidian = "cs302"     # daily-note property; slug of the name if omitted
gate = true
weight = 4
```

`energy` stays a 1–5 mood number, not a habit. Check and uncheck both sync. Runs on `mm next` / `mm status` / `mm done`, or:

```bash
mm obsidian sync
mm obsidian watch              # live — leave running while you toggle in Obsidian
mm obsidian autostart on       # same thing in the background, across logins (macOS)
mm obsidian autostart status   # off
```

Sync only moves a box that actually moved. `~/.mm/obsidian.json` remembers the
values the two sides last agreed on, so mm can tell "you unticked this" from
"mm closed it and has not written the note yet" — without that, closing an item
would read as an uncheck and reopen itself.

`autostart` needs one grant: macOS hides Desktop and Documents from background
agents, so add the Python interpreter it names to **System Settings → Privacy &
Security → Full Disk Access**. It refuses to claim success until it sees the
watcher running; until then `mm obsidian watch` in a terminal works as-is.

Tracks (`rotation` / `weekday` / `static`) still compile on `mm onboard` if you want them. Habits do not need onboard — `mm` / `mm next` injects due ones.

Full annotated example: [`mm/data/mm.toml`](mm/data/mm.toml) — this is exactly what `mm init` writes.

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
| `mm habit …` | `add` `set` `list [-t type]` `find` `log` `miss` `rm` |
| `mm obsidian sync` · `watch` · `autostart on\|off\|status` | Pull/push today's daily-note habit properties; `watch` is live, `autostart` runs it in the background |
| `mm book …` | `add` `progress` `done` `list` `sync [--prune]` `daily` `rm` (paged books; habits cover daily checklists) |
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
  habits.py   repeating items: due/miss/streak, inject into queue|stack|quick
  obsidian.py daily-note frontmatter ↔ habits
  books.py    rotation source with optional page targets
  state.py    atomic JSON persistence + lock
  paths.py    ~/.mm layout; tests call use_home()
  util.py     time, color, file lock
```

Want a new kind of learning? Add a habit. Do not add a new command if `type` + `repeat` + `position` can say it.

State the tool owns: `~/.mm/state.json`, `habits.json`, `books.json`. You own: `mm.toml`, `books_config.json`.

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
