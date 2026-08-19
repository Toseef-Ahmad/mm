"""Items, gates, selection. The physics of the queue — not the verbs."""
from datetime import datetime, timezone, date, timedelta

from .books import find_book, load_books
from .state import log_event
from .util import accent, bold, dim, good, now_iso, today_str, warn


def new_item(state, text, gate=False, dominant=False, track=None, rule_id=None,
             ref=None, group=None, habit=None, habit_due=None, habit_type=None, weight=None):
    item = {"id": state["next_id"], "text": text, "added_at": now_iso()}
    if dominant:
        gate = True
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
    if habit:
        item["habit"] = habit
    if habit_due:
        item["habit_due"] = habit_due
    if habit_type:
        item["habit_type"] = habit_type
    if weight:
        item["weight"] = weight
    state["next_id"] += 1
    return item


def is_gate_item(item):
    return bool(item.get("gate"))


def has_open_gate(state):
    """A suspended gate stops gating (you chose to park it)."""
    return any(is_gate_item(it) and not it.get("suspended") for it in state["queue"])


def gate_progress_today(state):
    today = today_str()
    closed = sum(1 for t in state["archive"]
                 if is_gate_item(t) and t.get("done_at", "").startswith(today))
    open_ = sum(1 for it in state["queue"]
                if is_gate_item(it) and not it.get("suspended"))
    return closed, open_


def streak_length(days, upto):
    dayset = set(days)
    d = date.fromisoformat(upto)
    n = 0
    while d.isoformat() in dayset:
        n += 1
        d -= timedelta(days=1)
    return n


def reward_check(state):
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
    from .config import load_rules
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
    """Interrupt stack always wins. While any gate is open, non-gate queue
    work is unreachable. That hard block is the anti-procrastination mechanism."""
    for i in range(len(state["stack"]) - 1, -1, -1):
        it = state["stack"][i]
        if not it.get("blocked") and not it.get("suspended"):
            return "stack", i, it
    gate_mode = has_open_gate(state)
    for i, it in enumerate(state["queue"]):
        if it.get("blocked") or it.get("suspended"):
            continue
        if gate_mode and not is_gate_item(it):
            continue
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


def item_tag(item, books_data=None, locked=False):
    states = []
    if item.get("blocked"):
        states.append(f"blocked: {item['blocked_reason']}" if item.get("blocked_reason") else "blocked")
    if item.get("suspended"):
        states.append("suspended")
    if locked:
        states.append("gate-locked")
    return dim("  · " + ", ".join(states)) if states else ""


def fmt_line(item, active=False, books_data=None, locked=False):
    """locked: sits in the queue but a gate makes it unreachable right now."""
    marker = accent("→") if active else " "
    idcol = dim(f"{item['id']:>2}")
    text = dim(item["text"]) if locked else item["text"]
    return f"  {marker} {idcol}  {text}{item_tag(item, books_data, locked)}"


def leading_gate_count(queue):
    count = 0
    for item in queue:
        if is_gate_item(item):
            count += 1
        else:
            break
    return count


def book_gate_ready(item):
    """Paged books close by reading. Checklist books (pages=0) close with mm done."""
    if item.get("track") != "books" or item.get("ref") is None:
        return True, None
    book = find_book(load_books(), item["ref"])
    if book is None or book["status"] == "done":
        return True, book
    if not book.get("pages"):
        return True, book
    logged_today = book.get("last_progress_at", "").startswith(today_str())
    return logged_today, book
