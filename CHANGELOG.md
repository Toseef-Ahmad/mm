# Changelog

Notable changes per release. Dates are release dates, newest first.

## Unreleased

- The landing page is a guide: one afternoon, the three places, and how a queue differs from holding work in your head, a todo list, or a calendar.
- The guide names the two losses: a gap that becomes a scroll, and an idea that arrives in the middle of the work.
- The landing example plays one moment at a time, with the sentence of that moment above the box.
- The landing page is the dark guide: the afternoon plays in the box, then the gap, the idea, the three places, the science, and the commands.

## 3.0.0 — 2026-09-09

Breaking reset: mm is a runtime box again. You add work when you want it.
Nothing appears unless you typed `mm add`. Tomorrow it is not there unless
you add it again.

### Removed

- `mm onboard`, `mm reset`, `mm init`, `mm rules *`
- `mm.toml`, `mm.rules.json`, books, habits, tracks, rotation, weekday tables
- Auto-inject of any kind (daily books, habits, weekends, streaks, rewards)
- Obsidian sync, landing `site/`, webapp
- Gates, capacity, backlog, sessions

### Kept

- Three containers: queue (FIFO), interrupt stack (LIFO), quick (batched)
- Runtime verbs: add, next/peek, done, block/unblock, suspend/resume, move,
  rm, edit, note, find, undo, status, stats, flush-quick, archive, export, log
- One file: `~/.mm/state.json`. File lock, atomic save, undo snapshots.
  Zero pip deps.
- Landing page at [mm.tafil.app](https://mm.tafil.app/) describes this version only.

No migrator. Wipe `~/.mm` yourself if you still have the old files.

## 2.1.0 — 2026-08-19

### Added

- **Habits as the primary object.** Anything you return to — a book, a course, a
  walk — is declared once in `[[habits]]` and injected when due. No re-adding by
  hand. Streaks are gap-aware: `repeat = 3` does not punish you for the two days
  the habit was never due.
- **Obsidian daily-note sync**, both directions. Tick a checkbox property in
  today's note or run `mm done`; the other side follows. New habits in either
  place grow the mapping, and mm registers the properties as checkbox types in
  the vault so Obsidian renders them correctly.
- `mm obsidian watch` for live sync, and `mm obsidian autostart on|off|status` to
  keep the watcher running in the background across logins (macOS).
- **`order` on a habit** (1 = front of the queue), with `weight` as the fallback.
  `mm habit set <name> order none` returns a habit to weight ordering.
- `mm --version`.
- The manual and the annotated starter config ship inside the package, so a
  `pip install` gets the same `mm help` and `mm init` as a git clone.
- CI across Python 3.11–3.13 on Linux and macOS, including a check that no
  third-party import ever creeps in.

### Fixed

- **`mm done` could undo itself when Obsidian sync was on.** Closing an item left
  the note property still reading `false`, which the next pull read as "the user
  unticked this" and reopened. mm now keeps a shadow of the values both sides
  last agreed on (`~/.mm/obsidian.json`), so only a genuine change counts as your
  edit.
- **Duplicate habits accumulated in the queue** across day boundaries. A day
  rollover now drops yesterday's unfinished copies, marks those due dates missed,
  and injects exactly one fresh copy per due habit.
- Unticking a habit in Obsidian no longer leaves stale points behind on the
  habit's record.
- A non-gate item moved to the top of the queue is labelled `gate-locked` instead
  of appearing selectable while the pointer silently skipped it.
- A first run with no config said "all clear — queue and stack empty", which read
  as a finished day. It now points at `mm init`.

## 2.0.0

- Modular engine: `cli` / `ops` / `model` / `config` / `state` / `paths` / `util`,
  one job each.
- TOML config (`~/.mm/mm.toml`) as the single file you edit; JSON kept as a
  compatibility fallback.
- `mm reset` no longer parks the queue by default — parking is explicit via
  `--park-gates`, because the old default felt like the tool had frozen.
- Book gates close by reading: `mm done` refuses a paged book gate with no pages
  logged today.
- Rewards pay out only on closed loops: a daily reward plus an all-gates-closed
  streak.
