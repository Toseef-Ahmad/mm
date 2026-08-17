"""Argparse surface. Verbs live in ops.py / books.py; this file only wires them."""
import argparse

from .books import (
    cmd_book_add, cmd_book_daily, cmd_book_done, cmd_book_list,
    cmd_book_progress, cmd_book_rm, cmd_book_sync,
)
from .ops import (
    cmd_add, cmd_archive, cmd_backlog, cmd_block, cmd_capacity, cmd_done,
    cmd_edit, cmd_export, cmd_find, cmd_flush_quick, cmd_init, cmd_log,
    cmd_move, cmd_next, cmd_note, cmd_onboard, cmd_peek, cmd_reset, cmd_resume,
    cmd_rm, cmd_rules_show, cmd_rules_strict, cmd_rules_validate,
    cmd_session, cmd_start, cmd_stats, cmd_status, cmd_stop, cmd_suspend,
    cmd_unblock, cmd_undo,
)
from .state import load, save
from .util import Lock


def main():
    p = argparse.ArgumentParser(
        prog="mm",
        description="Decide what's next. Never when. Queue + interrupt stack + gates.",
    )
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
    rs.add_argument("--all", action="store_true", help="resume every suspended item")
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

    ini = sub.add_parser("init", help="write a starter ~/.mm/mm.toml")
    ini.add_argument("--force", action="store_true")
    ini.set_defaults(func=cmd_init)

    ob = sub.add_parser("onboard", help="seed today's queue from mm.toml (once per day)")
    ob.add_argument("-n", "--count", type=int, default=None, help="override rotation count just for today")
    ob.add_argument("-f", "--force", action="store_true",
                    help="onboard even with leftover gates or if already seeded today")
    ob.add_argument("--again", action="store_true",
                    help="re-seed today even if already onboarded")
    ob.set_defaults(func=cmd_onboard)

    rst = sub.add_parser("reset", help="clear today's onboard lock (does not park the queue)")
    rst.add_argument("--park-gates", action="store_true",
                     help="also suspend leftover gates so they stop blocking")
    rst.add_argument("--drop-gates", action="store_true",
                     help="remove leftover gates from the queue instead of parking them")
    rst.set_defaults(func=cmd_reset)

    bk = sub.add_parser("book")
    bk_sub = bk.add_subparsers(dest="book_cmd", required=True)

    bka = bk_sub.add_parser("add")
    bka.add_argument("title", nargs="+", help="title; trailing integer is optional page count")
    bka.add_argument("-g", "--group", default=None)
    bka.set_defaults(func=cmd_book_add)

    bkp = bk_sub.add_parser("progress")
    bkp.add_argument("id", type=int)
    bkp.add_argument("pages", type=int)
    bkp.set_defaults(func=cmd_book_progress)

    bkd = bk_sub.add_parser("done")
    bkd.add_argument("id", type=int)
    bkd.set_defaults(func=cmd_book_done)

    bkl = bk_sub.add_parser("list")
    bkl.set_defaults(func=cmd_book_list)

    bks = bk_sub.add_parser("sync")
    bks.add_argument("--prune", action="store_true")
    bks.set_defaults(func=cmd_book_sync)

    bkdaily = bk_sub.add_parser("daily")
    bkdaily.add_argument("n", type=int)
    bkdaily.set_defaults(func=cmd_book_daily)

    bkr = bk_sub.add_parser("rm")
    bkr.add_argument("id", type=int)
    bkr.set_defaults(func=cmd_book_rm)

    ru = sub.add_parser("rules")
    ru_sub = ru.add_subparsers(dest="rules_cmd", required=True)
    ru_sub.add_parser("show").set_defaults(func=cmd_rules_show)
    ru_sub.add_parser("validate").set_defaults(func=cmd_rules_validate)
    ru_st = ru_sub.add_parser("strict")
    ru_st.add_argument("value", help="on or off")
    ru_st.set_defaults(func=cmd_rules_strict)

    bg = sub.add_parser("backlog")
    bg.add_argument("--promote", action="store_true")
    bg.set_defaults(func=cmd_backlog)

    cp = sub.add_parser("capacity")
    cp.add_argument("container", nargs="?", choices=["queue", "stack", "quick"], default=None)
    cp.add_argument("max", nargs="?", type=int, default=None)
    cp.set_defaults(func=cmd_capacity)

    args = p.parse_args()
    if not getattr(args, "func", None):
        args.func = cmd_next
    with Lock():
        state = load()
        args.func(state, args)
        save(state)
