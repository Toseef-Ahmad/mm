#!/usr/bin/env python3
"""
mm — a personal task scheduler modeled as: Queue + Interrupt Stack + Quick-task batch.

  MAIN QUEUE (FIFO):    default work. One thing at a time, run to completion.
  INTERRUPT STACK (LIFO): genuinely higher-priority preempts. Nested interrupts
                         unwind in reverse order, like a call stack.
  QUICK QUEUE:           sub-1-minute items. Never processed reactively mid-wait —
                         only flushed in batches, so it never becomes a hidden
                         context switch.
  BLOCK:                 current item stuck -> requeue at back, move on.
  SUSPEND:                set the active item aside without finishing it; resume later.

State: ~/.mm/state.json (plain JSON, one file, git-trackable, override with $MM_STATE).

Usage:
  mm add "task"                add to main queue
  mm add -p "task"              push to interrupt stack (preempts everything)
  mm add -q "task"              add to quick queue (batched, never reactive)
  mm next                       show what to do right now (with elapsed time)
  mm peek                       glance at current/next/quick without committing (no timer start)
  mm done [id]                  finish current item (or a specific id), advance, archive it
  mm block ["reason"]           current item stuck -> requeue at back, advance
  mm unblock <id> [--front]     clear the blocked mark (stack: reactivates; queue: --front to jump)
  mm suspend [id]                set the active item aside cleanly (or a specific id)
  mm resume [id]                 bring a suspended item back (defaults to most recently suspended)
  mm move <id> queue|stack|quick [--front]   reclassify a task, keep its id/history
  mm rm <id>                    remove a specific item (typo fix, mind changed)
  mm edit <id> "new text"       correct a specific item's text
  mm note <id> "text"           attach/append a note to a task
  mm find <query>               search text and notes across queue/stack/quick/archive
  mm undo                       reverse the last mutating action (add/done/block/unblock/move/rm/edit/suspend/resume)
  mm flush-quick                batch-process quick queue (only at a checkpoint)
  mm status                     show full state with ids
  mm stats | mm review          today's numbers, facts only
  mm session                    today's timeline (added/started/blocked/unblocked/finished)
  mm archive [today]            show completed items (optionally just today's)
  mm export [json|md|csv]       dump queue+stack+quick+archive to stdout in the given format
  mm start [label]               begin a tracked work stretch
  mm stop                       end the current work stretch, log duration/interruptions/completions
  mm log [n]                    show last n log events (default 10)
  mm rules show                 print today's compiled onboard plan without changing anything
  mm rules validate             check the unified schema for errors
  mm backlog [--promote]        view items parked over capacity; --promote pulls them back in
  mm capacity [<queue|stack|quick> <max>]   show or set per-container maximums
"""
import copy
import csv
import io
import json
import os
import sys
import argparse
import tempfile
from datetime import datetime, timezone, date, timedelta

try:
    import fcntl
    HAVE_FCNTL = True
except ImportError:
    HAVE_FCNTL = False  # non-POSIX fallback; save/load just won't lock

STATE_DIR = os.environ.get("MM_HOME", os.path.expanduser("~/.mm"))
STATE_PATH = os.environ.get("MM_STATE", os.path.join(STATE_DIR, "state.json"))
LOCK_PATH = STATE_PATH + ".lock"
BOOKS_PATH = os.environ.get("MM_BOOKS", os.path.join(STATE_DIR, "books.json"))
BOOKS_CONFIG_PATH = os.environ.get("MM_BOOKS_CONFIG", os.path.join(STATE_DIR, "books_config.json"))
RULES_PATH = os.environ.get("MM_RULES", os.path.join(STATE_DIR, "mm.rules.json"))

EMPTY_BOOKS = {"books": [], "daily_units": 2, "next_id": 1}

EMPTY_STATE = {
    "queue": [], "stack": [], "quick": [], "backlog": [], "log": [], "next_id": 1, "active": None,
    "archive": [], "sessions": [], "_snapshots": [], "onboarded_date": None,
    "gate_days": [],  # dates on which ALL gate work was closed — feeds the reward streak
}


def default_capacity():
    """Per-container limits. `max` is the ceiling of open items; `on_full`
    decides what happens to the next arrival: 'backlog' parks it aside (nothing
    lost), 'reject' refuses it outright, 'warn' allows it but flags the bloat."""
    return {
        "queue": {"max": 10, "on_full": "backlog"},
        "stack": {"max": 5, "on_full": "reject"},
        "quick": {"max": 50, "on_full": "warn"},
    }

MUTATORS_LABEL = {
    "cmd_add": "add", "cmd_done": "done", "cmd_block": "block", "cmd_unblock": "unblock",
    "cmd_move": "move", "cmd_rm": "rm", "cmd_edit": "edit", "cmd_note": "note",
    "cmd_suspend": "suspend", "cmd_resume": "resume", "cmd_flush_quick": "flush-quick",
}


# ---------- minimal output styling ----------
# Color only when writing to a real terminal, and never when NO_COLOR is set —
# so piping, redirecting, and tests stay plain text.
_COLOR = sys.stdout.isatty() and not os.environ.get("NO_COLOR") and os.environ.get("TERM") != "dumb"


def _paint(s, code):
    return f"\033[{code}m{s}\033[0m" if _COLOR else s


def dim(s):      return _paint(s, "2")
def bold(s):     return _paint(s, "1")
def accent(s):   return _paint(s, "36")   # cyan — the active item
def good(s):     return _paint(s, "32")   # green — done
def warn(s):     return _paint(s, "33")   # yellow — interrupt / caution


def now_iso():
    return datetime.now(timezone.utc).astimezone().isoformat(timespec="seconds")


def today_str():
    return datetime.now(timezone.utc).astimezone().date().isoformat()


def ensure_dir():
    os.makedirs(STATE_DIR, exist_ok=True)


class Lock:
    """Advisory file lock so two terminals never corrupt state.json together."""
    def __enter__(self):
        ensure_dir()
        self.fh = open(LOCK_PATH, "w")
        if HAVE_FCNTL:
            fcntl.flock(self.fh, fcntl.LOCK_EX)
        return self

    def __exit__(self, *exc):
        if HAVE_FCNTL:
            fcntl.flock(self.fh, fcntl.LOCK_UN)
        self.fh.close()


def load():
    ensure_dir()
    if not os.path.exists(STATE_PATH):
        return copy.deepcopy(EMPTY_STATE)
    # An empty file isn't corruption worth preserving — just start fresh, quietly.
    if os.path.getsize(STATE_PATH) == 0:
        return copy.deepcopy(EMPTY_STATE)
    try:
        with open(STATE_PATH) as f:
            data = json.load(f)
        for k, v in EMPTY_STATE.items():
            data.setdefault(k, v if not isinstance(v, (list, dict)) else type(v)())
        return data
    except (json.JSONDecodeError, OSError) as e:
        backup = STATE_PATH + f".corrupt-{int(datetime.now().timestamp())}"
        try:
            os.replace(STATE_PATH, backup)
        except OSError:
            pass
        print(f"⚠️  State file was corrupted ({e}). Backed up to {backup}. Starting fresh.", file=sys.stderr)
        return copy.deepcopy(EMPTY_STATE)


def save(state):
    ensure_dir()
    fd, tmp = tempfile.mkstemp(dir=STATE_DIR, prefix=".state-", suffix=".tmp")
    try:
        with os.fdopen(fd, "w") as f:
            json.dump(state, f, indent=2)
            f.flush()
            os.fsync(f.fileno())
        os.replace(tmp, STATE_PATH)  # atomic on POSIX
    finally:
        if os.path.exists(tmp):
            os.remove(tmp)


def load_books():
    ensure_dir()
    if not os.path.exists(BOOKS_PATH):
        return copy.deepcopy(EMPTY_BOOKS)
    try:
        with open(BOOKS_PATH) as f:
            data = json.load(f)
        for k, v in EMPTY_BOOKS.items():
            data.setdefault(k, v if not isinstance(v, (list, dict)) else type(v)())
        return data
    except (json.JSONDecodeError, OSError) as e:
        backup = BOOKS_PATH + f".corrupt-{int(datetime.now().timestamp())}"
        try:
            os.replace(BOOKS_PATH, backup)
        except OSError:
            pass
        print(f"⚠️  Books file was corrupted ({e}). Backed up to {backup}. Starting fresh.", file=sys.stderr)
        return copy.deepcopy(EMPTY_BOOKS)


def save_books(data):
    ensure_dir()
    fd, tmp = tempfile.mkstemp(dir=STATE_DIR, prefix=".books-", suffix=".tmp")
    try:
        with os.fdopen(fd, "w") as f:
            json.dump(data, f, indent=2)
            f.flush()
            os.fsync(f.fileno())
        os.replace(tmp, BOOKS_PATH)
    finally:
        if os.path.exists(tmp):
            os.remove(tmp)


def find_book(data, book_id):
    return next((b for b in data["books"] if b["id"] == book_id), None)


def build_units(books):
    """Group consecutive-in-list books sharing a 'group' into one rotation unit.
    Ungrouped books are their own unit. Order follows insertion order."""
    units, seen_groups = [], set()
    for b in books:
        grp = b.get("group")
        if grp:
            if grp in seen_groups:
                continue
            seen_groups.add(grp)
            units.append([x for x in books if x.get("group") == grp])
        else:
            units.append([b])
    return units


def pick_books_for_today(data, count=None):
    """Stateless sliding window: take the first `count` units (in stable list
    order) that aren't fully done yet. No pointer, no index math — an
    unfinished unit simply stays in the window until it's done, then the
    window slides forward on its own. `count` defaults to data['daily_units']."""
    if count is None:
        count = data.get("daily_units", 2)
    units = build_units(data["books"])
    not_done_units = [u for u in units if any(b["status"] != "done" for b in u)]
    picked_units = not_done_units[:count]
    return [b for u in picked_units for b in u if b["status"] != "done"]


def log_event(state, msg):
    state["log"].append({"ts": now_iso(), "event": msg})
    state["log"] = state["log"][-1000:]  # keep it bounded


def snapshot(state):
    """Push a pre-mutation copy of state (minus snapshot history itself) for mm undo."""
    snap = copy.deepcopy({k: v for k, v in state.items() if k != "_snapshots"})
    state["_snapshots"].append(snap)
    state["_snapshots"] = state["_snapshots"][-15:]


def new_item(state, text, gate=False, dominant=False, track=None, rule_id=None, ref=None, group=None):
    item = {"id": state["next_id"], "text": text, "added_at": now_iso()}
    if dominant:
        gate = True  # dominant work is, by definition, a gate
    if gate:
        item["gate"] = True
    if dominant:
        item["dominant"] = True
    if track:
        item["track"] = track
    if rule_id:
        item["rule_id"] = rule_id
    if ref is not None:
        item["ref"] = ref
    if group:
        item["group"] = group
    state["next_id"] += 1
    return item


def is_gate_item(item):
    """A gate item blocks everything behind it until it's done. Items are
    classified purely by their explicit `gate` field, set at creation time."""
    return bool(item.get("gate"))


def has_open_gate(state):
    """True if any gate item is still sitting in the queue and hasn't been
    consciously set aside. A suspended gate item stops gating (you chose to park
    it); a still-active or blocked one keeps the day gated."""
    return any(is_gate_item(it) and not it.get("suspended") for it in state["queue"])


# ---------- reward on closed loops ----------
# The reward fires ONLY when every gate is genuinely closed — never on partial
# progress. This is deliberate: partial-win dopamine ("good enough, time for
# YouTube") is the failure mode this tool exists to fight. The reward moves the
# payout to the far side of the finish line.

def gate_progress_today(state):
    """(closed_today, still_open). Suspended gates don't count as open — parking
    is an honest choice, but they don't count as closed either, so a day with
    suspensions still shows what was truly finished."""
    today = today_str()
    closed = sum(1 for t in state["archive"]
                 if is_gate_item(t) and t.get("done_at", "").startswith(today))
    open_ = sum(1 for it in state["queue"]
                if is_gate_item(it) and not it.get("suspended"))
    return closed, open_


def streak_length(days, upto):
    """Consecutive run of dates in `days` ending at `upto` (a date isoformat)."""
    dayset = set(days)
    d = date.fromisoformat(upto)
    n = 0
    while d.isoformat() in dayset:
        n += 1
        d -= timedelta(days=1)
    return n


def reward_check(state):
    """Called after a gate item closes. Prints progress while gates remain;
    prints the earned reward + streak when the last gate of the day closes."""
    closed, open_ = gate_progress_today(state)
    if closed == 0:
        return
    if open_:
        print(f"  {dim('gates')} {good(str(closed))} {dim('closed ·')} {warn(str(open_))} {dim('to go — reward unlocks at zero')}")
        return
    days = set(state.get("gate_days", []))
    days.add(today_str())
    state["gate_days"] = sorted(days)[-400:]
    streak = streak_length(state["gate_days"], today_str())
    log_event(state, f"ALL GATES CLOSED — streak {streak} day(s)")
    rewards = load_rules().get("rewards", {})
    print(f"\n  {good('★ ALL GATES CLOSED')} — {bold('day earned.')}")
    if rewards.get("daily"):
        print(f"  {bold('reward unlocked:')} {rewards['daily']}")
    print(f"  {dim('streak:')} {bold(str(streak))} {dim('day(s) of fully closed loops')}")
    milestone = rewards.get("streak_milestones", {}).get(str(streak))
    if milestone:
        print(f"  {warn('milestone —')} {milestone}")


def find_item(state, item_id, containers=("stack", "queue", "quick")):
    for container in containers:
        items = state[container]
        idx = next((i for i, it in enumerate(items) if it["id"] == item_id), None)
        if idx is not None:
            return container, idx, items[idx]
    return None, None, None


def find_active(state):
    """Returns (container, idx, item) for whichever item should actually be
    worked on right now — skips anything blocked or suspended.

    The interrupt stack always wins (genuine emergencies preempt everything).
    Within the main queue, while any gate item is open, ONLY gate items are
    selectable — non-gate work is unreachable until the day's dominant work is
    done. That hard block is the whole anti-procrastination mechanism."""
    for i in range(len(state["stack"]) - 1, -1, -1):  # top = last elem, scan downward
        it = state["stack"][i]
        if not it.get("blocked") and not it.get("suspended"):
            return "stack", i, it
    gate_mode = has_open_gate(state)
    for i, it in enumerate(state["queue"]):  # front = first elem, scan forward
        if it.get("blocked") or it.get("suspended"):
            continue
        if gate_mode and not is_gate_item(it):
            continue  # gate is open: non-gate work stays locked
        return "queue", i, it
    return None, None, None


def mark_active(state, item):
    if state["active"] is None or state["active"]["id"] != item["id"]:
        state["active"] = {"id": item["id"], "started_at": now_iso()}


def elapsed_str(started_at):
    try:
        started = datetime.fromisoformat(started_at)
    except Exception:
        return "?"
    delta = datetime.now(timezone.utc).astimezone() - started
    mins = int(delta.total_seconds() // 60)
    secs = int(delta.total_seconds() % 60)
    return f"{mins}m{secs:02d}s"


def item_tag(item, books_data=None):
    """Only the state that matters at a glance — blocked / suspended. Track,
    group and gate are shown by section context, not repeated on every line."""
    states = []
    if item.get("blocked"):
        states.append(f"blocked: {item['blocked_reason']}" if item.get("blocked_reason") else "blocked")
    if item.get("suspended"):
        states.append("suspended")
    return dim("  · " + ", ".join(states)) if states else ""


def fmt_line(item, active=False, books_data=None):
    """One task, rendered clean: a marker, a dim id, the text, subtle state."""
    marker = accent("→") if active else " "
    idcol = dim(f"{item['id']:>2}")
    return f"  {marker} {idcol}  {item['text']}{item_tag(item, books_data)}"


# ---------- commands ----------

def cmd_add(state, args):
    text = " ".join(args.task).strip()
    if not text:
        print("Nothing to add — empty task text.", file=sys.stderr)
        return
    rules = load_rules()
    container = "stack" if args.priority else "quick" if args.quick else "queue"
    policy, maxn, on_full = capacity_policy(state, rules, container)

    if policy == "reject":
        if container == "stack":
            print(f"🛑 Interrupt stack full ({maxn}). If everything's urgent, nothing is — "
                  f"finish/clear one (`mm done`/`mm move`) before adding another interrupt.")
        else:
            print(f"🛑 {container} full ({maxn}). Clear something first, or raise the cap: "
                  f"`mm capacity {container} <n>`.")
        return

    if policy == "warn":
        print(f"⚠️  {container} at {len(state[container])}/{maxn} — consider clearing before it balloons.", file=sys.stderr)

    item = new_item(state, text)

    if policy == "backlog":
        item["_from"] = container
        state["backlog"].append(item)
        log_event(state, f"add over capacity → backlog ({container}): [{item['id']}] {text}")
        print(f"  {warn('~')} {container} full ({maxn}) — parked in backlog  {dim(str(item['id']))}  {text}")
        print(dim("    resurfaces automatically as space frees (or: mm backlog --promote)"))
        return

    if container == "stack":
        state["stack"].append(item)
        log_event(state, f"pushed to interrupt stack: [{item['id']}] {text}")
        print(f"  {warn('!')} interrupt  {dim(str(item['id']))}  {text}")
    elif container == "quick":
        state["quick"].append(item)
        log_event(state, f"added to quick queue: [{item['id']}] {text}")
        print(f"  {dim('+')} quick  {dim(str(item['id']))}  {text}")
    else:
        state["queue"].append(item)
        log_event(state, f"enqueued: [{item['id']}] {text}")
        print(f"  {good('+')} queued  {dim(str(item['id']))}  {text}")


def cmd_next(state, _args):
    for it in promote_backlog(state, load_rules()):
        print(dim(f"  ↑ promoted from backlog  {it['id']}  {it['text']}"))
    kind, _idx, item = find_active(state)
    if item:
        mark_active(state, item)
        el = elapsed_str(state["active"]["started_at"])
        note = warn("interrupt") if kind == "stack" else dim(f"{el} active")
        print(f"\n{fmt_line(item, active=True, books_data=load_books())}   {note}\n")
    else:
        state["active"] = None
        stuck_n = sum(1 for it in state["stack"] + state["queue"] if it.get("blocked") or it.get("suspended"))
        if stuck_n:
            print(f"\n  {dim('nothing active —')} {stuck_n} blocked/suspended {dim('(mm status)')}\n")
        else:
            print(f"\n  {good('all clear')} {dim('— queue and stack empty')}\n")
    if state["quick"]:
        print(dim(f"  {len(state['quick'])} quick waiting — flush at a checkpoint (mm flush-quick)"))


def cmd_peek(state, _args):
    """Like mm next, but never starts/touches the active timer. Just a glance."""
    kind, _idx, item = find_active(state)
    if item:
        started = state["active"]["started_at"] if (state["active"] and state["active"]["id"] == item["id"]) else None
        el = elapsed_str(started) if started else "not started"
        note = warn("interrupt") if kind == "stack" else dim(el)
        print(f"\n{fmt_line(item, active=True, books_data=load_books())}   {note}")
    else:
        print(f"\n  {dim('nothing active')}")
    upcoming = [it for it in state["queue"] if not it.get("blocked") and not it.get("suspended")][:3]
    for t in upcoming[1:]:
        print(fmt_line(t))
    if state["quick"]:
        print(dim(f"  {len(state['quick'])} quick waiting"))
    print()


def cmd_done(state, args):
    snapshot(state)
    target_id = args.id

    def finish(container, idx, item):
        item = state[container].pop(idx)
        item["done_at"] = now_iso()
        state["archive"].append(item)
        log_event(state, f"done: [{item['id']}] {item['text']}")
        print(f"\n  {good('✓ done')}  {dim(str(item['id']))}  {item['text']}")
        state["active"] = None
        if is_gate_item(item):
            reward_check(state)

    if target_id is None:
        container, idx, item = find_active(state)
        if item is None:
            state["_snapshots"].pop()  # nothing happened, don't waste an undo slot
            print("Nothing active.")
            return
        finish(container, idx, item)
        cmd_next(state, args)
        return
    container, idx, item = find_item(state, target_id, containers=("stack", "queue"))
    if item is not None:
        finish(container, idx, item)
        cmd_next(state, args)
        return
    state["_snapshots"].pop()
    print("Nothing found to mark done.")


def cmd_block(state, args):
    snapshot(state)
    kind, idx, item = find_active(state)
    if not item:
        state["_snapshots"].pop()
        print("Nothing active to block.")
        return
    reason = " ".join(args.reason).strip() if getattr(args, "reason", None) else None
    el = elapsed_str(state["active"]["started_at"]) if state["active"] else "?"
    item["blocked"] = True
    item["blocked_reason"] = reason
    tag = f" — {reason}" if reason else ""
    if kind == "stack":
        state["stack"].pop(idx)
        state["stack"].insert(0, item)  # hold blocked interrupt at bottom, don't lose it
        log_event(state, f"blocked (interrupt, held after {el}): [{item['id']}] {item['text']}{tag}")
        print(f"  {dim('⏸ blocked')} {dim('('+el+', held)')}  {item['text']}{dim(tag)}")
    else:
        state["queue"].pop(idx)
        state["queue"].append(item)
        log_event(state, f"blocked, requeued after {el}: [{item['id']}] {item['text']}{tag}")
        print(f"  {dim('⏸ blocked')} {dim('('+el+', requeued)')}  {item['text']}{dim(tag)}")
    state["active"] = None
    cmd_next(state, args)


def cmd_unblock(state, args):
    snapshot(state)
    container, idx, item = find_item(state, args.id)
    if item is None or not item.get("blocked"):
        state["_snapshots"].pop()
        if item is None:
            print(f"No item with id {args.id} found.")
        else:
            print(f"[{item['id']}] {item['text']} isn't blocked.")
        return
    items = state[container]
    reason = item.pop("blocked_reason", None)
    item["blocked"] = False
    tag = f" (was: {reason})" if reason else ""
    if container == "stack":
        items.pop(idx)
        items.append(item)  # top of stack = active again
    elif container == "queue" and args.front:
        items.pop(idx)
        items.insert(0, item)  # jump the queue now that it's unblocked
    log_event(state, f"unblocked: [{item['id']}] {item['text']}{tag}")
    print(f"▶️  Unblocked [{item['id']}]: {item['text']}{tag}")


def cmd_suspend(state, args):
    snapshot(state)
    if args.id is not None:
        container, idx, item = find_item(state, args.id, containers=("stack", "queue"))
    else:
        container, idx, item = find_active(state)
    if item is None:
        state["_snapshots"].pop()
        print("Nothing to suspend.")
        return
    item["suspended"] = True
    item["suspended_at"] = now_iso()
    if state["active"] and state["active"]["id"] == item["id"]:
        state["active"] = None
    log_event(state, f"suspended: [{item['id']}] {item['text']}")
    print(f"⏹  Suspended [{item['id']}]: {item['text']}")
    cmd_next(state, args)


def cmd_resume(state, args):
    snapshot(state)
    if args.id is not None:
        container, idx, item = find_item(state, args.id, containers=("stack", "queue"))
        if item is None or not item.get("suspended"):
            state["_snapshots"].pop()
            print(f"No suspended item with id {args.id} found.")
            return
    else:
        # most recently suspended, across stack+queue
        candidates = [(c, i, it) for c in ("stack", "queue") for i, it in enumerate(state[c]) if it.get("suspended")]
        if not candidates:
            state["_snapshots"].pop()
            print("Nothing suspended.")
            return
        container, idx, item = max(candidates, key=lambda x: x[2].get("suspended_at", ""))
    item["suspended"] = False
    item.pop("suspended_at", None)
    log_event(state, f"resumed: [{item['id']}] {item['text']}")
    print(f"▶️  Resumed [{item['id']}]: {item['text']}")


def cmd_move(state, args):
    snapshot(state)
    container, idx, item = find_item(state, args.id)
    if item is None:
        state["_snapshots"].pop()
        print(f"No item with id {args.id} found.")
        return
    if container == args.dest:
        state["_snapshots"].pop()
        print(f"[{item['id']}] already in {args.dest}.")
        return
    state[container].pop(idx)
    if args.dest == "queue" and args.front:
        state["queue"].insert(0, item)
    else:
        state[args.dest].append(item)
    log_event(state, f"moved [{item['id']}] {item['text']}: {container} -> {args.dest}")
    print(f"↪️  Moved [{item['id']}]: {container} -> {args.dest}")


def cmd_rm(state, args):
    snapshot(state)
    container, idx, item = find_item(state, args.id)
    if item is not None:
        state[container].pop(idx)
        log_event(state, f"removed: [{item['id']}] {item['text']}")
        print(f"🗑  Removed [{item['id']}]: {item['text']}")
        return
    state["_snapshots"].pop()
    print(f"No item with id {args.id} found.")


def cmd_edit(state, args):
    snapshot(state)
    text = " ".join(args.text).strip()
    container, idx, item = find_item(state, args.id)
    if item is not None:
        old = item["text"]
        item["text"] = text
        log_event(state, f"edited [{item['id']}]: '{old}' -> '{text}'")
        print(f"✏️  Edited [{item['id']}]: {text}")
        return
    state["_snapshots"].pop()
    print(f"No item with id {args.id} found.")


def cmd_note(state, args):
    snapshot(state)
    text = " ".join(args.text).strip()
    container, idx, item = find_item(state, args.id)
    if item is not None:
        existing = item.get("note")
        item["note"] = f"{existing}\n{text}" if existing else text
        log_event(state, f"note added [{item['id']}]: {text}")
        print(f"📝 Noted [{item['id']}]: {text}")
        return
    state["_snapshots"].pop()
    print(f"No item with id {args.id} found.")


def cmd_find(state, args):
    query = " ".join(args.query).strip().lower()
    if not query:
        print("Give me something to search for.")
        return
    hits = []
    for container in ("stack", "queue", "quick"):
        for t in state[container]:
            if query in t["text"].lower() or query in (t.get("note") or "").lower():
                hits.append((container, t))
    for t in state["archive"]:
        if query in t["text"].lower() or query in (t.get("note") or "").lower():
            hits.append(("archive", t))
    if not hits:
        print(f"No matches for '{query}'.")
        return
    for container, t in hits:
        note = f"  — note: {t['note']}" if t.get("note") else ""
        print(f"[{container}] [{t['id']}] {t['text']}{note}")


def cmd_undo(state, _args):
    if not state["_snapshots"]:
        print("Nothing to undo.")
        return
    snap = state["_snapshots"].pop()
    remaining = state["_snapshots"]
    state.clear()
    state.update(snap)
    state["_snapshots"] = remaining
    print("↩️  Undid last action.")


def cmd_flush_quick(state, _args):
    if not state["quick"]:
        print("Quick queue empty.")
        return
    snapshot(state)
    print(f"🔻 Flushing {len(state['quick'])} quick task(s):")
    for t in state["quick"]:
        print(f"   [{t['id']}] {t['text']}")
    log_event(state, f"flushed quick queue ({len(state['quick'])} items)")
    state["quick"] = []


def _cap_str(rules, container, state):
    maxn, on_full = capacity_for(rules, container)
    return f"{len(state[container])}/{maxn}" if maxn is not None else str(len(state[container]))


def cmd_status(state, _args):
    rules = load_rules()
    books_data = load_books()
    _kind, _idx, active = find_active(state)
    active_id = active["id"] if active else None

    def section(title, count_str, items, note=""):
        head = f"  {bold(title)}  {dim(count_str)}"
        if note:
            head += f"   {accent(note)}"
        print(head)
        if not items:
            print(dim("     —"))
        for t in items:
            print(fmt_line(t, active=(t["id"] == active_id), books_data=books_data))
        print()

    print()
    section("interrupt", _cap_str(rules, "stack", state), list(reversed(state["stack"])))
    gate_note = "gate open — only gate items selectable" if has_open_gate(state) else ""
    section("queue", _cap_str(rules, "queue", state), state["queue"], gate_note)
    section("quick", _cap_str(rules, "quick", state), state["quick"])
    if state.get("backlog"):
        section("backlog", str(len(state["backlog"])), state["backlog"])
    open_session = next((s for s in reversed(state["sessions"]) if "stopped_at" not in s), None)
    if open_session:
        print(dim(f"  session running: {open_session['label']} since {open_session['started_at']}\n"))


def cmd_stats(state, _args):
    today = today_str()
    done_today = [t for t in state["archive"] if t.get("done_at", "").startswith(today)]
    added_today = [e for e in state["log"] if e["ts"].startswith(today) and
                   (e["event"].startswith("enqueued") or e["event"].startswith("pushed") or e["event"].startswith("added to quick"))]
    blocked_now = sum(1 for t in state["stack"] + state["queue"] if t.get("blocked"))
    suspended_now = sum(1 for t in state["stack"] + state["queue"] if t.get("suspended"))
    open_now = len(state["queue"]) + len(state["stack"])
    gates_closed, gates_open = gate_progress_today(state)
    streak = streak_length(state.get("gate_days", []), today)
    print(f"\n  {bold(today)}")
    print(f"    {dim('done')}       {good(str(len(done_today)))}")
    print(f"    {dim('added')}      {len(added_today)}")
    print(f"    {dim('blocked')}    {blocked_now}")
    print(f"    {dim('suspended')}  {suspended_now}")
    print(f"    {dim('open')}       {open_now} {dim('queue+stack')} · {len(state['quick'])} {dim('quick')}")
    print(f"    {dim('gates')}      {good(str(gates_closed))} {dim('closed ·')} {gates_open} {dim('open')}")
    print(f"    {dim('streak')}     {bold(str(streak))} {dim('day(s) all-gates-closed')}\n")


def cmd_session(state, _args):
    today = today_str()
    todays = [e for e in state["log"] if e["ts"].startswith(today)]
    if not todays:
        print("No activity logged today.")
        return
    print(f"🕒 Timeline — {today}")
    for e in todays:
        t = e["ts"].split("T")[1][:8]
        print(f"   {t}  {e['event']}")


def cmd_archive(state, args):
    items = state["archive"]
    if getattr(args, "scope", None) == "today":
        today = today_str()
        items = [t for t in items if t.get("done_at", "").startswith(today)]
        print(f"📦 Archive — today ({len(items)}):")
    else:
        print(f"📦 Archive — all time ({len(items)}):")
    for t in items:
        print(f"   [{t['id']}] {t['text']}  (done {t.get('done_at', '?')})")


def cmd_export(state, args):
    fmt = args.format
    rows = []
    for container in ("stack", "queue", "quick", "backlog"):
        for t in state.get(container, []):
            rows.append({"id": t["id"], "text": t["text"], "container": container,
                         "status": "blocked" if t.get("blocked") else ("suspended" if t.get("suspended") else "open")})
    for t in state["archive"]:
        rows.append({"id": t["id"], "text": t["text"], "container": "archive", "status": "done"})
    if fmt == "json":
        print(json.dumps(rows, indent=2))
    elif fmt == "csv":
        buf = io.StringIO()
        writer = csv.DictWriter(buf, fieldnames=["id", "text", "container", "status"])
        writer.writeheader()
        writer.writerows(rows)
        print(buf.getvalue(), end="")
    else:  # md
        print("| id | text | container | status |")
        print("|----|------|-----------|--------|")
        for r in rows:
            print(f"| {r['id']} | {r['text']} | {r['container']} | {r['status']} |")


def cmd_start(state, args):
    open_session = next((s for s in reversed(state["sessions"]) if "stopped_at" not in s), None)
    if open_session:
        print(f"A session is already running: '{open_session['label']}' (started {open_session['started_at']}). mm stop first.")
        return
    label = " ".join(args.label).strip() if args.label else "session"
    state["sessions"].append({"label": label, "started_at": now_iso()})
    log_event(state, f"session started: {label}")
    print(f"▶ Session started: {label}")


def cmd_stop(state, _args):
    open_session = next((s for s in reversed(state["sessions"]) if "stopped_at" not in s), None)
    if not open_session:
        print("No active session.")
        return
    open_session["stopped_at"] = now_iso()
    started = datetime.fromisoformat(open_session["started_at"])
    stopped = datetime.fromisoformat(open_session["stopped_at"])
    mins = int((stopped - started).total_seconds() // 60)
    window = [e for e in state["log"] if open_session["started_at"] <= e["ts"] <= open_session["stopped_at"]]
    interruptions = sum(1 for e in window if e["event"].startswith("pushed to interrupt stack"))
    completions = sum(1 for e in window if e["event"].startswith("done:"))
    open_session["duration_min"] = mins
    open_session["interruptions"] = interruptions
    open_session["completions"] = completions
    log_event(state, f"session stopped: {open_session['label']} ({mins}m, {completions} done, {interruptions} interrupts)")
    print(f"⏹  Session '{open_session['label']}' ended: {mins}m, {completions} done, {interruptions} interrupt(s)")


def cmd_log(state, args):
    n = args.n or 10
    for entry in state["log"][-n:]:
        print(f"{entry['ts']}  {entry['event']}")


def cmd_book_add(_state, args):
    data = load_books()
    title = " ".join(args.title).strip()
    if not title:
        print("Nothing to add — empty title.", file=sys.stderr)
        return
    if args.pages <= 0:
        print(f"⚠️  '{title}' needs a real page count (>0), got {args.pages}. Not added.", file=sys.stderr)
        return
    if any(b["title"].lower() == title.lower() for b in data["books"]):
        print(f"'{title}' is already on the list.", file=sys.stderr)
        return
    book_id = data["next_id"]
    data["next_id"] += 1
    entry = {"id": book_id, "title": title, "pages": args.pages, "page": 0, "status": "queued"}
    if getattr(args, "group", None):
        entry["group"] = args.group
    data["books"].append(entry)
    save_books(data)
    tag = f" [group: {args.group}]" if getattr(args, "group", None) else ""
    print(f"📚 Added [{book_id}]: {title} ({args.pages}p){tag}")


def cmd_book_progress(_state, args):
    data = load_books()
    book = find_book(data, args.id)
    if book is None:
        print(f"No book with id {args.id} found. mm book list to see ids.", file=sys.stderr)
        return
    book["status"] = "active"
    book["page"] = min(book["page"] + args.pages, book["pages"])
    title, pages, page = book["title"], book["pages"], book["page"]
    if page >= pages:
        book["status"] = "done"
        save_books(data)
        print(f"  {good('✓ finished')}  {title}  {dim(f'({pages}p)')}")
        return
    save_books(data)
    pct = page * 100 // pages
    print(f"  {good('+')} {title}  {page}/{pages}p  {dim(f'{pct}%')}")


def cmd_book_done(_state, args):
    data = load_books()
    book = find_book(data, args.id)
    if book is None:
        print(f"No book with id {args.id} found.", file=sys.stderr)
        return
    if book["status"] == "done":
        print(f"[{book['id']}] {book['title']} was already marked done.")
        return
    book["page"] = book["pages"]
    book["status"] = "done"
    save_books(data)
    print(f"📗 Finished [{book['id']}]: {book['title']}! (marked done directly, no page count needed)")


def cmd_book_list(_state, _args):
    data = load_books()
    if not data["books"]:
        print("No books yet. mm book add \"Title\" <pages>")
        return
    active = [b for b in data["books"] if b["status"] != "done"]
    daily = data.get("daily_units", 2)
    todays_picks = {b["id"] for b in pick_books_for_today(data, daily)}
    print(f"\n  {bold('books')}  {dim(f'{len(active)} open · {daily}/day')}\n")
    for b in data["books"]:
        done = b["status"] == "done"
        mark = good("✓") if done else (accent("→") if b["id"] in todays_picks else " ")
        pct = f"{b['page']}/{b['pages']}p" if b["pages"] else "?"
        grp = dim(f"  · {b['group']}") if b.get("group") else ""
        title = dim(b["title"]) if done else b["title"]
        idcol = dim(f"{b['id']:>2}")
        print(f"  {mark} {idcol}  {title}  {dim(pct)}{grp}")
    print()


WEEKDAY_KEYS = ["Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun"]  # datetime.weekday(): Mon=0


def today_weekday_key():
    """Locale-independent weekday key. strftime('%a') depends on the system's
    LC_TIME setting and silently returns non-English abbreviations under a
    different locale (e.g. 'So' instead of 'Sun') — which would make weekday
    track lookups vanish with no error at all. This never depends on locale."""
    return WEEKDAY_KEYS[datetime.now().weekday()]


def load_books_config():
    if not os.path.exists(BOOKS_CONFIG_PATH):
        return None
    try:
        with open(BOOKS_CONFIG_PATH) as f:
            return json.load(f)
    except (json.JSONDecodeError, OSError) as e:
        print(f"⚠️  {BOOKS_CONFIG_PATH} is malformed ({e}). Fix the JSON and re-run.", file=sys.stderr)
        return None



def cmd_book_sync(_state, _args):
    config = load_books_config()
    if config is None:
        if not os.path.exists(BOOKS_CONFIG_PATH):
            print(f"No config found at {BOOKS_CONFIG_PATH}.")
            print("Create it with a \"books\" list: [{\"title\": ..., \"pages\": ..., \"group\": ...}]")
        # if the file exists but is malformed, load_books_config already printed why
        return
    data = load_books()
    by_title = {b["title"].lower(): b for b in data["books"]}
    added, updated = [], []
    config_titles = set()

    for entry in config.get("books", []):
        title = entry["title"].strip()
        config_titles.add(title.lower())
        pages = entry.get("pages")
        group = entry.get("group")
        existing = by_title.get(title.lower())
        if existing is None:
            if pages is None or pages <= 0:
                print(f"⚠️  Skipping '{title}': needs a real page count in config (got {pages}).", file=sys.stderr)
                continue
            book_id = data["next_id"]
            data["next_id"] += 1
            new_book = {"id": book_id, "title": title, "pages": pages, "page": 0, "status": "queued"}
            if group:
                new_book["group"] = group
            data["books"].append(new_book)
            added.append(title)
        else:
            # Reconcile metadata only — never touch page/status, that's earned progress.
            changed = False
            if pages is not None and pages > 0 and existing["pages"] != pages:
                existing["pages"] = pages
                changed = True
            if group != existing.get("group"):
                if group:
                    existing["group"] = group
                else:
                    existing.pop("group", None)
                changed = True
            if changed:
                updated.append(title)

    orphaned = [b["title"] for b in data["books"]
                if b["title"].lower() not in config_titles and b["status"] != "done"]

    if "daily_units" in config and config["daily_units"] != data.get("daily_units"):
        data["daily_units"] = config["daily_units"]
        print(f"   daily_units set to {config['daily_units']}")

    save_books(data)
    print(f"🔄 Synced from {BOOKS_CONFIG_PATH}")
    print(f"   added:   {len(added)}" + (f"  ({', '.join(added)})" if added else ""))
    print(f"   updated: {len(updated)}" + (f"  ({', '.join(updated)})" if updated else ""))
    if orphaned:
        print(f"   ⚠️  in mm but no longer in config (left untouched, not deleted): {', '.join(orphaned)}")
        print("      remove by hand with `mm book rm <id>` if that's intentional.")


def cmd_book_rm(_state, args):
    data = load_books()
    book = find_book(data, args.id)
    if book is None:
        print(f"No book with id {args.id} found.", file=sys.stderr)
        return
    data["books"] = [b for b in data["books"] if b["id"] != args.id]
    save_books(data)
    print(f"🗑  Removed [{book['id']}]: {book['title']}")


def leading_gate_count(queue):
    """How many items at the very front of the queue are already-undone gate
    items from a previous onboard. New onboard items must be inserted right
    after this run, never ahead of it — otherwise today's fresh content
    would leapfrog yesterday's still-unfinished work, breaking the gate."""
    count = 0
    for item in queue:
        if is_gate_item(item):
            count += 1
        else:
            break
    return count


# ---------- unified rules engine ----------

def _merge_rules_defaults(rules):
    """Fill in any missing top-level sections so the rest of the engine can
    assume a complete shape. Never overwrites what the user declared."""
    if not isinstance(rules, dict):
        rules = {}
    rules.setdefault("version", 1)
    onboard = rules.setdefault("onboard", {})
    onboard.setdefault("strict_gate", True)
    onboard.setdefault("order", list(rules.get("tracks", {}).keys()))
    cap = rules.setdefault("capacity", {})
    for name, defaults in default_capacity().items():
        slot = cap.setdefault(name, {})
        slot.setdefault("max", defaults["max"])
        slot.setdefault("on_full", defaults["on_full"])
    rules.setdefault("tracks", {})
    return rules


def load_rules():
    """The single source of truth for onboarding: mm.rules.json. If it's missing
    or malformed, onboarding simply queues nothing (rather than crashing) — the
    rest of mm keeps working as a plain queue/stack/quick scheduler."""
    if os.path.exists(RULES_PATH):
        try:
            with open(RULES_PATH) as f:
                return _merge_rules_defaults(json.load(f))
        except (json.JSONDecodeError, OSError) as e:
            print(f"⚠️  {RULES_PATH} is malformed ({e}); onboarding is disabled until you fix it.", file=sys.stderr)
    return _merge_rules_defaults({})


def save_rules(rules):
    ensure_dir()
    fd, tmp = tempfile.mkstemp(dir=STATE_DIR, prefix=".rules-", suffix=".tmp")
    try:
        with os.fdopen(fd, "w") as f:
            json.dump(rules, f, indent=2, ensure_ascii=False)
            f.flush()
            os.fsync(f.fileno())
        os.replace(tmp, RULES_PATH)
    finally:
        if os.path.exists(tmp):
            os.remove(tmp)


def _as_list(value):
    """A track's daily value may be a scalar or a list — normalize to a list so
    'multiple items per day' is just data, not a special case."""
    if value is None:
        return []
    if isinstance(value, list):
        return value
    return [value]


def _fmt_label(label, **kw):
    try:
        return label.format(**kw)
    except (KeyError, IndexError, ValueError):
        return label


def compile_track(name, track, weekday, count_override=None):
    """Turn one track's config into concrete item specs for today. Dispatch on
    `type` — this table is the single extension seam for future track kinds
    (and, later, a scripting layer)."""
    if not isinstance(track, dict):
        print(f"⚠️  Track '{name}' is malformed; skipping.", file=sys.stderr)
        return []
    ttype = track.get("type")
    dominant = bool(track.get("dominant", False))
    gate = bool(track.get("gate", False)) or dominant
    position = track.get("position", "back")
    label = track.get("label", "{value}")
    daily_cap = track.get("daily_cap")

    def spec(text, ref=None, group=None):
        return {"text": text, "gate": gate, "dominant": dominant,
                "track": name, "position": position, "ref": ref, "group": group}

    specs = []
    if ttype == "rotation":
        data = load_books()
        count = count_override if count_override is not None else track.get("count", data.get("daily_units", 2))
        for b in pick_books_for_today(data, count):
            text = _fmt_label(label, id=b["id"], title=b["title"],
                              page=b["page"], pages=b["pages"], value=b["title"])
            specs.append(spec(text, ref=b["id"], group=b.get("group")))
    elif ttype == "weekday":
        for v in _as_list(track.get("table", {}).get(weekday)):
            if v:
                specs.append(spec(_fmt_label(label, value=v)))
    elif ttype in ("static", "list"):
        for v in _as_list(track.get("items", track.get("values"))):
            if v:
                specs.append(spec(_fmt_label(label, value=v)))
    else:
        print(f"⚠️  Track '{name}' has unknown type '{ttype}'; skipping.", file=sys.stderr)
        return []

    if isinstance(daily_cap, int) and daily_cap >= 0:
        specs = specs[:daily_cap]
    return specs


def compile_rules(rules, weekday, count_override=None):
    """Compile every track, in the declared onboard order, into a flat list of
    specs. Pure — reads config + books, produces specs, mutates nothing."""
    tracks = rules.get("tracks", {})
    order = rules.get("onboard", {}).get("order") or list(tracks.keys())
    specs = []
    for name in order:
        track = tracks.get(name)
        if track is None:
            continue
        specs.extend(compile_track(name, track, weekday, count_override))
    return specs


# ---------- capacity governor + backlog ----------

def capacity_for(rules, container):
    slot = rules.get("capacity", {}).get(container, {})
    return slot.get("max"), slot.get("on_full", "warn")


def capacity_policy(state, rules, container):
    """What would happen to the NEXT arrival in `container` right now: 'ok'
    (room to spare), or the configured on_full action ('backlog'/'reject'/'warn')."""
    maxn, on_full = capacity_for(rules, container)
    if maxn is None or len(state[container]) < maxn:
        return "ok", maxn, on_full
    return on_full, maxn, on_full


def promote_backlog(state, rules):
    """Pull parked items back into the queue as space frees up (oldest first),
    so overflow ideas resurface automatically instead of being lost."""
    maxn, _ = capacity_for(rules, "queue")
    promoted = []
    i = 0
    while i < len(state["backlog"]):
        if maxn is not None and len(state["queue"]) >= maxn:
            break
        item = state["backlog"][i]
        if item.get("_from", "queue") != "queue":
            i += 1
            continue
        state["backlog"].pop(i)
        item.pop("_from", None)
        state["queue"].append(item)
        promoted.append(item)
        log_event(state, f"promoted from backlog: [{item['id']}] {item['text']}")
    return promoted


# ---------- onboarding (engine-driven) ----------

def cmd_onboard(state, args):
    today = today_str()
    rules = load_rules()
    strict = rules.get("onboard", {}).get("strict_gate", True)

    # Hard gate: refuse to start a new day while dominant/gate work is still open.
    if strict and has_open_gate(state):
        open_gates = [it for it in state["queue"] if is_gate_item(it) and not it.get("suspended")]
        headline = warn("Can't onboard yet")
        subtext = dim("— finish (or suspend) yesterday's gate work first:")
        print(f"\n  {headline} {subtext}\n")
        for it in open_gates:
            print(fmt_line(it))
        print()
        return

    if state.get("onboarded_date") == today:
        print(f"\n  {dim('already onboarded today — nothing to re-add')}\n")
        return

    snapshot(state)
    weekday = today_weekday_key()
    count_override = getattr(args, "count", None)
    specs = compile_rules(rules, weekday, count_override)

    seen = {(it.get("track"), it["text"]) for it in state["queue"]}
    seen_texts = {it["text"] for it in state["queue"]}
    gate_specs, front_specs, back_specs = [], [], []
    skipped = []
    for s in specs:
        if (s["track"], s["text"]) in seen or s["text"] in seen_texts:
            skipped.append(s["text"])
            continue
        seen.add((s["track"], s["text"]))
        seen_texts.add(s["text"])
        pos = s.get("position", "back")
        (gate_specs if pos == "gate" else front_specs if pos == "front" else back_specs).append(s)

    added, backlogged = [], []

    def make(s):
        return new_item(state, s["text"], gate=s.get("gate", False),
                        dominant=s.get("dominant", False), track=s.get("track"),
                        rule_id=s.get("track"), ref=s.get("ref"), group=s.get("group"))

    # Gate items bypass the capacity cap (the non-negotiable core of the day)
    # and land right after any still-undone gate items from before, never ahead.
    gate_items = [make(s) for s in gate_specs]
    insert_at = leading_gate_count(state["queue"])
    state["queue"][insert_at:insert_at] = gate_items
    for it in gate_items:
        added.append(it)
        log_event(state, f"onboarded ({it.get('track')}, gate): [{it['id']}] {it['text']}")

    # Non-gate items respect the queue capacity: overflow parks in the backlog.
    for s in front_specs + back_specs:
        policy, maxn, _ = capacity_policy(state, rules, "queue")
        if policy == "reject":
            skipped.append(s["text"])
            continue
        item = make(s)
        if policy == "backlog":
            item["_from"] = "queue"
            state["backlog"].append(item)
            backlogged.append(item)
            log_event(state, f"onboarded→backlog ({item.get('track')}): [{item['id']}] {item['text']}")
            continue
        if policy == "warn":
            print(f"⚠️  queue at {len(state['queue'])}/{maxn} — adding anyway.", file=sys.stderr)
        if s.get("position") == "front":
            state["queue"].insert(leading_gate_count(state["queue"]), item)
        else:
            state["queue"].append(item)
        added.append(item)
        log_event(state, f"onboarded ({item.get('track')}): [{item['id']}] {item['text']}")

    state["onboarded_date"] = today

    pretty_day = datetime.now().strftime("%a %d %b").lower()
    if not added and not backlogged:
        print(f"\n  {bold('onboarded')} {dim('· ' + pretty_day)} {dim('— nothing new')}\n")
    else:
        print(f"\n  {bold('onboarded')} {dim('· ' + pretty_day)}\n")
        books_data = load_books()
        for item in added:
            print(fmt_line(item, books_data=books_data))
        print()
    if backlogged:
        print(dim(f"  {len(backlogged)} over capacity → backlog: " +
                  ", ".join(str(it['id']) for it in backlogged)))
    if skipped:
        print(dim(f"  skipped (already queued): {', '.join(skipped)}"))


# ---------- rules / capacity / backlog commands ----------

def cmd_rules_show(state, _args):
    rules = load_rules()
    weekday = today_weekday_key()
    source = RULES_PATH if os.path.exists(RULES_PATH) else f"(none yet — create {RULES_PATH})"
    print(f"\n  {bold('rules')}  {dim(source)}")
    print(f"    {dim('strict_gate')} {rules['onboard'].get('strict_gate', True)}   {dim('order')} {', '.join(rules['onboard'].get('order', []))}")
    cap = rules.get("capacity", {})
    print("    " + dim("capacity  ") + ", ".join(f"{k}={v.get('max')}({v.get('on_full')})" for k, v in cap.items()))
    specs = compile_rules(rules, weekday)
    print(f"\n  {bold('today')} {dim('· ' + weekday)} — {len(specs)} item(s):\n")
    if not specs:
        print(dim("     nothing scheduled"))
    for s in specs:
        flag = "gate" if (s.get("dominant") or s.get("gate")) else s.get("position", "back")
        print(f"     {s['text']}  {dim('· ' + s['track'] + ' · ' + flag)}")
    print()


def cmd_rules_validate(state, _args):
    rules = load_rules()
    errors, warnings = [], []
    onboard = rules.get("onboard", {})
    tracks = rules.get("tracks", {})
    if not isinstance(tracks, dict) or not tracks:
        warnings.append("no tracks defined — onboard will queue nothing.")
    for name in onboard.get("order", []):
        if name not in tracks:
            warnings.append(f"onboard.order references unknown track '{name}'.")
    valid_types = {"rotation", "weekday", "static", "list"}
    valid_pos = {"gate", "front", "back"}
    for name, track in (tracks.items() if isinstance(tracks, dict) else []):
        if not isinstance(track, dict):
            errors.append(f"track '{name}' is not an object.")
            continue
        if track.get("type") not in valid_types:
            errors.append(f"track '{name}' has invalid type '{track.get('type')}' (expected one of {sorted(valid_types)}).")
        if track.get("position", "back") not in valid_pos:
            errors.append(f"track '{name}' has invalid position '{track.get('position')}'.")
    for cname, slot in rules.get("capacity", {}).items():
        if not isinstance(slot, dict) or not isinstance(slot.get("max"), int):
            errors.append(f"capacity.{cname}.max must be an integer.")
        elif slot.get("on_full") not in ("backlog", "reject", "warn"):
            errors.append(f"capacity.{cname}.on_full must be backlog|reject|warn.")
    for w in warnings:
        print(f"⚠️  {w}")
    for e in errors:
        print(f"❌ {e}")
    if not errors and not warnings:
        print("✅ Rules valid.")
    elif not errors:
        print("✅ Rules usable (warnings only).")
    if errors:
        sys.exit(1)


def cmd_backlog(state, args):
    if getattr(args, "promote", False):
        snapshot(state)
        rules = load_rules()
        promoted = promote_backlog(state, rules)
        if promoted:
            print(f"⬆️  Promoted {len(promoted)} item(s) into the queue:")
            for it in promoted:
                print(f"   [{it['id']}] {it['text']}")
        else:
            state["_snapshots"].pop()
            print("Nothing promoted (queue full or backlog empty).")
        return
    if not state["backlog"]:
        print("📥 Backlog empty.")
        return
    print(f"📥 Backlog ({len(state['backlog'])} parked over capacity):")
    books_data = load_books()
    for it in state["backlog"]:
        print(f"   [{it['id']}] {it['text']}{item_tag(it, books_data)}")
    print("   Run `mm backlog --promote` to pull items back in as space allows.")


def cmd_capacity(state, args):
    rules = load_rules()
    container = getattr(args, "container", None)
    maxn = getattr(args, "max", None)
    if container is None:
        print("📦 Capacity limits:")
        for k, v in rules.get("capacity", {}).items():
            print(f"   {k:6s} max={v.get('max')}  on_full={v.get('on_full')}  (currently {len(state.get(k, []))} open)")
        print(f"   backlog: {len(state.get('backlog', []))} parked")
        return
    if maxn is None:
        slot = rules.get("capacity", {}).get(container, {})
        print(f"{container}: max={slot.get('max')} on_full={slot.get('on_full')}")
        return
    rules.setdefault("capacity", {}).setdefault(container, {"on_full": default_capacity().get(container, {}).get("on_full", "warn")})
    rules["capacity"][container]["max"] = maxn
    save_rules(rules)
    print(f"✅ Set {container} max={maxn}. (schema: {RULES_PATH})")


def main():
    p = argparse.ArgumentParser(prog="mm", description="Queue/Stack/Quick personal scheduler")
    sub = p.add_subparsers(dest="cmd", required=True)

    a = sub.add_parser("add")
    a.add_argument("task", nargs="+")
    a.add_argument("-p", "--priority", action="store_true", help="push to interrupt stack")
    a.add_argument("-q", "--quick", action="store_true", help="add to quick queue")
    a.set_defaults(func=cmd_add)

    sub.add_parser("next").set_defaults(func=cmd_next)
    sub.add_parser("peek").set_defaults(func=cmd_peek)

    d = sub.add_parser("done")
    d.add_argument("id", nargs="?", type=int, default=None)
    d.set_defaults(func=cmd_done)

    bl = sub.add_parser("block")
    bl.add_argument("reason", nargs="*", default=None, help="why it's stuck, e.g. mm block waiting on API")
    bl.set_defaults(func=cmd_block)

    ub = sub.add_parser("unblock")
    ub.add_argument("id", type=int)
    ub.add_argument("--front", action="store_true", help="also jump it to the front of the queue")
    ub.set_defaults(func=cmd_unblock)

    sp = sub.add_parser("suspend")
    sp.add_argument("id", nargs="?", type=int, default=None)
    sp.set_defaults(func=cmd_suspend)

    rs = sub.add_parser("resume")
    rs.add_argument("id", nargs="?", type=int, default=None)
    rs.set_defaults(func=cmd_resume)

    mv = sub.add_parser("move")
    mv.add_argument("id", type=int)
    mv.add_argument("dest", choices=["queue", "stack", "quick"])
    mv.add_argument("--front", action="store_true", help="if moving into queue, jump to the front")
    mv.set_defaults(func=cmd_move)

    r = sub.add_parser("rm")
    r.add_argument("id", type=int)
    r.set_defaults(func=cmd_rm)

    e = sub.add_parser("edit")
    e.add_argument("id", type=int)
    e.add_argument("text", nargs="+")
    e.set_defaults(func=cmd_edit)

    nt = sub.add_parser("note")
    nt.add_argument("id", type=int)
    nt.add_argument("text", nargs="+")
    nt.set_defaults(func=cmd_note)

    fd = sub.add_parser("find")
    fd.add_argument("query", nargs="+")
    fd.set_defaults(func=cmd_find)

    sub.add_parser("undo").set_defaults(func=cmd_undo)
    sub.add_parser("flush-quick").set_defaults(func=cmd_flush_quick)
    sub.add_parser("status").set_defaults(func=cmd_status)
    sub.add_parser("stats").set_defaults(func=cmd_stats)
    sub.add_parser("review").set_defaults(func=cmd_stats)
    sub.add_parser("session").set_defaults(func=cmd_session)

    ar = sub.add_parser("archive")
    ar.add_argument("scope", nargs="?", choices=["today"], default=None)
    ar.set_defaults(func=cmd_archive)

    ex = sub.add_parser("export")
    ex.add_argument("format", choices=["json", "md", "csv"], nargs="?", default="json")
    ex.set_defaults(func=cmd_export)

    st = sub.add_parser("start")
    st.add_argument("label", nargs="*", default=None)
    st.set_defaults(func=cmd_start)

    sub.add_parser("stop").set_defaults(func=cmd_stop)

    lg = sub.add_parser("log")
    lg.add_argument("n", nargs="?", type=int, default=None)
    lg.set_defaults(func=cmd_log)

    ob = sub.add_parser("onboard", help="seed today's queue from mm.rules.json (idempotent per day)")
    ob.add_argument("-n", "--count", type=int, default=None, help="override daily_units just for today")
    ob.set_defaults(func=cmd_onboard)

    bk = sub.add_parser("book")
    bk_sub = bk.add_subparsers(dest="book_cmd", required=True)

    bka = bk_sub.add_parser("add")
    bka.add_argument("title", nargs="+")
    bka.add_argument("pages", type=int)
    bka.add_argument("-g", "--group", default=None, help="tag books to always onboard together, e.g. same course")
    bka.set_defaults(func=cmd_book_add)

    bkp = bk_sub.add_parser("progress")
    bkp.add_argument("id", type=int)
    bkp.add_argument("pages", type=int)
    bkp.set_defaults(func=cmd_book_progress)

    bkd = bk_sub.add_parser("done", help="mark a book fully finished directly, no page count needed")
    bkd.add_argument("id", type=int)
    bkd.set_defaults(func=cmd_book_done)

    bkl = bk_sub.add_parser("list")
    bkl.set_defaults(func=cmd_book_list)

    bks = bk_sub.add_parser("sync", help="reconcile books_config.json (hand-edited) into tracked state")
    bks.set_defaults(func=cmd_book_sync)

    bkr = bk_sub.add_parser("rm")
    bkr.add_argument("id", type=int)
    bkr.set_defaults(func=cmd_book_rm)

    ru = sub.add_parser("rules", help="inspect the unified rules engine")
    ru_sub = ru.add_subparsers(dest="rules_cmd", required=True)
    ru_sub.add_parser("show", help="print today's compiled plan without changing anything").set_defaults(func=cmd_rules_show)
    ru_sub.add_parser("validate", help="check the schema for errors").set_defaults(func=cmd_rules_validate)

    bg = sub.add_parser("backlog", help="view/promote items parked over capacity")
    bg.add_argument("--promote", action="store_true", help="pull backlog items into the queue as space allows")
    bg.set_defaults(func=cmd_backlog)

    cp = sub.add_parser("capacity", help="show or set per-queue maximums")
    cp.add_argument("container", nargs="?", choices=["queue", "stack", "quick"], default=None)
    cp.add_argument("max", nargs="?", type=int, default=None)
    cp.set_defaults(func=cmd_capacity)

    args = p.parse_args()
    with Lock():
        state = load()
        args.func(state, args)
        save(state)


if __name__ == "__main__":
    main()
