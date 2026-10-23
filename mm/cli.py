"""Argparse only. Verbs live in ops.py."""
import argparse

from .ops import (
    cmd_add, cmd_archive, cmd_block, cmd_done, cmd_edit, cmd_export,
    cmd_find, cmd_flush_quick, cmd_log, cmd_move, cmd_next, cmd_note,
    cmd_peek, cmd_resume, cmd_rm, cmd_stats, cmd_status, cmd_suspend,
    cmd_unblock, cmd_undo,
)
from .state import load, save
from .util import Lock


def _man_page():
    from pathlib import Path
    pkg = Path(__file__).resolve().parent
    candidates = (
        Path.home() / ".local/share/man/man1/mm.1",
        pkg / "data" / "mm.1",
    )
    for candidate in candidates:
        if candidate.is_file():
            return candidate
    return None


def cmd_help(_state=None, _args=None):
    import os
    import shutil
    import sys
    page = _man_page()
    if page is None:
        print("mm(1) not found. Try: mm --help", file=sys.stderr)
        raise SystemExit(1)
    if shutil.which("man") is None:
        print(page.read_text(encoding="utf-8"))
        return
    os.execvp("man", ["man", str(page)])


def main():
    from . import __version__
    p = argparse.ArgumentParser(
        prog="mm",
        description="A runtime queue: add work, do the next thing, mark it done. Nothing repeats.",
        epilog="Manual: mm help   (or man mm, where man is installed)",
    )
    p.add_argument("--version", action="version", version=f"mm {__version__}")
    sub = p.add_subparsers(dest="cmd")

    a = sub.add_parser("add", help="add to the main queue")
    a.add_argument("task", nargs="+")
    a.add_argument("-p", "--priority", action="store_true", help="push to interrupt stack")
    a.add_argument("-q", "--quick", action="store_true", help="add to quick queue")
    a.set_defaults(func=cmd_add)

    sub.add_parser("next", help="what to do right now (starts the timer)").set_defaults(func=cmd_next)
    sub.add_parser("peek", help="glance without starting the timer").set_defaults(func=cmd_peek)

    d = sub.add_parser("done", help="finish current item (or a specific id)")
    d.add_argument("id", nargs="?", type=int, default=None)
    d.set_defaults(func=cmd_done)

    bl = sub.add_parser("block", help="stuck — requeue and move on")
    bl.add_argument("reason", nargs="*", default=None)
    bl.set_defaults(func=cmd_block)

    ub = sub.add_parser("unblock")
    ub.add_argument("id", type=int)
    ub.add_argument("--front", action="store_true")
    ub.set_defaults(func=cmd_unblock)

    sp = sub.add_parser("suspend", help="park without finishing")
    sp.add_argument("id", nargs="?", type=int, default=None)
    sp.set_defaults(func=cmd_suspend)

    rs = sub.add_parser("resume", help="bring a parked item back")
    rs.add_argument("id", nargs="?", type=int, default=None)
    rs.add_argument("--all", action="store_true")
    rs.set_defaults(func=cmd_resume)

    mv = sub.add_parser("move")
    mv.add_argument("id", type=int)
    mv.add_argument("dest", choices=["queue", "stack", "quick"])
    mv.add_argument("--front", action="store_true")
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

    ar = sub.add_parser("archive")
    ar.add_argument("scope", nargs="?", choices=["today"], default=None)
    ar.set_defaults(func=cmd_archive)

    ex = sub.add_parser("export")
    ex.add_argument("format", choices=["json", "md", "csv"], nargs="?", default="json")
    ex.set_defaults(func=cmd_export)

    lg = sub.add_parser("log")
    lg.add_argument("n", nargs="?", type=int, default=None)
    lg.set_defaults(func=cmd_log)

    hlp = sub.add_parser("help", help="open the mm(1) manual")
    hlp.set_defaults(func=cmd_help, skip_state=True)

    args = p.parse_args()
    if not getattr(args, "func", None):
        args.func = cmd_next
    if getattr(args, "skip_state", False):
        args.func(None, args)
        return
    with Lock():
        state = load()
        args.func(state, args)
        save(state)
