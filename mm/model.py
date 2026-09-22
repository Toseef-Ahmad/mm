"""Items and selection. Stack preempts queue. No config, no gates."""
from datetime import datetime, timezone

from .util import accent, dim, now_iso


def new_item(state, text):
    item = {"id": state["next_id"], "text": text, "added_at": now_iso()}
    state["next_id"] += 1
    return item


def find_item(state, item_id, containers=("stack", "queue", "quick")):
    for container in containers:
        items = state[container]
        idx = next((i for i, it in enumerate(items) if it["id"] == item_id), None)
        if idx is not None:
            return container, idx, items[idx]
    return None, None, None


def find_active(state):
    """Interrupt stack first (top = last). Then the queue, front to back.
    Blocked and suspended items are skipped."""
    for i in range(len(state["stack"]) - 1, -1, -1):
        it = state["stack"][i]
        if not it.get("blocked") and not it.get("suspended"):
            return "stack", i, it
    for i, it in enumerate(state["queue"]):
        if not it.get("blocked") and not it.get("suspended"):
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


def item_tag(item):
    states = []
    if item.get("blocked"):
        states.append(f"blocked: {item['blocked_reason']}" if item.get("blocked_reason") else "blocked")
    if item.get("suspended"):
        states.append("suspended")
    return dim("  · " + ", ".join(states)) if states else ""


def fmt_line(item, active=False):
    marker = accent("→") if active else " "
    idcol = dim(f"{item['id']:>2}")
    return f"  {marker} {idcol}  {item['text']}{item_tag(item)}"
