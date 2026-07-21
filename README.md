# mm — Universal Focus Engine

A single-file, zero-dependency CLI for procrastination-prone work: **one queue**, **true interrupts**, **dominant gates**, and a **capacity governor** so your day cannot grow past your energy.

Philosophy: *remove daily decisions, don't add daily decisions.* `mm next` always answers **what to do right now** — you never sit and choose.

There is exactly one config file you edit (`~/.mm/mm.rules.json`) plus your book list. Everything else the tool manages for you.

---

## Install

Requires Python 3 only — no pip packages.

```bash
mkdir -p ~/bin ~/.mm
cp mm.py ~/bin/mm
chmod +x ~/bin/mm
```

Add `~/bin` to your PATH if needed, then reload:

```bash
echo 'export PATH="$HOME/bin:$PATH"' >> ~/.zshrc
source ~/.zshrc
mm status        # empty state = installed correctly
```

---

## The daily loop

```bash
mm onboard     # morning: seed today's gate work (once per day)
mm next        # what to do right now
mm done        # finished it — advance to the next thing
mm stats       # end of day: the honest numbers
```

That's the whole ritual. **`mm onboard` in the morning, then `mm` / `mm done` all day.** (Bare `mm` = `mm next`.)

### Rewards — paid only on closed loops

Configure a `rewards` section in `~/.mm/mm.rules.json`:

```json
"rewards": {
  "daily": "30 min guilt-free fun — EARNED, not stolen mid-task",
  "streak_milestones": { "3": "…", "7": "…", "30": "…" }
}
```

While gates remain open, `mm done` shows `gates N closed · M to go — reward unlocks at zero`. When the **last** gate of the day closes, the daily reward unlocks and the all-gates-closed **streak** advances (shown in `mm stats`). The reward never fires on partial progress — by design: partial-win dopamine ("good enough, time for YouTube") is the exact failure mode this tool exists to fight. Suspended gates don't block the day (parking is honest), but they don't count as closed either.

**Precedence** (what `mm next` hands you): interrupt stack (`mm add -p`) → gate items (today's dominant learning) → rest of the queue.

- **Stuck waiting on something (e.g. an agent run)?** `mm block "reason"` — parks it and advances immediately, so idle time auto-fills with your next task.
- **Real interrupt (meeting, fire)?** `mm add -p "..."` — preempts everything.
- **Sub-1-minute trivia?** `mm add -q "..."` — batched, never breaks your focus.

---

## Core model

```
INTERRUPT STACK (LIFO)  — real urgency only. Preempts everything.
        ↓
MAIN QUEUE (FIFO)       — default work. Gate items block the rest until done.
        ↓
QUICK QUEUE             — sub-1-min trivia. Batched at checkpoints only.
```

**The gate is the anti-procrastination mechanism.** While any dominant (gate) item is open in the queue, non-gate work is *unreachable* — there is no legal first move except your learning. And with `strict_gate: true`, `mm onboard` refuses to start a new day until yesterday's dominant work is done or consciously suspended.

---

## Configuration — one file

Edit `~/.mm/mm.rules.json`. One schema drives every automated track (books, thinking, topics, chores, anything):

```json
{
  "onboard": { "strict_gate": true, "order": ["books", "thinking", "topic"] },
  "capacity": {
    "queue": { "max": 10, "on_full": "backlog" },
    "stack": { "max": 5,  "on_full": "reject" },
    "quick": { "max": 50, "on_full": "warn" }
  },
  "tracks": {
    "books": { "type": "rotation", "count": 2, "dominant": true, "position": "gate",
               "label": "📖 [{id}] {title} ({page}/{pages}p)" },
    "thinking": { "type": "weekday", "dominant": true, "position": "gate",
                  "label": "🧠 {value}",
                  "table": { "Mon": "DSA", "Tue": "Screeps", "Wed": "Find skeleton from sentence" } },
    "topic": { "type": "weekday", "dominant": true, "position": "gate",
               "label": "🧭 {value}",
               "table": { "Mon": "Physics", "Tue": "Chemistry", "Wed": "Biology" } }
  }
}
```

- **Track types:** `rotation` (books), `weekday` (Mon–Sun table), `static` (fixed list), `list`.
- **`dominant: true`** on a track makes its items **gates** — hard-blocking the day until done.
- **`position`:** `gate` (front, blocks), `front`, or `back`.
- A weekday value may be a **single string or a list** (multiple items that day). An empty `""` value = a rest slot, silently skipped.
- **`order`** must list every track you want onboarded — a track missing from `order` is never queued.

Preview and check anytime, without changing anything:

```bash
mm rules show        # today's compiled plan
mm rules validate    # catch schema mistakes before they bite
```

---

## Books

Books have progress, so they live in their own tracked file and rotate automatically.

```bash
mm book add "CS302" 500          # add one (optionally: -g <group> to rotate together)
mm book progress 1 45            # log 45 pages read; auto-marks done at the end
mm book done 2                   # mark finished directly, no page count
mm book list                     # ▶ marks which books are in today's window
mm book rm 3
```

A book gate closes by reading, not by ticking: `mm done` on a book gate is refused
unless pages were logged (`mm book progress`) that same day. Park it honestly with
`mm suspend` instead if today isn't the day.

**Bulk-declare** your reading list in `~/.mm/books_config.json`, then reconcile:

```json
{ "daily_units": 2, "books": [ {"title": "CS302", "pages": 500}, {"title": "CS201", "pages": 500} ] }
```

```bash
mm book sync    # adds/updates from config; never touches earned progress
```

Rotation is a **stateless sliding window**: each `mm onboard` picks the first `count` not-yet-finished book units, in list order. Finish one, the window slides forward on its own — no pointer to drift.

---

## Commands

| Command | Effect |
|---|---|
| `mm onboard [-n count]` | Seed today's gate work from rules (idempotent per day) |
| `mm next` / `mm peek` | Show the active task (peek = no timer) |
| `mm done [id]` | Finish and advance |
| `mm add "task"` | Enqueue (respects capacity) |
| `mm add -p "task"` | Push interrupt (preempts everything) |
| `mm add -q "task"` | Quick queue (batched trivia) |
| `mm block ["reason"]` | Active item stuck → requeue, advance |
| `mm unblock <id> [--front]` | Clear a block |
| `mm suspend [id]` / `mm resume [id]` | Set aside cleanly / bring back |
| `mm move <id> queue\|stack\|quick [--front]` | Reclassify, keep id/history |
| `mm rm <id>` · `mm edit <id> "…"` · `mm note <id> "…"` | Fix / annotate |
| `mm find <query>` | Search text + notes everywhere |
| `mm undo` | Reverse the last mutation |
| `mm flush-quick` | Batch-process the quick queue |
| `mm status` | Full state with gate markers |
| `mm stats` / `mm review` · `mm session` · `mm archive [today]` | The numbers / timeline / done items |
| `mm export [json\|md\|csv]` · `mm log [n]` | Dump / recent events |
| `mm start [label]` · `mm stop` | Track a work stretch |
| `mm rules show` · `mm rules validate` | Preview / check config |
| `mm backlog [--promote]` | Items parked over capacity |
| `mm capacity [queue\|stack\|quick] [max]` | Show or set limits |
| `mm book …` | `add`, `progress`, `done`, `list`, `sync`, `rm` |

---

## Files

| Path | Purpose | Who edits |
|---|---|---|
| `~/.mm/mm.rules.json` | Tracks, order, dominance, capacity | **You** |
| `~/.mm/books_config.json` | Your declared reading list | **You** |
| `~/.mm/books.json` | Book progress/status | mm |
| `~/.mm/state.json` | Queue, stack, quick, backlog, archive, log | mm |

Override the base dir for a separate instance: `export MM_HOME=~/.mm-work`

---

## Design notes

- **Calm, minimal output.** Color is used only when writing to a real terminal, and is disabled by `NO_COLOR=1` or `TERM=dumb`, so piping/redirecting stays plain text.
- **Zero dependencies, plain JSON, atomic writes** (`temp + os.replace` + `fsync`) — a crash mid-write can't corrupt state. Empty/corrupt files start fresh instead of failing.
- **Advisory file lock** so two terminals can't race.
- **One source of truth.** All scheduling lives in `mm.rules.json`; there is no second, drifting copy of your weekly tables.
- **Onboard never duplicates and never leapfrogs.** Yesterday's unfinished gate item stays first; today's fresh content queues behind it.
- **No time-of-day windows, no server, no web app.** mm decides *what's next*, never *when* — you own your time.

## Tests

```bash
python3 -m unittest tests.test_mm -v
```

## License

MIT
