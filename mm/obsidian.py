"""Bidirectional sync between MM habits and an Obsidian daily note.

Today's note holds boolean properties (cs302, exercise, …). Toggling one
in Obsidian or closing the item in MM updates the other. Adding a habit
in either place grows the mapping. Stdlib only — no PyYAML.

Config in mm.toml:

    [obsidian]
    enabled = true
    vault = "/path/to/Professional_notes_from_scratch"
    folder = "20 Journal/Personal"
    template = "80 System/Templates/Daily Journal Template.md"
"""
from __future__ import annotations

import json
import os
import re
from datetime import date

from .config import load_rules, save_rules
from .habits import (
    iter_open_habit_items, load_declared, normalize_habit,
    record_done, record_undone, load_progress, upsert_declared,
)
from .paths import P
from .util import dim, good, now_iso, today_str, warn

RESERVED_KEYS = {
    "type", "topic", "status", "created", "updated", "tags", "energy",
    "cssclass", "cssclasses", "aliases", "alias", "publish", "permalink",
    "date", "title", "description", "draft", "cover", "cssclasses",
}

# Names that do not slug the obvious way.
KNOWN_SLUGS = {
    "thinking mathematically": "thinking_math_book",
    "nand": "nand2tetris",
    "nand2tetris": "nand2tetris",
    "english grammar": "english_grammar",
}

TYPE_FOR_SLUG = {
    "journaling": "journal",
    "exercise": "fitness",
    "meditation": "mind",
    "english_grammar": "skill",
    "screeps": "course",
    "cs301": "book",
    "cs302": "book",
    "psy101": "book",
    "thinking_math_book": "book",
    "nand2tetris": "course",
}

# Heatmap keys are not gates unless MM already declared them as gates.
DEFAULT_GATE_SLUGS = {
    "cs301", "cs302", "psy101", "thinking_math_book", "nand2tetris", "screeps",
}


def slugify(name):
    key = (name or "").strip().lower()
    if key in KNOWN_SLUGS:
        return KNOWN_SLUGS[key]
    slug = re.sub(r"[^a-z0-9]+", "_", key).strip("_")
    return slug or "habit"


def slug_for(habit):
    return (habit.get("obsidian") or "").strip() or slugify(habit.get("name") or "")


def obsidian_cfg(rules=None):
    if rules is None:
        rules = load_rules()
    raw = rules.get("obsidian") or {}
    if not raw:
        return None
    enabled = raw.get("enabled", True)
    if isinstance(enabled, str):
        enabled = enabled.strip().lower() in ("1", "true", "yes", "on")
    if not enabled:
        return None
    vault = os.path.expanduser(str(raw.get("vault") or "").strip())
    if not vault or not os.path.isdir(vault):
        return None
    folder = str(raw.get("folder") or "20 Journal/Personal").strip().strip("/")
    template = str(raw.get("template") or "80 System/Templates/Daily Journal Template.md").strip()
    if not template.endswith(".md"):
        template = template + ".md"
    return {
        "vault": vault,
        "folder": folder,
        "template": template,
        "enabled": True,
    }


def configured(rules=None):
    return obsidian_cfg(rules) is not None


def daily_note_path(cfg, day):
    return os.path.join(cfg["vault"], cfg["folder"], f"{day}.md")


def template_path(cfg):
    return os.path.join(cfg["vault"], cfg["template"])


def heatmap_path(cfg):
    return os.path.join(cfg["vault"], "System", "scripts", "weighted-heatmap.js")


def types_path(cfg):
    return os.path.join(cfg["vault"], ".obsidian", "types.json")


def ensure_checkbox_types(cfg, slugs):
    """Obsidian only writes true/false if the property type is checkbox."""
    path = types_path(cfg)
    folder = os.path.dirname(path)
    if not os.path.isdir(folder):
        return False
    data = {"types": {}}
    if os.path.isfile(path):
        try:
            with open(path, encoding="utf-8") as f:
                data = json.load(f)
            if not isinstance(data, dict):
                data = {"types": {}}
        except (OSError, json.JSONDecodeError):
            data = {"types": {}}
    types = data.setdefault("types", {})
    if not isinstance(types, dict):
        types = {}
        data["types"] = types
    changed = False
    if types.get("energy") != "number":
        types["energy"] = "number"
        changed = True
    for slug in slugs:
        if not slug or slug in RESERVED_KEYS:
            continue
        if types.get(slug) != "checkbox":
            types[slug] = "checkbox"
            changed = True
    if changed:
        _atomic_write(path, json.dumps(data, indent=2, ensure_ascii=False) + "\n")
    return changed


def resolve_templater(text, day):
    d = date.fromisoformat(day)
    weekday = d.strftime("%A")
    text = re.sub(r'<%\s*tp\.date\.now\("YYYY-MM-DD"\)\s*%>', day, text)
    text = re.sub(r"<%\s*tp\.date\.now\('YYYY-MM-DD'\)\s*%>", day, text)
    text = re.sub(r'<%\s*tp\.date\.now\("dddd"\)\s*%>', weekday, text)
    text = re.sub(r"<%\s*tp\.date\.now\('dddd'\)\s*%>", weekday, text)
    text = re.sub(r"<%.*?%>", "", text, flags=re.S)
    return text


def parse_frontmatter(text):
    """Return (props dict, body). Props keep YAML-ish scalars and simple lists."""
    if not text.startswith("---"):
        return {}, text
    rest = text[3:]
    if rest.startswith("\n"):
        rest = rest[1:]
    end = rest.find("\n---")
    if end < 0:
        return {}, text
    fm = rest[:end]
    body = rest[end + 4:]
    if body.startswith("\n"):
        body = body[1:]
    props = {}
    lines = fm.splitlines()
    i = 0
    while i < len(lines):
        line = lines[i]
        if not line.strip() or line.lstrip().startswith("#"):
            i += 1
            continue
        m = re.match(r"^([A-Za-z0-9_]+)\s*:\s*(.*)$", line)
        if not m:
            i += 1
            continue
        key, val = m.group(1), m.group(2).strip()
        if val == "":
            items = []
            j = i + 1
            while j < len(lines) and re.match(r"^\s+-\s+", lines[j]):
                items.append(re.sub(r"^\s+-\s+", "", lines[j]).strip().strip('"').strip("'"))
                j += 1
            props[key] = items if items else ""
            i = j
            continue
        low = val.lower()
        if low in ("true", "false"):
            props[key] = low == "true"
        elif re.fullmatch(r"-?\d+", val):
            props[key] = int(val)
        else:
            props[key] = val.strip('"').strip("'")
        i += 1
    return props, body


def _truthy_prop(v):
    if v is True or v == 1:
        return True
    if isinstance(v, str) and v.strip().lower() in ("true", "1", "yes", "on", "x", "checked"):
        return True
    return False


def set_frontmatter_bool(text, key, value):
    """Set key: true|false in the opening frontmatter. Inserts the key if missing."""
    bool_s = "true" if value else "false"
    pattern = re.compile(
        rf"^({re.escape(key)}:\s*)(true|false|True|False|1|0)\s*$",
        re.M,
    )
    if pattern.search(text):
        return pattern.sub(rf"\g<1>{bool_s}", text, count=1)
    if not text.startswith("---"):
        return f"---\n{key}: {bool_s}\n---\n{text}"
    # Insert before the closing --- of the first frontmatter block.
    m = re.search(r"\n---\s*\n", text[3:])
    if not m:
        return text.rstrip() + f"\n{key}: {bool_s}\n"
    insert_at = 3 + m.start()
    return text[:insert_at] + f"\n{key}: {bool_s}" + text[insert_at:]


def parse_targets_table(text):
    """Rows from the Daily targets markdown table."""
    rows = []
    seen_header = False
    for line in text.splitlines():
        if re.match(r"^\|\s*Target\s*\|\s*Property\s*\|\s*Weight", line, re.I):
            seen_header = True
            continue
        if not seen_header:
            continue
        if not line.startswith("|"):
            break
        stripped = line.replace("|", "").replace(" ", "").replace(":", "")
        if stripped and set(stripped) <= set("-"):
            continue
        cells = [c.strip() for c in line.strip().strip("|").split("|")]
        if len(cells) < 3:
            continue
        name = cells[0].strip()
        prop = cells[1].strip().strip("`").strip()
        try:
            weight = int(re.sub(r"[^\d-]", "", cells[2]) or "1")
        except ValueError:
            weight = 1
        if name and prop and prop.lower() not in RESERVED_KEYS:
            rows.append({"name": name, "obsidian": prop, "weight": weight})
    return rows


def add_table_row(text, name, prop, weight):
    token = f"`{prop}`"
    if token in text and re.search(r"\|\s*Target\s*\|", text):
        return text
    row = f"| {name} | `{prop}` | {weight} |"
    lines = text.splitlines(keepends=True)
    last = None
    seen_header = False
    for i, line in enumerate(lines):
        if re.search(r"\|\s*Target\s*\|\s*Property", line, re.I):
            seen_header = True
            last = i
            continue
        if seen_header and line.lstrip().startswith("|"):
            last = i
        elif seen_header:
            break
    if last is None:
        block = (
            "\n\n## Daily targets\n\n"
            "| Target | Property | Weight |\n"
            "|---|---|---|\n"
            f"{row}\n"
        )
        return text.rstrip() + block
    nl = "" if lines[last].endswith("\n") else "\n"
    lines[last] = lines[last] + nl + row + "\n"
    return "".join(lines)


def ensure_heatmap_habit(cfg, key, label, weight):
    path = heatmap_path(cfg)
    if not os.path.isfile(path):
        return False
    try:
        with open(path, encoding="utf-8") as f:
            body = f.read()
    except OSError:
        return False
    if re.search(rf'key:\s*"{re.escape(key)}"', body):
        return False
    entry = (
        f'  {{ key: "{key}",'.ljust(28)
        + f'label: "{label}",'.ljust(30)
        + f"weight: {int(weight)} }},\n"
    )
    m = re.search(r"const HABITS = \[\n", body)
    if not m:
        return False
    # Insert before the closing ]; of that array.
    end = body.find("];", m.end())
    if end < 0:
        return False
    body = body[:end] + entry + body[end:]
    _atomic_write(path, body)
    return True


def _atomic_write(path, body):
    os.makedirs(os.path.dirname(path) or ".", exist_ok=True)
    tmp = path + ".mm-tmp"
    with open(tmp, "w", encoding="utf-8") as f:
        f.write(body)
        f.flush()
        os.fsync(f.fileno())
    os.replace(tmp, path)


def read_note(path):
    with open(path, encoding="utf-8") as f:
        return f.read()


def write_note(path, text):
    _atomic_write(path, text)


def write_daily(path, text):
    """Write the note without losing a box the user ticked while we worked.

    For structural edits only (new property, new table row). Value changes
    go through push_state, which re-reads the file immediately before writing.
    """
    if os.path.isfile(path):
        try:
            disk_props, _ = parse_frontmatter(read_note(path))
        except OSError:
            disk_props = {}
        for key, val in disk_props.items():
            if key in RESERVED_KEYS:
                continue
            if _truthy_prop(val):
                text = set_frontmatter_bool(text, key, True)
    write_note(path, text)


def ensure_daily_note(cfg, day):
    """Create today's note from the template if it is missing."""
    path = daily_note_path(cfg, day)
    if os.path.isfile(path):
        return path, False
    os.makedirs(os.path.dirname(path), exist_ok=True)
    tpl = template_path(cfg)
    if os.path.isfile(tpl):
        with open(tpl, encoding="utf-8") as f:
            text = resolve_templater(f.read(), day)
    else:
        text = (
            f"---\ntype: daily\nenergy: 3\n---\n"
            f"# {day}\n\n## Reflection\n- \n\n## Daily targets\n\n"
            "| Target | Property | Weight |\n|---|---|---|\n"
        )
    write_note(path, text)
    return path, True


def _habit_from_row(row, gate=False):
    raw = {
        "name": row["name"],
        "obsidian": row["obsidian"],
        "type": TYPE_FOR_SLUG.get(row["obsidian"], "habit"),
        "repeat": 1,
        "enabled": 1,
        "archived": 0,
        "position": "queue",
        "gate": bool(gate),
        "weight": 1 if not gate else int(row.get("weight") or 1),
    }
    # Heatmap weights (40–90) would bury MM's queue weights (1–10).
    # New habits from Obsidian are normals at weight 1; user can raise them.
    if not gate:
        raw["weight"] = 1
        raw["place"] = "back"
    habit, err = normalize_habit(raw)
    return habit, err


def reconcile(cfg, day, rules=None):
    """Grow the mapping both ways. Returns (added_habits, added_props)."""
    rules = rules or load_rules()
    path, _created = ensure_daily_note(cfg, day)
    text = read_note(path)
    props, _body = parse_frontmatter(text)
    table = parse_targets_table(text)
    tpl_path = template_path(cfg)
    tpl_text = read_note(tpl_path) if os.path.isfile(tpl_path) else ""
    if tpl_text:
        for row in parse_targets_table(tpl_text):
            if not any(r["obsidian"] == row["obsidian"] for r in table):
                table.append(row)

    added_habits = []
    declared = load_declared(rules)
    by_slug = {slug_for(h): h for h in declared}
    by_name = {h["name"].lower(): h for h in declared}

    for row in table:
        slug = row["obsidian"]
        if slug in RESERVED_KEYS:
            continue
        if slug in by_slug or row["name"].lower() in by_name:
            continue
        gate = slug in DEFAULT_GATE_SLUGS
        habit, err = _habit_from_row(row, gate=gate)
        if err or habit is None:
            continue
        upsert_declared(habit)
        added_habits.append(habit["name"])
        by_slug[slug] = habit
        by_name[habit["name"].lower()] = habit

    added_props = []
    # Reload after possible upserts.
    declared = load_declared()
    note_text = text
    tpl_out = tpl_text
    changed_note = False
    changed_tpl = False
    for habit in declared:
        if not habit.get("enabled") or habit.get("archived"):
            continue
        slug = slug_for(habit)
        if slug in RESERVED_KEYS:
            continue
        if slug not in props:
            note_text = set_frontmatter_bool(note_text, slug, False)
            props[slug] = False
            changed_note = True
            added_props.append(slug)
        if habit["name"] and slug:
            new_note = add_table_row(note_text, habit["name"], slug, habit.get("weight") or 1)
            if new_note != note_text:
                note_text = new_note
                changed_note = True
            if tpl_out:
                new_tpl = add_table_row(tpl_out, habit["name"], slug, habit.get("weight") or 1)
                tpl_props, _ = parse_frontmatter(new_tpl)
                if slug not in tpl_props:
                    new_tpl = set_frontmatter_bool(new_tpl, slug, False)
                if new_tpl != tpl_out:
                    tpl_out = new_tpl
                    changed_tpl = True
            ensure_heatmap_habit(cfg, slug, habit["name"], habit.get("weight") or 1)

    slugs = [slug_for(h) for h in declared if h.get("enabled") and not h.get("archived")]
    slugs.extend(row["obsidian"] for row in table)
    ensure_checkbox_types(cfg, slugs)

    if changed_note:
        write_daily(path, note_text)
    if changed_tpl and tpl_out:
        write_note(tpl_path, tpl_out)
    return added_habits, added_props


def shadow_path():
    return os.path.join(P.dir, "obsidian.json")


def load_shadow(day):
    """Last values we and Obsidian agreed on, so we can tell who moved.

    A missing entry counts as false: a fresh note is all unticked, so a
    true we have never seen can only have come from the user.
    """
    try:
        with open(shadow_path(), encoding="utf-8") as f:
            data = json.load(f)
    except (OSError, ValueError):
        return {}
    if data.get("day") != day:
        return {}
    props = data.get("props")
    return props if isinstance(props, dict) else {}


def save_shadow(day, props):
    """Merge, so a phase that only saw some slugs cannot blank the rest."""
    P.ensure()
    merged = load_shadow(day)
    merged.update({k: bool(v) for k, v in props.items()})
    _atomic_write(shadow_path(), json.dumps({"day": day, "props": merged}, indent=2) + "\n")


def _mm_done(progress, name, day):
    return (progress.get("habits") or {}).get(name, {}).get("history", {}).get(day) == "done"


def _sync_targets(cfg, day, rules):
    """(note path, note props, [(habit, slug)]) for habits with a property."""
    path = daily_note_path(cfg, day)
    if not os.path.isfile(path):
        return None, {}, []
    props, _ = parse_frontmatter(read_note(path))
    targets = []
    for habit in load_declared(rules):
        if not habit.get("enabled") or habit.get("archived"):
            continue
        slug = slug_for(habit)
        if not slug or slug in RESERVED_KEYS or slug not in props:
            continue
        targets.append((habit, slug))
    return path, props, targets


def pull_user_edits(state, cfg, day, rules=None):
    """Apply only the boxes the user moved in Obsidian since our last sync.

    Without the shadow we cannot distinguish "user unticked this" from
    "mm marked it done and has not pushed yet", and the pull would undo
    the done that the very same command just recorded.
    """
    path, props, targets = _sync_targets(cfg, day, rules)
    if not path:
        return [], []
    shadow = load_shadow(day)
    done, undone = [], []
    seen = {}
    for habit, slug in targets:
        note_val = _truthy_prop(props.get(slug))
        seen[slug] = note_val
        if note_val == bool(shadow.get(slug, False)):
            continue  # user did not touch it; mm state wins on push
        progress = load_progress()
        if note_val and not _mm_done(progress, habit["name"], day):
            close_habit_for_day(state, habit, day)
            done.append(habit["name"])
        elif not note_val and _mm_done(progress, habit["name"], day):
            record_undone(habit["name"], day)
            undone.append(habit["name"])
    save_shadow(day, seen)
    return done, undone


def close_habit_for_day(state, habit, day):
    """Archive any open items for this habit and record the day as done."""
    opened = list(iter_open_habit_items(state, habit["name"]))
    if opened:
        for container, item in opened:
            state[container].remove(item)
            item["done_at"] = now_iso()
            state.setdefault("archive", []).append(item)
            record_done(state, item, today=day)
    else:
        record_done(state, {
            "habit": habit["name"],
            "habit_due": day,
            "weight": habit.get("weight") or 1,
        }, today=day)


def push_state(state, cfg, day, rules=None):
    """Write MM's truth into the note and refresh the shadow."""
    path, props, targets = _sync_targets(cfg, day, rules)
    if not path:
        return []
    progress = load_progress()
    text = read_note(path)
    shadow, pushed = {}, []
    for habit, slug in targets:
        desired = _mm_done(progress, habit["name"], day)
        shadow[slug] = desired
        if _truthy_prop(props.get(slug)) != desired:
            text = set_frontmatter_bool(text, slug, desired)
            pushed.append(slug)
    if pushed:
        write_note(path, text)
    save_shadow(day, shadow)
    return pushed


def apply_obsidian(state, today=None, rules=None, phase="all"):
    """phase: before (reconcile+pull), after (push), all."""
    rules = rules or load_rules()
    cfg = obsidian_cfg(rules)
    summary = {
        "ok": bool(cfg),
        "added_habits": [],
        "added_props": [],
        "pulled": [],
        "undone": [],
        "pushed": [],
    }
    if not cfg:
        return summary
    today = today or today_str()
    try:
        if phase in ("before", "all"):
            summary["added_habits"], summary["added_props"] = reconcile(cfg, today, rules)
            if summary["added_habits"]:
                rules = load_rules()
            summary["pulled"], summary["undone"] = pull_user_edits(state, cfg, today, rules)
        if phase in ("after", "all"):
            summary["pushed"] = push_state(state, cfg, today, rules)
    except OSError as e:
        print(f"⚠️  obsidian sync skipped ({e})", file=__import__("sys").stderr)
        summary["ok"] = False
    return summary


def on_habit_changed(habit):
    """After mm habit add/set — grow the daily note + template if configured."""
    try:
        cfg = obsidian_cfg()
        if not cfg or not habit:
            return
        day = today_str()
        path, _ = ensure_daily_note(cfg, day)
        slug = slug_for(habit)
        if slug in RESERVED_KEYS:
            return
        text = set_frontmatter_bool(read_note(path), slug, False)
        text = add_table_row(text, habit["name"], slug, habit.get("weight") or 1)
        write_daily(path, text)
        tpl = template_path(cfg)
        if os.path.isfile(tpl):
            t = read_note(tpl)
            t = set_frontmatter_bool(t, slug, False)
            t = add_table_row(t, habit["name"], slug, habit.get("weight") or 1)
            write_note(tpl, t)
        ensure_heatmap_habit(cfg, slug, habit["name"], habit.get("weight") or 1)
        ensure_checkbox_types(cfg, [slug])
    except OSError:
        return


def cmd_obsidian_sync(state, _args=None):
    from .habits import ensure_due_habits

    summary = apply_obsidian(state, phase="before")
    if not summary["ok"]:
        rules = load_rules()
        raw = rules.get("obsidian") or {}
        vault = os.path.expanduser(str(raw.get("vault") or "").strip())
        if not raw or not raw.get("enabled", True):
            print("Obsidian sync is off. Add [obsidian] enabled = true and vault = \"…\" to mm.toml.")
        elif not vault:
            print("Obsidian vault path is empty. Set [obsidian].vault in mm.toml.")
        elif not os.path.isdir(vault):
            print(f"Obsidian vault not found: {vault}")
        else:
            print("Obsidian sync skipped.")
        return summary
    added, backlogged, skipped, missed = ensure_due_habits(state)
    after = apply_obsidian(state, phase="after")
    summary["pushed"] = after.get("pushed") or []
    bits = []
    if summary["pulled"]:
        bits.append("pulled " + ", ".join(summary["pulled"]))
    if summary.get("undone"):
        bits.append("reopened " + ", ".join(summary["undone"]))
    if summary["pushed"]:
        bits.append("pushed " + ", ".join(summary["pushed"]))
    if summary["added_habits"]:
        bits.append("+habit " + ", ".join(summary["added_habits"]))
    if summary["added_props"]:
        bits.append("+prop " + ", ".join(summary["added_props"]))
    if added:
        bits.append(f"{len(added)} due queued")
    if missed:
        bits.append(f"missed {len(missed)}")
    extra = dim("  · " + " · ".join(bits)) if bits else dim("  · already in sync")
    print(f"  {good('✓')} obsidian{extra}")
    return summary


WATCH_READY = "watching "
WATCH_BLOCKED = "vault-unreadable"


def _vault_readable(cfg):
    """A background agent may be denied ~/Documents by macOS privacy control."""
    try:
        os.listdir(cfg["vault"])
        return True
    except PermissionError:
        return False
    except OSError:
        return True  # missing path is a different problem; let the sync report it


def cmd_obsidian_watch(_state=None, _args=None):
    """Poll today's daily note so checkbox toggles hit the queue without mm status."""
    import time

    from .habits import ensure_due_habits
    from .state import load, save
    from .util import Lock

    cfg = obsidian_cfg()
    if not cfg:
        print("Obsidian sync is off. Set [obsidian] in mm.toml.")
        return
    if not _vault_readable(cfg):
        print(f"{WATCH_BLOCKED}: {cfg['vault']}", flush=True)
        print("macOS is denying this process access to the vault folder.", flush=True)
        return
    path = daily_note_path(cfg, today_str())
    print(f"  {WATCH_READY}{path}", flush=True)
    print(dim("  check/uncheck in Obsidian — Ctrl-C to stop"))
    last = None
    try:
        while True:
            day = today_str()
            path = daily_note_path(cfg, day)
            try:
                mtime = os.path.getmtime(path) if os.path.isfile(path) else 0
            except OSError:
                mtime = 0
            if mtime != last:
                last = mtime
                with Lock():
                    state = load()
                    before = apply_obsidian(state, today=day, phase="before")
                    added, _b, _s, _m = ensure_due_habits(state, today=day)
                    apply_obsidian(state, today=day, phase="after")
                    save(state)
                bits = []
                if before.get("pulled"):
                    bits.append("done " + ", ".join(before["pulled"]))
                if before.get("undone"):
                    bits.append("reopened " + ", ".join(before["undone"]))
                if added:
                    bits.append(f"{len(added)} queued")
                if bits:
                    print("  " + " · ".join(bits), flush=True)
            time.sleep(0.4)
    except KeyboardInterrupt:
        print("\n  stopped")


AGENT_LABEL = "com.mm.obsidian.watch"


def _agent_plist_path():
    return os.path.expanduser(f"~/Library/LaunchAgents/{AGENT_LABEL}.plist")


def _mm_executable():
    import shutil as _shutil
    import sys
    return _shutil.which("mm") or os.path.abspath(sys.argv[0])


def _explain_fda(interpreter, log):
    print(warn("  autostart could not start."))
    print("  macOS withholds Desktop/Documents from background agents, so the")
    print("  watcher cannot read the vault until you grant it access once:")
    print()
    print("    System Settings → Privacy & Security → Full Disk Access → +")
    print(f"    add:  {interpreter}")
    print()
    print("  then:  mm obsidian autostart on")
    print(dim(f"  until then run  mm obsidian watch  in a terminal (that already has access)"))
    print(dim(f"  log: {log}"))


def cmd_obsidian_autostart(_state=None, args=None):
    """Keep the watcher alive in the background, across logins (launchd)."""
    import platform
    import subprocess

    action = getattr(args, "action", None) or "status"
    plist = _agent_plist_path()
    if platform.system() != "Darwin":
        print("autostart needs macOS launchd. Elsewhere, run: mm obsidian watch")
        return
    if action == "status":
        if not os.path.isfile(plist):
            print("  autostart off — turn it on with: mm obsidian autostart on")
            return
        out = subprocess.run(["launchctl", "list"], capture_output=True, text=True).stdout
        live = AGENT_LABEL in out
        print(f"  autostart on — watcher {'running' if live else 'not running'}")
        print(dim(f"  log: {os.path.join(P.dir, 'obsidian-watch.log')}"))
        return
    if action == "off":
        subprocess.run(["launchctl", "unload", plist], capture_output=True)
        if os.path.isfile(plist):
            os.remove(plist)
        print(f"  {good('✓')} autostart off")
        return
    import sys
    import time

    log = os.path.join(P.dir, "obsidian-watch.log")
    P.ensure()
    # Pin the interpreter so the path we ask you to authorise is the one that runs.
    interpreter = sys.executable
    body = f"""<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN" "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0">
<dict>
  <key>Label</key><string>{AGENT_LABEL}</string>
  <key>ProgramArguments</key>
  <array>
    <string>{interpreter}</string>
    <string>{_mm_executable()}</string>
    <string>obsidian</string>
    <string>watch</string>
  </array>
  <key>RunAtLoad</key><true/>
  <key>KeepAlive</key><true/>
  <key>ThrottleInterval</key><integer>10</integer>
  <key>StandardOutPath</key><string>{log}</string>
  <key>StandardErrorPath</key><string>{log}</string>
  <key>EnvironmentVariables</key>
  <dict><key>MM_HOME</key><string>{P.dir}</string></dict>
</dict>
</plist>
"""
    os.makedirs(os.path.dirname(plist), exist_ok=True)
    with open(log, "w", encoding="utf-8") as f:
        f.write("")
    _atomic_write(plist, body)
    subprocess.run(["launchctl", "unload", plist], capture_output=True)
    r = subprocess.run(["launchctl", "load", plist], capture_output=True, text=True)
    if r.returncode != 0:
        print(warn("  could not load the agent: ") + (r.stderr or "").strip())
        return
    # Don't claim success we have not seen: wait for the watcher to report in.
    deadline = time.time() + 8
    out = ""
    while time.time() < deadline:
        time.sleep(0.4)
        try:
            with open(log, encoding="utf-8") as f:
                out = f.read()
        except OSError:
            out = ""
        if WATCH_READY in out or WATCH_BLOCKED in out or "Error" in out:
            break
    if WATCH_READY not in out:
        subprocess.run(["launchctl", "unload", plist], capture_output=True)
        os.remove(plist)
        _explain_fda(interpreter, log)
        return
    print(f"  {good('✓')} autostart on — ticking a box in Obsidian now lands in mm within a second")
    print(dim(f"  log: {log}   ·  off again: mm obsidian autostart off"))
