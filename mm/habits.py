"""Repeating items. Not a special type — a book, a walk, a course: same object.

User owns the list in mm.toml (`[[habits]]`). Tool owns progress in
habits.json (streak, missed, last done). Repeat is a gap in days; a
3-day habit does not break streak on the two days it was never due.
"""
from __future__ import annotations

import copy
import json
import os
import sys
import tempfile
from datetime import date, timedelta

from .paths import P
from .util import WEEKDAY_KEYS, accent, bold, dim, good, today_str, warn

CONTAINERS = ("stack", "queue", "quick")
DESTINATIONS = ("queue", "stack", "quick")
PLACES = ("gate", "front", "back")
SETTABLE = (
    "name", "description", "type", "repeat", "enabled", "archived",
    "position", "place", "gate", "weight", "order", "tags", "days", "obsidian",
)

EMPTY_PROGRESS = {"habits": {}}


def _truthy(v, default=True):
    if v is None:
        return default
    if isinstance(v, str):
        return v.strip().lower() in ("1", "true", "yes", "on")
    return bool(v)


def _as_list(value):
    if value is None or value == "":
        return []
    if isinstance(value, list):
        return [str(x).strip() for x in value if str(x).strip()]
    return [str(value).strip()]


def _day(s):
    return date.fromisoformat(s) if isinstance(s, str) else s


def normalize_habit(raw, index=0):
    """One config row → a strict habit dict. Bad rows return (None, warning)."""
    if not isinstance(raw, dict):
        return None, f"habit #{index + 1} is not an object"
    name = str(raw.get("name") or raw.get("title") or "").strip()
    if not name:
        return None, f"habit #{index + 1} has no name"
    try:
        repeat = int(raw.get("repeat") or 1)
    except (TypeError, ValueError):
        return None, f"habit '{name}' repeat must be an integer"
    if repeat < 1:
        return None, f"habit '{name}' repeat must be >= 1"

    position = str(raw.get("position") or "queue").strip().lower()
    place = str(raw.get("place") or "").strip().lower()
    gate = _truthy(raw.get("gate", raw.get("dominant")), default=False)
    if position == "gate":
        position, place, gate = "queue", "gate", True
    elif position in ("front", "back"):
        place, position = position, "queue"
    if position not in DESTINATIONS:
        return None, f"habit '{name}' position must be queue|stack|quick"
    if not place:
        place = "gate" if gate else "back"
    if place not in PLACES:
        return None, f"habit '{name}' place must be gate|front|back"
    if place == "gate":
        gate = True

    tags = _as_list(raw.get("tags"))
    htype = str(raw.get("type") or (tags[0] if tags else "habit")).strip().lower()
    days = _as_list(raw.get("days"))
    for d in days:
        if d not in WEEKDAY_KEYS:
            return None, f"habit '{name}' days must be Mon..Sun (got {d!r})"

    try:
        weight = int(raw.get("weight", raw.get("points", 1)) or 1)
    except (TypeError, ValueError):
        return None, f"habit '{name}' weight must be an integer"

    order = raw.get("order")
    if order is None or order == "":
        order = None
    else:
        try:
            order = int(order)
        except (TypeError, ValueError):
            return None, f"habit '{name}' order must be an integer"

    habit = {
        "name": name,
        "description": str(raw.get("description") or "").strip(),
        "type": htype,
        "tags": tags,
        "repeat": repeat,
        "enabled": _truthy(raw.get("enabled"), default=True),
        "archived": _truthy(raw.get("archived"), default=False),
        "position": position,
        "place": place,
        "gate": gate,
        "weight": weight,
        "order": order,
        "days": days,
        "obsidian": str(raw.get("obsidian") or "").strip(),
    }
    return habit, None


def load_declared(rules=None):
    """Habits from the active config. Tracks stay valid; this is the new list."""
    if rules is None:
        from .config import load_rules
        rules = load_rules()
    raw = rules.get("habits") or []
    if isinstance(raw, dict):
        rows = []
        for name, body in raw.items():
            row = dict(body or {})
            row.setdefault("name", name)
            rows.append(row)
        raw = rows
    if not isinstance(raw, list):
        print("⚠️  habits must be an array of objects; ignoring.", file=sys.stderr)
        return []
    out, seen = [], set()
    for i, row in enumerate(raw):
        habit, err = normalize_habit(row, i)
        if err:
            print(f"⚠️  {err}; skipping.", file=sys.stderr)
            continue
        key = habit["name"].lower()
        if key in seen:
            print(f"⚠️  duplicate habit '{habit['name']}'; skipping.", file=sys.stderr)
            continue
        seen.add(key)
        out.append(habit)
    return out


def find_declared(name, rules=None):
    needle = name.strip().lower()
    for h in load_declared(rules):
        if h["name"].lower() == needle:
            return h
    return None


def load_progress():
    P.ensure()
    if not os.path.exists(P.habits):
        return copy.deepcopy(EMPTY_PROGRESS)
    try:
        with open(P.habits, encoding="utf-8") as f:
            data = json.load(f)
        data.setdefault("habits", {})
        return data
    except (json.JSONDecodeError, OSError) as e:
        backup = P.habits + f".corrupt-{int(date.today().toordinal())}"
        try:
            os.replace(P.habits, backup)
        except OSError:
            pass
        print(f"⚠️  Habits progress was corrupted ({e}). Backed up to {backup}.", file=sys.stderr)
        return copy.deepcopy(EMPTY_PROGRESS)


def save_progress(data):
    P.ensure()
    fd, tmp = tempfile.mkstemp(dir=P.dir, prefix=".habits-", suffix=".tmp")
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=2, ensure_ascii=False)
            f.write("\n")
            f.flush()
            os.fsync(f.fileno())
        os.replace(tmp, P.habits)
    finally:
        if os.path.exists(tmp):
            os.remove(tmp)


def slot_for(progress, name):
    slots = progress.setdefault("habits", {})
    slot = slots.setdefault(name, {
        "anchor": None,
        "streak": 0,
        "best_streak": 0,
        "points": 0,
        "last_done": None,
        "last_missed": None,
        "history": {},
    })
    slot.setdefault("history", {})
    return slot


def _weekday(d):
    return WEEKDAY_KEYS[_day(d).weekday()]


def is_due_on(habit, day, anchor):
    """True iff `day` is an occurrence, given repeat and optional weekday filter.

    Gap days are not due. A repeat=3 habit due Mon is not due Tue/Wed — those
    days must not break the streak.
    """
    day = _day(day)
    anchor = _day(anchor)
    if day < anchor:
        return False
    days = habit.get("days") or []
    repeat = max(1, int(habit.get("repeat") or 1))
    if days:
        if _weekday(day) not in days:
            return False
        n = 0
        cursor = anchor
        while cursor <= day:
            if _weekday(cursor) in days:
                if cursor == day:
                    return n % repeat == 0
                n += 1
            cursor += timedelta(days=1)
        return False
    return (day - anchor).days % repeat == 0


def due_dates_through(habit, anchor, until):
    until = _day(until)
    anchor = _day(anchor)
    out = []
    cursor = anchor
    while cursor <= until:
        if is_due_on(habit, cursor, anchor):
            out.append(cursor.isoformat())
        cursor += timedelta(days=1)
    return out


def previous_due(habit, anchor, before):
    before = _day(before)
    cursor = before - timedelta(days=1)
    anchor = _day(anchor)
    while cursor >= anchor:
        if is_due_on(habit, cursor, anchor):
            return cursor.isoformat()
        cursor -= timedelta(days=1)
    return None


def streak_from_history(habit, history, today, anchor):
    """Count consecutive done due-dates walking backward.

    Non-due days are skipped. A miss on a due day breaks it. Today's due
    date, if not yet resolved, is ignored (still in progress).
    """
    today = _day(today)
    anchor = _day(anchor)
    cursor = today
    if is_due_on(habit, today, anchor) and history.get(today.isoformat()) not in ("done", "missed"):
        prev = previous_due(habit, anchor, today)
        if prev is None:
            return 0
        cursor = _day(prev)
    n = 0
    while cursor >= anchor:
        if is_due_on(habit, cursor, anchor):
            result = history.get(cursor.isoformat())
            if result == "done":
                n += 1
            elif result == "missed":
                break
            # Unresolved (leftover still open) — skip, do not break.
        cursor -= timedelta(days=1)
    return n


def _item_matches_habit(item, name_l):
    if (item.get("habit") or "").lower() == name_l:
        return True
    text = (item.get("text") or "").lower()
    return text == name_l or text.startswith(name_l + " —") or text.startswith(name_l + " -")


def iter_open_habit_items(state, name):
    """Every open occurrence of a habit, including yesterday leftovers."""
    name_l = name.lower()
    for container in CONTAINERS + ("backlog",):
        for it in state.get(container, []):
            if _item_matches_habit(it, name_l):
                yield container, it


def open_habit_item(state, name, due=None):
    """First open occurrence. Pass due=YYYY-MM-DD to pick that day's item."""
    for container, it in iter_open_habit_items(state, name):
        if due is None or it.get("habit_due") == due:
            return container, it
    return None, None


def _stamp_open_habit(item, habit, today):
    """Attach habit metadata to a leftover; keep its original due date."""
    item["habit"] = habit["name"]
    item["habit_type"] = habit.get("type")
    item["weight"] = habit.get("weight") or 1
    if not item.get("habit_due"):
        added = (item.get("added_at") or "")[:10]
        if added and added < today:
            item["habit_due"] = added
        else:
            item["habit_due"] = today


def _item_text(habit):
    desc = habit.get("description") or ""
    if desc:
        return f"{habit['name']} — {desc}"
    return habit["name"]


def _make_item(state, habit, due):
    from .model import new_item
    gate = bool(habit.get("gate") or habit.get("place") == "gate")
    return new_item(
        state, _item_text(habit),
        gate=gate, dominant=gate,
        track=habit.get("type") or "habit",
        habit=habit["name"], habit_due=due,
        habit_type=habit.get("type"), weight=habit.get("weight") or 1,
    )


def _place_item(state, rules, item, habit, added, backlogged, skipped):
    from .config import capacity_policy
    from .model import leading_gate_count
    dest = habit["position"]
    if dest == "stack":
        policy, maxn, _ = capacity_policy(state, rules, "stack")
        if policy == "reject":
            skipped.append(habit["name"] + " (stack full)")
            return
        state["stack"].append(item)
        added.append(item)
        return
    if dest == "quick":
        policy, maxn, _ = capacity_policy(state, rules, "quick")
        if policy == "reject":
            skipped.append(habit["name"] + " (quick full)")
            return
        if policy == "warn":
            print(f"⚠️  quick at {len(state['quick'])}/{maxn} — adding {habit['name']}.", file=sys.stderr)
        state["quick"].append(item)
        added.append(item)
        return
    # queue
    place = habit.get("place") or "back"
    if place == "gate" or habit.get("gate"):
        item["gate"] = True
        insert_at = leading_gate_count(state["queue"])
        state["queue"][insert_at:insert_at] = [item]
        added.append(item)
        return
    policy, maxn, _ = capacity_policy(state, rules, "queue")
    if policy == "reject":
        skipped.append(habit["name"] + " (queue full)")
        return
    if policy == "backlog":
        item["_from"] = "queue"
        state["backlog"].append(item)
        backlogged.append(item)
        return
    if policy == "warn":
        print(f"⚠️  queue at {len(state['queue'])}/{maxn} — adding {habit['name']}.", file=sys.stderr)
    if place == "front":
        state["queue"].insert(leading_gate_count(state["queue"]), item)
    else:
        state["queue"].append(item)
    added.append(item)


def _drop_stale_habit_items(state, name, today):
    """Remove leftover occurrences from a previous day. Today stays."""
    dropped = []
    for container, item in list(iter_open_habit_items(state, name)):
        due = item.get("habit_due") or today
        if due < today:
            state[container].remove(item)
            dropped.append(item)
    return dropped


def collapse_duplicate_habits(state):
    """One open item per habit. Keep a single row if anything doubled."""
    for container in CONTAINERS + ("backlog",):
        items = list(state.get(container) or [])
        keep_idx = {}
        drop = set()
        for i, it in enumerate(items):
            name = (it.get("habit") or "").lower()
            if not name:
                continue
            due = it.get("habit_due") or "9999-99-99"
            iid = int(it.get("id") or 0)
            if name not in keep_idx:
                keep_idx[name] = i
                continue
            j = keep_idx[name]
            other = items[j]
            other_due = other.get("habit_due") or "9999-99-99"
            other_id = int(other.get("id") or 0)
            if due < other_due or (due == other_due and iid < other_id):
                drop.add(j)
                keep_idx[name] = i
            else:
                drop.add(i)
        if drop:
            state[container] = [it for i, it in enumerate(items) if i not in drop]


def _declared_rank(rules=None):
    """order (lower first) when set; otherwise weight (higher first)."""
    wmap, omap = {}, {}
    for h in load_declared(rules):
        key = h["name"].lower()
        wmap[key] = int(h.get("weight") or 0)
        if h.get("order") is not None:
            omap[key] = int(h["order"])
    return wmap, omap


def _item_weight(item, wmap):
    name = (item.get("habit") or "").lower()
    if name and name in wmap:
        return int(wmap[name])
    return int(item.get("weight") or 0)


def _sort_key(item, index, wmap, omap):
    name = (item.get("habit") or "").lower()
    weight = _item_weight(item, wmap)
    if name in omap:
        return (0, omap[name], -weight, index)
    return (1, 0, -weight, index)


def reorder_by_weight(state, rules=None, today=None):
    """Queue order: explicit `order` (1 = front), then higher weight.

    File order is only a tie-breaker. Real interrupts stay on top of the
    stack; ordered habit-stack items sit nearer the top.
    """
    wmap, omap = _declared_rank(rules)
    for container in CONTAINERS + ("backlog",):
        for it in state.get(container, []):
            name = (it.get("habit") or "").lower()
            if name in wmap:
                it["weight"] = wmap[name]
            if name in omap:
                it["order"] = omap[name]

    def sort_queue(items):
        indexed = list(enumerate(items))
        indexed.sort(key=lambda p: _sort_key(p[1], p[0], wmap, omap))
        return [it for _, it in indexed]

    q = state.get("queue") or []
    habits_q = [it for it in q if it.get("habit")]
    other_q = [it for it in q if not it.get("habit")]
    state["queue"] = sort_queue(habits_q) + other_q

    stack = state.get("stack") or []
    habit_s = [it for it in stack if it.get("habit")]
    interrupts = [it for it in stack if not it.get("habit")]
    # LIFO: first in queue-order sits nearest the top.
    state["stack"] = list(reversed(sort_queue(habit_s))) + interrupts

    quick = state.get("quick") or []
    habit_k = [it for it in quick if it.get("habit")]
    other_k = [it for it in quick if not it.get("habit")]
    state["quick"] = sort_queue(habit_k) + other_k
    return wmap


def ensure_due_habits(state, rules=None, today=None, quiet=True):
    """Each day: fresh due items from mm.toml. No leftover copies.

    Unfinished previous due-days are marked missed (streak resets).
    Done days keep the streak. Same habit is never queued twice.
    """
    from .config import load_rules
    from .state import log_event

    if rules is None:
        rules = load_rules()
    today = today or today_str()
    today_d = _day(today)
    habits = [h for h in load_declared(rules) if h["enabled"] and not h["archived"]]
    if not habits:
        return [], [], [], []

    collapse_duplicate_habits(state)

    progress = load_progress()
    added, backlogged, skipped, missed = [], [], [], []
    yesterday = (today_d - timedelta(days=1)).isoformat()

    for habit in habits:
        slot = slot_for(progress, habit["name"])
        if not slot.get("anchor"):
            slot["anchor"] = today
        anchor = slot["anchor"]
        history = slot["history"]

        for _container, open_item in iter_open_habit_items(state, habit["name"]):
            _stamp_open_habit(open_item, habit, today)
        _drop_stale_habit_items(state, habit["name"], today)

        for due in due_dates_through(habit, anchor, yesterday):
            if history.get(due) in ("done", "missed"):
                continue
            history[due] = "missed"
            slot["last_missed"] = due
            slot["streak"] = 0
            missed.append((habit["name"], due))
            log_event(state, f"habit missed: {habit['name']} ({due})")

        opens = list(iter_open_habit_items(state, habit["name"]))
        open_today = any((it.get("habit_due") or today) == today for _c, it in opens)

        if not is_due_on(habit, today, anchor):
            slot["streak"] = streak_from_history(habit, history, today, anchor)
            slot["best_streak"] = max(int(slot.get("best_streak") or 0), int(slot.get("streak") or 0))
            continue
        if open_today:
            slot["streak"] = streak_from_history(habit, history, today, anchor)
            continue
        if history.get(today) == "done":
            slot["streak"] = streak_from_history(habit, history, today, anchor)
            continue
        if history.get(today) == "missed":
            continue

        item = _make_item(state, habit, today)
        _place_item(state, rules, item, habit, added, backlogged, skipped)
        if item in added or item in backlogged:
            log_event(state, f"habit due ({habit['type']}, {habit['position']}): [{item['id']}] {item['text']}")

        slot["streak"] = streak_from_history(habit, history, today, anchor)
        slot["best_streak"] = max(int(slot.get("best_streak") or 0), int(slot.get("streak") or 0))

    reorder_by_weight(state, rules, today=today)
    save_progress(progress)
    if not quiet:
        return added, backlogged, skipped, missed
    return added, backlogged, skipped, missed


def record_done(state, item, today=None):
    """Credit this occurrence's due date. Today's close counts today."""
    name = item.get("habit")
    if not name:
        return None
    today = today or today_str()
    habit = find_declared(name)
    progress = load_progress()
    slot = slot_for(progress, name)
    if not slot.get("anchor"):
        slot["anchor"] = item.get("habit_due") or today
    history = slot["history"]
    due = item.get("habit_due") or today
    history[due] = "done"
    slot["last_done"] = today
    slot["points"] = int(slot.get("points") or 0) + int(item.get("weight") or (habit or {}).get("weight") or 1)
    if habit:
        slot["streak"] = streak_from_history(habit, history, today, slot["anchor"])
        slot["best_streak"] = max(int(slot.get("best_streak") or 0), slot["streak"])
    else:
        slot["streak"] = int(slot.get("streak") or 0) + 1
        slot["best_streak"] = max(int(slot.get("best_streak") or 0), slot["streak"])
    save_progress(progress)
    from .state import log_event
    log_event(state, f"habit done: {name} streak {slot['streak']}")
    return slot


def record_undone(name, day=None):
    """Clear today's done so the habit can be queued again (Obsidian uncheck)."""
    day = day or today_str()
    progress = load_progress()
    slot = slot_for(progress, name)
    hist = slot.setdefault("history", {})
    if hist.get(day) != "done":
        return slot
    del hist[day]
    if slot.get("last_done") == day:
        dones = [d for d, v in hist.items() if v == "done"]
        slot["last_done"] = max(dones) if dones else None
    habit = find_declared(name)
    slot["points"] = max(0, int(slot.get("points") or 0) - int((habit or {}).get("weight") or 1))
    if habit:
        slot["streak"] = streak_from_history(habit, hist, day, slot.get("anchor") or day)
    else:
        slot["streak"] = max(0, int(slot.get("streak") or 0) - 1)
    save_progress(progress)
    return slot


def record_miss(name, today=None, drop_open=None):
    today = today or today_str()
    progress = load_progress()
    slot = slot_for(progress, name)
    slot["history"][today] = "missed"
    slot["last_missed"] = today
    slot["streak"] = 0
    save_progress(progress)
    if drop_open is not None:
        container, item = open_habit_item(drop_open, name, due=today)
        if item is None:
            container, item = open_habit_item(drop_open, name)
        if item is not None:
            drop_open[container].remove(item)
    return slot


def search_habits(query, rules=None):
    q = (query or "").strip().lower()
    hits = []
    for h in load_declared(rules):
        blob = " ".join([
            h["name"], h.get("description") or "", h.get("type") or "",
            " ".join(h.get("tags") or []), " ".join(h.get("days") or []),
            h.get("position") or "", h.get("obsidian") or "",
        ]).lower()
        if not q or q in blob:
            hits.append(h)
    return hits


def declared_to_raw(habit):
    """Config-shaped dict for writing back to mm.toml."""
    row = {
        "name": habit["name"],
        "type": habit["type"],
        "repeat": habit["repeat"],
        "enabled": 1 if habit["enabled"] else 0,
        "archived": 1 if habit["archived"] else 0,
        "position": habit["position"],
        "weight": habit["weight"],
    }
    if habit.get("description"):
        row["description"] = habit["description"]
    if habit.get("tags"):
        row["tags"] = habit["tags"]
    if habit.get("days"):
        row["days"] = habit["days"]
    if habit.get("obsidian"):
        row["obsidian"] = habit["obsidian"]
    if habit.get("order") is not None:
        row["order"] = habit["order"]
    if habit.get("gate") or habit.get("place") == "gate":
        row["gate"] = True
    if habit.get("place") and habit["place"] != ("gate" if habit.get("gate") else "back"):
        row["place"] = habit["place"]
    elif habit.get("place") == "front":
        row["place"] = "front"
    return row


def replace_declared(habits):
    from .config import load_rules, save_rules
    rules = load_rules()
    rules["habits"] = [declared_to_raw(h) for h in habits]
    save_rules(rules)
    return rules


def upsert_declared(habit):
    current = load_declared()
    found = False
    for i, h in enumerate(current):
        if h["name"].lower() == habit["name"].lower():
            current[i] = habit
            found = True
            break
    if not found:
        current.append(habit)
    replace_declared(current)
    return habit


def remove_declared(name):
    current = load_declared()
    kept = [h for h in current if h["name"].lower() != name.strip().lower()]
    if len(kept) == len(current):
        return False
    replace_declared(kept)
    return True


def parse_set_value(field, raw):
    raw = " ".join(raw) if isinstance(raw, list) else str(raw)
    raw = raw.strip()
    if field in ("enabled", "archived", "gate"):
        return _truthy(raw, default=False)
    if field == "order" and raw.lower() in ("", "none", "off", "clear"):
        return None  # back to weight ordering
    if field in ("repeat", "weight", "order"):
        return int(raw)
    if field in ("tags", "days"):
        parts = [p.strip() for p in raw.replace(",", " ").split() if p.strip()]
        if field == "days":
            for p in parts:
                key = p[:3].title()
                if key not in WEEKDAY_KEYS and p.title() not in WEEKDAY_KEYS:
                    raise ValueError(f"days must be Mon..Sun (got {p!r})")
            parts = [p[:3].title() if p[:3].title() in WEEKDAY_KEYS else p.title() for p in parts]
        return parts
    if field == "position":
        v = raw.lower()
        if v not in DESTINATIONS:
            raise ValueError("position must be queue|stack|quick")
        return v
    if field == "place":
        v = raw.lower()
        if v not in PLACES:
            raise ValueError("place must be gate|front|back")
        return v
    return raw


def _fmt_habit_line(habit, slot, today, due):
    mark = good("→") if due and habit["enabled"] and not habit["archived"] else (
        dim("·") if not habit["enabled"] or habit["archived"] else " "
    )
    flags = []
    if habit["archived"]:
        flags.append("archived")
    elif not habit["enabled"]:
        flags.append("off")
    if habit.get("gate"):
        flags.append("gate")
    flags.append(habit["position"])
    flags.append(f"w{habit.get('weight') or 1}")
    if habit.get("order") is not None:
        flags.append(f"#{habit['order']}")
    if habit["repeat"] == 1 and not habit.get("days"):
        cadence = "daily"
    elif habit.get("days"):
        cadence = f"every {habit['repeat']}× {'/'.join(habit['days'])}"
    else:
        cadence = f"every {habit['repeat']}d"
    last = slot.get("last_done") or "—"
    missed = slot.get("last_missed")
    miss = dim(f"  missed {missed}") if missed and missed >= (slot.get("last_done") or "") else ""
    extra = dim("  · " + " · ".join(flags))
    streak = slot.get("streak") or 0
    name = f"{habit['name']:<28}"
    htype = f"{habit['type']:<10}"
    cad = f"{cadence:<22}"
    return (
        f"  {mark} {name} {dim(htype)} {dim(cad)} "
        f"{dim('streak')} {bold(str(streak))}  {dim('last')} {last}{extra}{miss}"
    )


def cmd_habit_list(_state, args):
    today = today_str()
    q = " ".join(getattr(args, "query", []) or []).strip()
    type_f = getattr(args, "type", None)
    habits = search_habits(q) if q else load_declared()
    if type_f:
        type_f = type_f.strip().lower()
        habits = [h for h in habits if h["type"] == type_f or type_f in h.get("tags", [])]
    habits = sorted(habits, key=lambda h: (
        0 if h.get("order") is not None else 1,
        int(h["order"]) if h.get("order") is not None else 0,
        -int(h.get("weight") or 0),
        h["name"].lower(),
    ))
    if not habits:
        print("No habits. mm habit add NAME [--type book] [--repeat 1]")
        return
    progress = load_progress()
    print(f"\n  {bold('habits')}  {dim(str(len(habits)) + ' declared')}\n")
    for h in habits:
        slot = slot_for(progress, h["name"])
        anchor = slot.get("anchor") or today
        due = h["enabled"] and not h["archived"] and is_due_on(h, today, anchor)
        print(_fmt_habit_line(h, slot, today, due))
    print()


def cmd_habit_add(_state, args):
    name = " ".join(args.name).strip()
    if not name:
        print("Nothing to add — empty name.", file=sys.stderr)
        return
    if find_declared(name):
        print(f"'{name}' is already a habit. mm habit set {name} …", file=sys.stderr)
        return
    tags = [p.strip() for p in str(getattr(args, "tags", "") or "").replace(",", " ").split() if p.strip()]
    days = [p.strip() for p in str(getattr(args, "days", "") or "").replace(",", " ").split() if p.strip()]
    days = [(p[:3].title() if p[:3].title() in WEEKDAY_KEYS else p.title()) for p in days]
    raw = {
        "name": name,
        "description": getattr(args, "description", None) or "",
        "type": getattr(args, "type", None) or "habit",
        "repeat": getattr(args, "repeat", None) or 1,
        "position": getattr(args, "position", None) or "queue",
        "enabled": 1 if _truthy(getattr(args, "enabled", 1), default=True) else 0,
        "archived": 0,
        "weight": getattr(args, "weight", None) or 1,
        "order": getattr(args, "order", None),
        "gate": bool(getattr(args, "gate", False)),
        "tags": tags,
        "days": days,
        "obsidian": getattr(args, "obsidian", None) or "",
    }
    if getattr(args, "place", None):
        raw["place"] = args.place
    habit, err = normalize_habit(raw)
    if err:
        print(f"⚠️  {err}", file=sys.stderr)
        return
    upsert_declared(habit)
    from .obsidian import on_habit_changed
    on_habit_changed(habit)
    print(f"  {good('+')} habit  {habit['name']}  {dim(habit['type'] + ' · every ' + str(habit['repeat']) + 'd · ' + habit['position'])}")


def cmd_habit_set(state, args):
    name = args.name
    field = (args.field or "").strip().lower()
    if field not in SETTABLE:
        print(f"Unknown field '{field}'. One of: {', '.join(SETTABLE)}", file=sys.stderr)
        return
    habit = find_declared(name)
    if habit is None:
        print(f"No habit named '{name}'. mm habit list", file=sys.stderr)
        return
    try:
        value = parse_set_value(field, args.value)
    except (ValueError, TypeError) as e:
        print(f"⚠️  {e}", file=sys.stderr)
        return
    if field == "name":
        old = habit["name"]
        habit["name"] = str(value).strip()
        progress = load_progress()
        if old in progress["habits"]:
            progress["habits"][habit["name"]] = progress["habits"].pop(old)
            save_progress(progress)
    else:
        habit[field] = value
        if field == "place" and value == "gate":
            habit["gate"] = True
        if field == "gate" and value:
            habit["place"] = "gate"
    habit, err = normalize_habit(habit)
    if err:
        print(f"⚠️  {err}", file=sys.stderr)
        return
    current = load_declared()
    out = []
    replaced = False
    for h in current:
        if h["name"].lower() == name.strip().lower() or h["name"].lower() == habit["name"].lower():
            if not replaced:
                out.append(habit)
                replaced = True
            continue
        out.append(h)
    if not replaced:
        out.append(habit)
    replace_declared(out)
    if field in ("weight", "position", "gate", "place", "order"):
        reorder_by_weight(state)
    if field in ("obsidian", "name", "weight"):
        from .obsidian import on_habit_changed
        on_habit_changed(habit)
    extra = ""
    if field == "weight":
        extra = dim("  · higher weight goes first unless order is set")
    if field == "order":
        extra = dim("  · lower order goes first in the queue (1 = front)")
    print(f"  {good('✓')} {habit['name']}.{field} = {value}{extra}")


def cmd_habit_rm(_state, args):
    name = " ".join(args.name).strip() if isinstance(args.name, list) else str(args.name)
    if not remove_declared(name):
        print(f"No habit named '{name}'.", file=sys.stderr)
        return
    print(f"🗑  Removed habit {name}")


def cmd_habit_log(_state, args):
    name = " ".join(getattr(args, "name", []) or []).strip()
    progress = load_progress()
    today = today_str()
    names = [name] if name else [h["name"] for h in load_declared()]
    if name and name not in progress["habits"] and not find_declared(name):
        print(f"No habit named '{name}'.", file=sys.stderr)
        return
    for n in names:
        slot = progress.get("habits", {}).get(n) or slot_for(progress, n)
        hist = slot.get("history") or {}
        print(f"\n  {bold(n)}  {dim('streak ' + str(slot.get('streak') or 0))}  "
              f"{dim('best ' + str(slot.get('best_streak') or 0))}  "
              f"{dim('pts ' + str(slot.get('points') or 0))}")
        if not hist:
            print(dim("     — no history yet"))
            continue
        for day in sorted(hist, reverse=True)[:30]:
            result = hist[day]
            mark = good("done") if result == "done" else warn("missed")
            print(f"     {day}  {mark}")
    print()


def cmd_habit_find(_state, args):
    query = " ".join(args.query).strip()
    hits = search_habits(query)
    if not hits:
        print(f"No habits match '{query}'.")
        return
    progress = load_progress()
    today = today_str()
    print(f"\n  {bold('find')}  {dim(query)}  {len(hits)} hit(s)\n")
    for h in hits:
        slot = slot_for(progress, h["name"])
        due = h["enabled"] and not h["archived"] and is_due_on(h, today, slot.get("anchor") or today)
        print(_fmt_habit_line(h, slot, today, due))
    print()


def cmd_habit_miss(state, args):
    name = " ".join(args.name).strip() if isinstance(args.name, list) else str(args.name)
    habit = find_declared(name)
    if habit is None:
        print(f"No habit named '{name}'.", file=sys.stderr)
        return
    from .state import log_event, snapshot
    snapshot(state)
    record_miss(habit["name"], drop_open=state)
    log_event(state, f"habit missed (manual): {habit['name']}")
    print(f"  {warn('missed')}  {habit['name']}  {dim('streak reset')}")
