"""User config: ~/.mm/mm.toml (preferred) or ~/.mm/mm.rules.json.

TOML is the format tools actually ship — Cargo, pyproject, ripgrep, gh.
JSON still loads so existing homes keep working. mm writes whichever is active.

Track types (the whole engine — anything you learn is one of these):
  rotation  — sliding/cycling window over a list (books, papers, études, kata)
  weekday   — Mon–Sun table
  static    — same items every day
  list      — alias of static
"""
import json
import os
import sys
import tempfile
from datetime import datetime

from .books import load_books, pick_books_for_today
from .paths import P
from .util import today_weekday_key

try:
    import tomllib
except ImportError:  # pragma: no cover — py<3.11
    tomllib = None


def default_capacity():
    return {
        "queue": {"max": 10, "on_full": "backlog"},
        "stack": {"max": 5, "on_full": "reject"},
        "quick": {"max": 50, "on_full": "warn"},
    }


def _merge_rules_defaults(rules):
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
    rules.setdefault("habits", [])
    rules.setdefault("rewards", {})
    rules.setdefault("obsidian", {})
    return rules


def _toml_scalar(v):
    if isinstance(v, bool):
        return "true" if v else "false"
    if isinstance(v, int):
        return str(v)
    if isinstance(v, float):
        return repr(v)
    if isinstance(v, str):
        return json.dumps(v, ensure_ascii=False)
    if isinstance(v, list):
        return "[ " + ", ".join(_toml_scalar(x) for x in v) + " ]"
    raise TypeError(f"cannot dump {type(v).__name__} to TOML")


def _toml_key(k):
    s = str(k)
    if s.isidentifier() and not s.isnumeric():
        return s
    return json.dumps(s, ensure_ascii=False)


def dumps_toml(obj):
    """Small TOML writer for mm's nested-dict schema. No extra dependency.

    Lists of dicts become array-of-tables (`[[habits]]`).
    """
    chunks = []
    obj = dict(obj)
    array_tables = {}
    for k, v in list(obj.items()):
        if isinstance(v, list) and v and all(isinstance(x, dict) for x in v):
            array_tables[k] = obj.pop(k)
        elif isinstance(v, list) and not v and k == "habits":
            obj.pop(k)

    def emit(path, d):
        scalars = {k: v for k, v in d.items() if not isinstance(v, dict)}
        nested = {k: v for k, v in d.items() if isinstance(v, dict)}
        if not path:
            for k, v in scalars.items():
                chunks.append(f"{_toml_key(k)} = {_toml_scalar(v)}")
            if scalars:
                chunks.append("")
        elif scalars or not nested:
            chunks.append(f"[{path}]")
            for k, v in scalars.items():
                chunks.append(f"{_toml_key(k)} = {_toml_scalar(v)}")
            chunks.append("")
        for k, v in nested.items():
            child = f"{path}.{_toml_key(k)}" if path else _toml_key(k)
            emit(child, v)

    emit("", obj)
    for key, rows in array_tables.items():
        for row in rows:
            chunks.append(f"[[{key}]]")
            scalars = {k: v for k, v in row.items() if not isinstance(v, dict)}
            nested = {k: v for k, v in row.items() if isinstance(v, dict)}
            for k, v in scalars.items():
                if v is None or v == "" or v == []:
                    continue
                chunks.append(f"{_toml_key(k)} = {_toml_scalar(v)}")
            chunks.append("")
            for k, v in nested.items():
                child = f"{key}.{_toml_key(k)}"
                emit(child, v)
    return "\n".join(chunks).rstrip() + "\n"


def load_rules():
    P.ensure()
    kind = P.rules_kind
    if kind == "toml":
        if tomllib is None:
            print("⚠️  mm.toml needs Python 3.11+ (tomllib).", file=sys.stderr)
            return _merge_rules_defaults({})
        try:
            with open(P.rules_toml, "rb") as f:
                return _merge_rules_defaults(tomllib.load(f))
        except (OSError, tomllib.TOMLDecodeError) as e:
            print(f"⚠️  {P.rules_toml} is malformed ({e}); onboarding is disabled until you fix it.", file=sys.stderr)
            return _merge_rules_defaults({})
    if kind == "json":
        try:
            with open(P.rules_json, encoding="utf-8") as f:
                return _merge_rules_defaults(json.load(f))
        except (json.JSONDecodeError, OSError) as e:
            print(f"⚠️  {P.rules_json} is malformed ({e}); onboarding is disabled until you fix it.", file=sys.stderr)
            return _merge_rules_defaults({})
    return _merge_rules_defaults({})


def save_rules(rules):
    P.ensure()
    kind = P.rules_kind or "toml"
    to_dump = rules
    if kind == "toml":
        to_dump = dict(rules)
        onboard = dict(to_dump.get("onboard") or {})
        if not onboard.get("order"):
            onboard.pop("order", None)
            to_dump["onboard"] = onboard
        if not to_dump.get("tracks"):
            to_dump.pop("tracks", None)
        if not to_dump.get("obsidian"):
            to_dump.pop("obsidian", None)
        body = dumps_toml(to_dump)
        path, prefix = P.rules_toml, ".rules-"
    else:
        body = json.dumps(rules, indent=2, ensure_ascii=False)
        path, prefix = P.rules_json, ".rules-"
    fd, tmp = tempfile.mkstemp(dir=P.dir, prefix=prefix, suffix=".tmp")
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as f:
            f.write(body)
            f.flush()
            os.fsync(f.fileno())
        os.replace(tmp, path)
    finally:
        if os.path.exists(tmp):
            os.remove(tmp)


def _as_list(value):
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


def _rotate_values(values, count):
    """Calendar-day slice so a repeating list doesn't freeze on the first N."""
    values = [v for v in values if v]
    if not values or not count:
        return []
    start = datetime.now().toordinal() % len(values)
    rotated = values[start:] + values[:start]
    return rotated[:count]


def compile_track(name, track, weekday, count_override=None):
    """One track → today's item specs. This table is the extension seam."""
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
        source = track.get("source") or ("books" if name == "books" else "items")
        count = count_override if count_override is not None else track.get("count")
        if source == "books":
            data = load_books()
            if count is None:
                count = data.get("daily_units", 2)
            for b in pick_books_for_today(data, count):
                text = _fmt_label(label, id=b["id"], title=b["title"],
                                  page=b["page"], pages=b["pages"], value=b["title"])
                specs.append(spec(text, ref=b["id"], group=b.get("group")))
        else:
            items = _as_list(track.get("items", track.get("values")))
            if count is None:
                count = len(items) or 1
            for v in _rotate_values(items, count):
                specs.append(spec(_fmt_label(label, value=v)))
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
    tracks = rules.get("tracks", {})
    order = rules.get("onboard", {}).get("order") or list(tracks.keys())
    specs = []
    for name in order:
        track = tracks.get(name)
        if track is None:
            continue
        specs.extend(compile_track(name, track, weekday, count_override))
    return specs


def capacity_for(rules, container):
    slot = rules.get("capacity", {}).get(container, {})
    return slot.get("max"), slot.get("on_full", "warn")


def capacity_policy(state, rules, container):
    maxn, on_full = capacity_for(rules, container)
    if maxn is None or len(state[container]) < maxn:
        return "ok", maxn, on_full
    return on_full, maxn, on_full


def promote_backlog(state, rules):
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
        from .state import log_event
        log_event(state, f"promoted from backlog: [{item['id']}] {item['text']}")
        promoted.append(item)
    return promoted


def validate_rules(rules):
    errors, warnings = [], []
    onboard = rules.get("onboard", {})
    tracks = rules.get("tracks", {})
    from .habits import normalize_habit
    habits = rules.get("habits") or []
    has_habits = bool(habits)
    if (not isinstance(tracks, dict) or not tracks) and not has_habits:
        warnings.append("no tracks or habits defined — onboard will queue nothing.")
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
    if isinstance(habits, dict):
        habits = [{"name": n, **(b or {})} for n, b in habits.items()]
    if habits and not isinstance(habits, list):
        errors.append("habits must be an array of objects.")
    else:
        seen = set()
        for i, row in enumerate(habits or []):
            habit, err = normalize_habit(row, i)
            if err:
                errors.append(err)
                continue
            key = habit["name"].lower()
            if key in seen:
                errors.append(f"duplicate habit name '{habit['name']}'.")
            seen.add(key)
    for cname, slot in rules.get("capacity", {}).items():
        if not isinstance(slot, dict) or not isinstance(slot.get("max"), int):
            errors.append(f"capacity.{cname}.max must be an integer.")
        elif slot.get("on_full") not in ("backlog", "reject", "warn"):
            errors.append(f"capacity.{cname}.on_full must be backlog|reject|warn.")
    return errors, warnings
