"""Command handlers. One function per verb. Physics live in model.py."""
import csv
import io
import json
import os
import sys
from datetime import datetime

from .books import load_books
from .config import (
    capacity_for, capacity_policy, compile_rules, default_capacity,
    load_rules, promote_backlog, save_rules, validate_rules,
)
from .model import (
    book_gate_ready, elapsed_str, find_active, find_item, fmt_line, gate_progress_today,
    has_open_gate, is_gate_item, item_tag, leading_gate_count, mark_active,
    new_item, reward_check, streak_length,
)
from .paths import P
from .state import log_event, snapshot
from .util import accent, bold, dim, good, now_iso, today_str, today_weekday_key, warn


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

    def refuse_unread_book(item, book):
        state["_snapshots"].pop()  # nothing changed, don't waste an undo slot
        print(f"\n  {warn('✗ not closed')}  {item['text']}")
        print(f"  No pages logged today for '{book['title']}' — a book gate closes by reading, not by ticking.")
        print(f"    log pages:  mm book progress {book['id']} <pages>")
        print(f"    or park it: mm suspend {item['id']}   {dim('(honest — parked, not closed)')}\n")

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
        ok, book = book_gate_ready(item)
        if not ok:
            refuse_unread_book(item, book)
            return
        finish(container, idx, item)
        cmd_next(state, args)
        return
    container, idx, item = find_item(state, target_id, containers=("stack", "queue"))
    if item is not None:
        ok, book = book_gate_ready(item)
        if not ok:
            refuse_unread_book(item, book)
            return
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



def cmd_onboard(state, args):
    today = today_str()
    rules = load_rules()
    strict = rules.get("onboard", {}).get("strict_gate", True)
    force = bool(getattr(args, "force", False))
    again = bool(getattr(args, "again", False))

    # Hard gate: refuse to start a new day while dominant/gate work is still open.
    # --force is the testing/unstick hatch; default behaviour stays strict.
    if strict and not force and has_open_gate(state):
        open_gates = [it for it in state["queue"] if is_gate_item(it) and not it.get("suspended")]
        headline = warn("Can't onboard yet")
        subtext = dim("— finish (or suspend) yesterday's gate work first:")
        print(f"\n  {headline} {subtext}\n")
        for it in open_gates:
            print(fmt_line(it))
        print(f"    {dim('unlock onboard:')}  mm reset")
        print(f"    {dim('park leftovers:')}  mm reset --park-gates")
        print(f"    {dim('seed anyway:')}     mm onboard --force\n")
        return

    if state.get("onboarded_date") == today and not force and not again:
        print(f"\n  {dim('already onboarded today — nothing to re-add')}")
        print(f"    {dim('re-seed today:')}  mm onboard --again")
        print(f"    {dim('ignore gates:')}   mm onboard --force\n")
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


def cmd_reset(state, args):
    """Clear the per-day onboard lock. Does not touch the queue unless you
    pass --park-gates (suspend leftovers) or --drop-gates (remove them).
    Archive is never touched."""
    snapshot(state)
    drop = bool(getattr(args, "drop_gates", False))
    park = bool(getattr(args, "park_gates", False)) or drop
    parked, dropped, kept = [], [], []
    if park:
        for it in state["queue"]:
            if is_gate_item(it) and not it.get("suspended"):
                if drop:
                    dropped.append(it)
                    log_event(state, f"reset dropped gate: [{it['id']}] {it['text']}")
                    continue
                it["suspended"] = True
                it["suspended_at"] = now_iso()
                parked.append(it)
                log_event(state, f"reset parked gate: [{it['id']}] {it['text']}")
            kept.append(it)
        state["queue"] = kept
        if state.get("active"):
            aid = state["active"]["id"]
            live = next((it for it in state["queue"]
                         if it["id"] == aid and not it.get("suspended")), None)
            if live is None:
                state["active"] = None
    state["onboarded_date"] = None
    print(f"\n  {bold('reset')}  {dim('onboard lock cleared')}")
    if parked:
        print(dim(f"  parked {len(parked)} leftover gate(s) — mm resume --all to bring them back"))
    if dropped:
        print(dim(f"  dropped {len(dropped)} leftover gate(s) from the queue (not archived)"))
    if not park:
        print(dim("  queue unchanged — leftover gates still block onboard unless you mm onboard --force"))
        print(dim("  park them:  mm reset --park-gates"))
    print(f"    {dim('next:')} mm onboard\n")


# ---------- rules / capacity / backlog commands ----------

def cmd_rules_show(state, _args):
    rules = load_rules()
    weekday = today_weekday_key()
    source = P.rules if P.rules_kind else f"(none yet — create {P.rules_toml})"
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
    errors, warnings = validate_rules(load_rules())
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


def cmd_rules_strict(_state, args):
    val = (args.value or "").strip().lower()
    on = val in ("on", "true", "1", "yes")
    off = val in ("off", "false", "0", "no")
    if not on and not off:
        print("Usage: mm rules strict on|off", file=sys.stderr)
        return
    rules = load_rules()
    rules.setdefault("onboard", {})["strict_gate"] = on
    save_rules(rules)
    print(f"  {good('✓')} strict_gate {'on' if on else 'off'}")


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
    print(f"✅ Set {container} max={maxn}. (schema: {P.rules})")


def cmd_init(_state, args):
    """Write a starter mm.toml if none exists. Never overwrites without --force."""
    P.ensure()
    dest = P.rules_toml
    if os.path.exists(dest) and not getattr(args, "force", False):
        print(f"Already have {dest} — pass --force to replace.")
        return
    example = os.path.join(os.path.dirname(__file__), "..", "examples", "mm.toml")
    if os.path.exists(example):
        with open(example, encoding="utf-8") as f:
            body = f.read()
    else:
        body = dumps_starter()
    with open(dest, "w", encoding="utf-8") as f:
        f.write(body)
    print(f"  {good('✓')} wrote {dest}")
    print(dim("    edit tracks, then: mm rules validate && mm onboard"))


def dumps_starter():
    from .config import dumps_toml
    return dumps_toml({
        "version": 2,
        "onboard": {"strict_gate": True, "order": ["learn"]},
        "capacity": default_capacity(),
        "tracks": {
            "learn": {
                "type": "rotation",
                "count": 1,
                "dominant": True,
                "position": "gate",
                "label": "{value}",
                "items": ["One focused session on the thing that matters"],
            },
        },
        "rewards": {"daily": "The rest of the evening is yours."},
    })


