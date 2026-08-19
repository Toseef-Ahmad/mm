"""Rotation source for anything you return to — courses, books, papers, études.

`pages=0` (or omitted) = repeating daily checklist. `pages>0` = honest progress
gate: mm done refuses until pages were logged today.
"""
import copy
import json
import os
import sys
import tempfile
from datetime import datetime

from .paths import P
from .util import accent, bold, dim, good, now_iso, today_str

EMPTY_BOOKS = {"books": [], "daily_units": 2, "next_id": 1}


def load_books():
    P.ensure()
    if not os.path.exists(P.books):
        return copy.deepcopy(EMPTY_BOOKS)
    try:
        with open(P.books) as f:
            data = json.load(f)
        for k, v in EMPTY_BOOKS.items():
            data.setdefault(k, v if not isinstance(v, (list, dict)) else type(v)())
        return data
    except (json.JSONDecodeError, OSError) as e:
        backup = P.books + f".corrupt-{int(datetime.now().timestamp())}"
        try:
            os.replace(P.books, backup)
        except OSError:
            pass
        print(f"⚠️  Books file was corrupted ({e}). Backed up to {backup}. Starting fresh.", file=sys.stderr)
        return copy.deepcopy(EMPTY_BOOKS)


def save_books(data):
    P.ensure()
    fd, tmp = tempfile.mkstemp(dir=P.dir, prefix=".books-", suffix=".tmp")
    try:
        with os.fdopen(fd, "w") as f:
            json.dump(data, f, indent=2)
            f.flush()
            os.fsync(f.fileno())
        os.replace(tmp, P.books)
    finally:
        if os.path.exists(tmp):
            os.remove(tmp)


def find_book(data, book_id):
    return next((b for b in data["books"] if b["id"] == book_id), None)


def build_units(books):
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
    """Paged books: sliding window of unfinished units.
    Checklist books never finish, so they rotate by calendar day."""
    if count is None:
        count = data.get("daily_units", 2)
    if not count:
        return []
    units = build_units(data["books"])
    not_done_units = [u for u in units if any(b["status"] != "done" for b in u)]

    def is_checklist(unit):
        return all(not b.get("pages") for b in unit)

    checklist = [u for u in not_done_units if is_checklist(u)]
    paged = [u for u in not_done_units if not is_checklist(u)]
    picked = []
    if checklist:
        start = datetime.now().toordinal() % len(checklist)
        rotated = checklist[start:] + checklist[:start]
        picked.extend(rotated[:count])
    picked.extend(paged[:count])
    return [b for u in picked for b in u if b["status"] != "done"]


def parse_book_title_pages(words, pages_flag=None):
    words = list(words or [])
    pages = pages_flag
    if pages is None and words and str(words[-1]).isdigit():
        pages = int(words[-1])
        words = words[:-1]
    title = " ".join(words).strip()
    if pages is None:
        pages = 0
    return title, pages


def load_books_config():
    if not os.path.exists(P.books_config):
        return None
    try:
        with open(P.books_config) as f:
            return json.load(f)
    except (json.JSONDecodeError, OSError) as e:
        print(f"⚠️  {P.books_config} is malformed ({e}). Fix the JSON and re-run.", file=sys.stderr)
        return None


def save_books_config(config):
    """Keep the declared list in sync with mm book add/rm/daily.
    Manual edits still work; mm book sync copies this file into books.json."""
    P.ensure()
    fd, tmp = tempfile.mkstemp(dir=P.dir, prefix=".books-config-", suffix=".tmp")
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as f:
            json.dump(config, f, indent=2, ensure_ascii=False)
            f.write("\n")
            f.flush()
            os.fsync(f.fileno())
        os.replace(tmp, P.books_config)
    finally:
        if os.path.exists(tmp):
            os.remove(tmp)


def _config_or_empty():
    return load_books_config() or {"books": [], "daily_units": 2}


def declare_book(title, pages=0, group=None):
    config = _config_or_empty()
    books = config.setdefault("books", [])
    if any(str(b.get("title", "")).lower() == title.lower() for b in books):
        return
    entry = {"title": title, "pages": pages}
    if group:
        entry["group"] = group
    books.append(entry)
    save_books_config(config)


def undeclare_book(title):
    config = load_books_config()
    if not config:
        return
    before = config.get("books", [])
    after = [b for b in before if str(b.get("title", "")).lower() != title.lower()]
    if len(after) == len(before):
        return
    config["books"] = after
    save_books_config(config)


def cmd_book_add(_state, args):
    data = load_books()
    title, pages = parse_book_title_pages(args.title)
    if not title:
        print("Nothing to add — empty title.", file=sys.stderr)
        return
    if pages < 0:
        print(f"⚠️  '{title}' page count can't be negative.", file=sys.stderr)
        return
    if any(b["title"].lower() == title.lower() for b in data["books"]):
        print(f"'{title}' is already on the list.", file=sys.stderr)
        return
    book_id = data["next_id"]
    data["next_id"] += 1
    entry = {"id": book_id, "title": title, "pages": pages, "page": 0, "status": "queued"}
    if getattr(args, "group", None):
        entry["group"] = args.group
    data["books"].append(entry)
    save_books(data)
    declare_book(title, pages, getattr(args, "group", None))
    tag = f" [group: {args.group}]" if getattr(args, "group", None) else ""
    pages_s = f"{pages}p" if pages else "daily checklist (no page target)"
    print(f"  {good('+')} book [{book_id}]  {title}  {dim(pages_s)}{tag}")


def cmd_book_progress(_state, args):
    data = load_books()
    book = find_book(data, args.id)
    if book is None:
        print(f"No book with id {args.id} found. mm book list to see ids.", file=sys.stderr)
        return
    if not book.get("pages"):
        print(f"[{book['id']}] {book['title']} has no page target — close the gate with mm done, or mm book done {book['id']} to drop it from rotation.", file=sys.stderr)
        return
    book["status"] = "active"
    book["page"] = min(book["page"] + args.pages, book["pages"])
    book["last_progress_at"] = now_iso()
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
    book["last_progress_at"] = now_iso()
    save_books(data)
    print(f"📗 Finished [{book['id']}]: {book['title']}! (marked done directly, no page count needed)")


def cmd_book_list(_state, _args):
    data = load_books()
    if not data["books"]:
        print("No books yet. mm book add \"Title\" [pages]")
        return
    active = [b for b in data["books"] if b["status"] != "done"]
    daily = data.get("daily_units", 2)
    todays_picks = {b["id"] for b in pick_books_for_today(data, daily)}
    print(f"\n  {bold('books')}  {dim(f'{len(active)} open · {daily}/day')}\n")
    for b in data["books"]:
        done = b["status"] == "done"
        mark = good("✓") if done else (accent("→") if b["id"] in todays_picks else " ")
        pct = f"{b['page']}/{b['pages']}p" if b["pages"] else "daily"
        grp = dim(f"  · {b['group']}") if b.get("group") else ""
        title = dim(b["title"]) if done else b["title"]
        idcol = dim(f"{b['id']:>2}")
        print(f"  {mark} {idcol}  {title}  {dim(pct)}{grp}")
    print()


def cmd_book_daily(_state, args):
    n = args.n
    if n < 1:
        print("daily window must be at least 1.", file=sys.stderr)
        return
    data = load_books()
    data["daily_units"] = n
    save_books(data)
    config = _config_or_empty()
    config["daily_units"] = n
    save_books_config(config)
    print(f"  {good('✓')} daily book window set to {n}")


def cmd_book_sync(_state, args):
    config = load_books_config()
    if config is None:
        if not os.path.exists(P.books_config):
            print(f"No config found at {P.books_config}.")
            print("Create it with a \"books\" list: [{\"title\": ..., \"pages\": ..., \"group\": ...}]")
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
            if pages is None:
                pages = 0
            if pages < 0:
                print(f"⚠️  Skipping '{title}': page count can't be negative.", file=sys.stderr)
                continue
            book_id = data["next_id"]
            data["next_id"] += 1
            new_book = {"id": book_id, "title": title, "pages": pages, "page": 0, "status": "queued"}
            if group:
                new_book["group"] = group
            data["books"].append(new_book)
            added.append(title)
        else:
            changed = False
            if pages is not None and pages >= 0 and existing["pages"] != pages:
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
                if b["title"].lower() not in config_titles]
    pruned = []
    if getattr(args, "prune", False) and orphaned:
        drop = {t.lower() for t in orphaned}
        pruned = [b["title"] for b in data["books"] if b["title"].lower() in drop]
        data["books"] = [b for b in data["books"] if b["title"].lower() not in drop]
        orphaned = []

    if "daily_units" in config and config["daily_units"] != data.get("daily_units"):
        data["daily_units"] = config["daily_units"]
        print(f"   daily_units set to {config['daily_units']}")

    save_books(data)
    print(f"🔄 Synced from {P.books_config}")
    print(f"   added:   {len(added)}" + (f"  ({', '.join(added)})" if added else ""))
    print(f"   updated: {len(updated)}" + (f"  ({', '.join(updated)})" if updated else ""))
    if pruned:
        print(f"   pruned:  {len(pruned)}  ({', '.join(pruned)})")
    if orphaned:
        print(f"   ⚠️  in mm but no longer in config (left untouched, not deleted): {', '.join(orphaned)}")
        print("      mm book sync --prune  to drop them, or mm book rm <id> one at a time.")


def cmd_book_rm(_state, args):
    data = load_books()
    book = find_book(data, args.id)
    if book is None:
        print(f"No book with id {args.id} found.", file=sys.stderr)
        return
    data["books"] = [b for b in data["books"] if b["id"] != args.id]
    save_books(data)
    undeclare_book(book["title"])
    print(f"🗑  Removed [{book['id']}]: {book['title']}")
