# Changelog

Notable changes per release. Dates are release dates, newest first.

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
