"""Runtime verbs. Nothing appears unless the user added it."""
import csv
import io
import json
import sys
from datetime import datetime

from .model import (
    elapsed_str, find_active, find_item, fmt_line, item_tag,
    mark_active, new_item,
)
from .state import log_event, snapshot
from .util import bold, dim, good, now_iso, today_str, warn


def cmd_add(state, args):
    text = " ".join(args.task).strip()
    if not text:
        print("Nothing to add — empty task text.", file=sys.stderr)
        return
    snapshot(state)
    item = new_item(state, text)
    if args.priority:
        state["stack"].append(item)
        log_event(state, f"pushed to interrupt stack: [{item['id']}] {text}")
        print(f"  {warn('!')} interrupt  {dim(str(item['id']))}  {text}")
    elif args.quick:
        state["quick"].append(item)
        log_event(state, f"added to quick queue: [{item['id']}] {text}")
        print(f"  {dim('+')} quick  {dim(str(item['id']))}  {text}")
    else:
        state["queue"].append(item)
        log_event(state, f"enqueued: [{item['id']}] {text}")
        print(f"  {good('+')} queued  {dim(str(item['id']))}  {text}")


def cmd_next(state, _args):
    kind, _idx, item = find_active(state)
    if item:
        mark_active(state, item)
        el = elapsed_str(state["active"]["started_at"])
        note = warn("interrupt") if kind == "stack" else dim(f"{el} active")
        print(f"\n{fmt_line(item, active=True)}   {note}\n")
    else:
        state["active"] = None
        stuck_n = sum(1 for it in state["stack"] + state["queue"]
                      if it.get("blocked") or it.get("suspended"))
        if stuck_n:
            print(f"\n  {dim('nothing active —')} {stuck_n} blocked/suspended {dim('(mm status)')}\n")
        else:
            print(f"\n  {good('all clear')} {dim('— add something: mm add \"…\"')}\n")
    if state["quick"]:
        print(dim(f"  {len(state['quick'])} quick waiting — flush at a checkpoint (mm flush-quick)"))


def cmd_peek(state, _args):
    kind, _idx, item = find_active(state)
    if item:
        started = state["active"]["started_at"] if (state["active"] and state["active"]["id"] == item["id"]) else None
        el = elapsed_str(started) if started else "not started"
        note = warn("interrupt") if kind == "stack" else dim(el)
        print(f"\n{fmt_line(item, active=True)}   {note}")
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

    if target_id is None:
        container, idx, item = find_active(state)
        if item is None:
            state["_snapshots"].pop()
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
        state["stack"].insert(0, item)
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
        items.append(item)
    elif container == "queue" and args.front:
        items.pop(idx)
        items.insert(0, item)
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
    if getattr(args, "all", False):
        items = [it for c in ("stack", "queue") for it in state[c] if it.get("suspended")]
        if not items:
            state["_snapshots"].pop()
            print("Nothing suspended.")
            return
        for item in items:
            item["suspended"] = False
            item.pop("suspended_at", None)
            log_event(state, f"resumed: [{item['id']}] {item['text']}")
        print(f"▶️  Resumed {len(items)} item(s)")
        return
    if args.id is not None:
        container, idx, item = find_item(state, args.id, containers=("stack", "queue"))
        if item is None or not item.get("suspended"):
            state["_snapshots"].pop()
            print(f"No suspended item with id {args.id} found.")
            return
    else:
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


def cmd_status(state, _args):
    _kind, _idx, active = find_active(state)
    active_id = active["id"] if active else None

    def section(title, items):
        print(f"  {bold(title)}  {dim(str(len(items)))}")
        if not items:
            print(dim("     —"))
        for t in items:
            print(fmt_line(t, active=(t["id"] == active_id)))
        print()

    print()
    section("interrupt", list(reversed(state["stack"])))
    section("queue", state["queue"])
    section("quick", state["quick"])


def cmd_stats(state, _args):
    today = today_str()
    done_today = [t for t in state["archive"] if t.get("done_at", "").startswith(today)]
    added_today = [e for e in state["log"] if e["ts"].startswith(today) and
                   (e["event"].startswith("enqueued") or e["event"].startswith("pushed")
                    or e["event"].startswith("added to quick"))]
    blocked_now = sum(1 for t in state["stack"] + state["queue"] if t.get("blocked"))
    suspended_now = sum(1 for t in state["stack"] + state["queue"] if t.get("suspended"))
    open_now = len(state["queue"]) + len(state["stack"])
    print(f"\n  {bold(today)}")
    print(f"    {dim('done')}       {good(str(len(done_today)))}")
    print(f"    {dim('added')}      {len(added_today)}")
    print(f"    {dim('blocked')}    {blocked_now}")
    print(f"    {dim('suspended')}  {suspended_now}")
    print(f"    {dim('open')}       {open_now} {dim('queue+stack')} · {len(state['quick'])} {dim('quick')}\n")


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
    for container in ("stack", "queue", "quick"):
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
    else:
        print("| id | text | container | status |")
        print("|----|------|-----------|--------|")
        for r in rows:
            print(f"| {r['id']} | {r['text']} | {r['container']} | {r['status']} |")


def cmd_log(state, args):
    n = args.n or 10
    for entry in state["log"][-n:]:
        print(f"{entry['ts']}  {entry['event']}")
