# mm — Universal Focus Engine

A single-file, zero-dependency CLI for procrastination-prone work: **one queue**, **true interrupts**, **dominant gates**, and a **capacity governor** so your day cannot grow past your energy.

Philosophy: remove daily decisions, don't add daily decisions. `mm next` always answers *what to do now*.

## Install

Requires Python 3 only — no pip packages.

```bash
git clone https://github.com/Toseef-Ahmad/mm.git
mkdir -p ~/bin ~/.mm
cp mm/mm.py ~/bin/mm
chmod +x ~/bin/mm
```

Add `~/bin` to your PATH if needed:

```bash
echo 'export PATH="$HOME/bin:$PATH"' >> ~/.zshrc
source ~/.zshrc
```

Verify:

```bash
mm status
```

## First-time setup

If you have legacy config files under `~/.mm/` (`books_config.json`, `concepts_config.json`, etc.):

```bash
mm migrate          # writes ~/.mm/mm.rules.json (legacy files kept)
mm book sync        # if using book rotation
mm rules show       # preview today's plan
mm rules validate   # check schema
```

## Daily loop

```bash
mm onboard          # seed today's dominant work (once per day)
mm next             # what to do right now
mm done             # finish active item, advance
mm stats            # end-of-day numbers
```

**Precedence:** interrupt stack (`mm add -p`) → gate items (dominant tracks) → rest of queue.

**Stuck waiting on something?** `mm block "reason"` — advances immediately.

**Queue full?** Overflow parks in `mm backlog` and auto-promotes as space frees.

## Core model

```
INTERRUPT STACK (LIFO)  — real urgency only. Preempts everything.
        ↓
MAIN QUEUE (FIFO)       — default work. Gate items block the rest until done.
        ↓
QUICK QUEUE             — sub-1-min trivia. Batched at checkpoints only.
```

## Configuration

Edit `~/.mm/mm.rules.json` — one schema for all tracks (books, learning, chores, anything):

```json
{
  "onboard": { "strict_gate": true, "order": ["books", "concept", "topic"] },
  "capacity": {
    "queue": { "max": 10, "on_full": "backlog" },
    "stack": { "max": 5, "on_full": "reject" },
    "quick": { "max": 50, "on_full": "warn" }
  },
  "tracks": {
    "books": { "type": "rotation", "count": 2, "dominant": true, "position": "gate",
               "label": "📖 [{id}] {title} ({page}/{pages}p)" },
    "concept": { "type": "weekday", "dominant": true, "position": "gate",
                 "label": "🧠 {value}", "table": { "Mon": "DSA", "Tue": "Screeps" } },
    "topic": { "type": "weekday", "dominant": true, "position": "gate",
                "label": "🧭 {value}", "table": { "Mon": "Physics", "Tue": "Chemistry" } }
  }
}
```

Track types: `rotation`, `weekday`, `static`, `list`. Set `dominant: true` on any track to hard-block the day until its items are done.

## Commands

| Command | Effect |
|---|---|
| `mm onboard` | Seed today's queue from rules (idempotent per day) |
| `mm next` / `mm peek` | Show active task (peek = no timer) |
| `mm done [id]` | Finish and advance |
| `mm add "task"` | Enqueue (respects capacity) |
| `mm add -p "task"` | Push interrupt (stack cap = 5) |
| `mm add -q "task"` | Quick queue |
| `mm block ["reason"]` | Active item stuck → requeue, advance |
| `mm migrate` | Write `mm.rules.json` from legacy configs |
| `mm rules show` | Preview today's compiled plan |
| `mm rules validate` | Validate schema |
| `mm backlog [--promote]` | View/promote overflow |
| `mm capacity [queue\|stack\|quick] [max]` | Show or set limits |
| `mm status` | Full state with gate markers |
| `mm undo` | Reverse last mutation |

Book commands: `mm book add`, `progress`, `done`, `list`, `sync`, `rm`.

## Files

| Path | Purpose |
|---|---|
| `~/.mm/mm.rules.json` | **You edit** — tracks, order, dominance, capacity |
| `~/.mm/state.json` | mm manages — queue, stack, backlog, archive |
| `~/.mm/books.json` | mm manages — book progress |

Override base dir: `export MM_HOME=~/.mm-work`

## Tests

```bash
python3 -m unittest tests.test_mm -v
```

## License

MIT
