#!/usr/bin/env python3
"""Regenerate the landing page demo from the real CLI.

Every terminal frame on mm.tafil.app is genuine output. This script runs mm
inside a pseudo-terminal (so it emits its real ANSI colours), converts those
colours to spans, and writes site/demo-data.js.

    python3 site/tools/capture.py            # re-record
    python3 site/tools/capture.py --check    # is the committed demo still valid?

It never touches your ~/.mm: each scenario runs against a throwaway MM_HOME
built from site/tools/demo.mm.toml, and the Obsidian scenario builds a
throwaway vault too.

If the CLI's output changes, run this again. A demo that drifts from the tool
is worse than no demo.
"""
from __future__ import annotations

import json
import os
import pty
import re
import shutil
import subprocess
import sys
import tempfile
from datetime import date
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
TOOLS = Path(__file__).resolve().parent
OUT = TOOLS.parent / "demo-data.js"

# mm/util.py: dim=2, bold=1, accent=36, good=32, warn=33.
ANSI_CLASS = {"1": "b", "2": "d", "36": "a", "32": "g", "33": "w"}

ANSI_RE = re.compile(r"\033\[([0-9;]*)m")
OSC_RE = re.compile(r"\033\][^\007\033]*(?:\007|\033\\)")
CSI_RE = re.compile(r"\033\[[0-9;?]*[a-zA-Z]")


def run_in_pty(argv: list[str], env: dict) -> str:
    """Run a command attached to a pty so mm turns colour on."""
    master, slave = pty.openpty()
    proc = subprocess.Popen(argv, stdout=slave, stderr=slave, stdin=subprocess.DEVNULL,
                            env=env, close_fds=True)
    os.close(slave)
    chunks = []
    while True:
        try:
            data = os.read(master, 65536)
        except OSError:
            break
        if not data:
            break
        chunks.append(data)
    os.close(master)
    proc.wait()
    return b"".join(chunks).decode("utf-8", "replace")


def esc(s: str) -> str:
    return s.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")


def ansi_to_html(text: str) -> str:
    """Translate mm's ANSI into <i class=…> spans, dropping other control noise."""
    text = OSC_RE.sub("", text).replace("\r\n", "\n").replace("\r", "")
    out, open_spans, pos = [], 0, 0
    for m in ANSI_RE.finditer(text):
        out.append(esc(text[pos:m.start()]))
        pos = m.end()
        for code in (m.group(1) or "0").split(";"):
            code = code.lstrip("0") or "0"
            if code == "0":
                out.append("</i>" * open_spans)
                open_spans = 0
            elif code in ANSI_CLASS:
                out.append(f'<i class="{ANSI_CLASS[code]}">')
                open_spans += 1
    out.append(esc(text[pos:]))
    out.append("</i>" * open_spans)
    html = "".join(out)
    html = CSI_RE.sub("", html)
    return html.strip("\n")


def new_home(tmp: Path, name: str) -> dict:
    """A throwaway MM_HOME seeded with the demo schedule."""
    home = tmp / name
    home.mkdir(parents=True)
    shutil.copy(TOOLS / "demo.mm.toml", home / "mm.toml")
    env = dict(os.environ)
    env.pop("NO_COLOR", None)
    env["MM_HOME"] = str(home)
    env["TERM"] = "xterm-256color"
    env["COLUMNS"] = "72"
    env["PYTHONPATH"] = str(REPO)
    return env


def mm(env: dict, *args: str) -> str:
    return run_in_pty([sys.executable, "-m", "mm", *args], env)


def frame(cmd: str, out: str, note: str = "") -> dict:
    f = {"cmd": cmd, "out": ansi_to_html(out)}
    if note:
        f["note"] = note
    return f


# --------------------------------------------------------------------------
# Scenarios. Each is a list of {cmd, out} frames replayed in the browser.
# --------------------------------------------------------------------------

def scenario_ritual(tmp: Path) -> list[dict]:
    """Two commands, no decisions."""
    env = new_home(tmp, "ritual")
    frames = [frame("mm status", mm(env, "status"),
                    "The day is already queued from your config. You typed "
                    "none of this.")]
    frames.append(frame("mm", mm(env, "next"),
                        "One command asks the only question that matters. "
                        "mm picks; you do not."))
    frames.append(frame("mm done", mm(env, "done"),
                        "Closed — and the next thing is already on screen."))
    frames.append(frame("mm done", mm(env, "done"),
                        "Both gates shut, so the day is earned. That is the "
                        "entire ritual: mm, mm done, repeat."))
    return frames


def scenario_gates(tmp: Path) -> list[dict]:
    """The gate is the whole point: the easy thing is not on offer."""
    env = new_home(tmp, "gates")
    mm(env, "status")
    frames = [frame("mm status", mm(env, "status"),
                    "Inbox triage sits at the top of the list — and mm still "
                    "will not offer it. A gate is open, so the pointer skips "
                    "to the work you said mattered.")]
    frames.append(frame("mm", mm(env, "next"),
                        "No negotiation, no willpower. There is nothing else to pick."))
    frames.append(frame("mm done", mm(env, "done"),
                        "Close the gate and the day opens up. The reward is "
                        "paid on closed loops, not on good intentions."))
    frames.append(frame("mm status", mm(env, "status"),
                        "Gate closed. Now the small stuff is reachable."))
    return frames


def scenario_interrupt(tmp: Path) -> list[dict]:
    """A real fire preempts, then the stack unwinds to where you were."""
    env = new_home(tmp, "interrupt")
    mm(env, "status")
    frames = [frame("mm", mm(env, "next"), "Mid-task on the thing that matters.")]
    frames.append(frame('mm add -p "prod is down"', mm(env, "add", "-p", "prod is down"),
                        "A genuine fire goes on the interrupt stack."))
    frames.append(frame("mm", mm(env, "next"),
                        "It preempts everything. LIFO, like a call stack."))
    frames.append(frame("mm done", mm(env, "done"),
                        "Fire out — and the stack unwinds to exactly where you "
                        "were. An interruption cannot quietly become your new plan."))
    return frames


def scenario_habits(tmp: Path) -> list[dict]:
    """You configure the schedule once; mm re-queues it forever."""
    env = new_home(tmp, "habits")
    frames = [frame("cat ~/.mm/mm.toml", ansi_demo_config("Deep work", "Inbox triage"),
                    "Declare it once, in one file you own. There is no "
                    "\"add task\" step in the morning.")]
    frames.append(frame("mm status", mm(env, "status"),
                        "Everything due today is already queued. You did not "
                        "type any of it."))
    frames.append(frame("mm habit list", mm(env, "habit", "list"),
                        "The whole schedule, with cadence and streaks. "
                        "gate, w9, #1 are the flags from the file."))
    mm(env, "done")
    frames.append(frame("mm habit log 'Deep work'", mm(env, "habit", "log", "Deep work"),
                        "Streaks are gap-aware: a repeat = 3 habit is never "
                        "punished for the two days it was not due."))
    return frames


def scenario_obsidian(tmp: Path) -> list[dict]:
    """Both directions, against a real note on disk."""
    env = new_home(tmp, "obsidian")
    vault = tmp / "Vault"
    folder = vault / "Journal"
    folder.mkdir(parents=True)
    (vault / ".obsidian").mkdir()
    day = date.today().isoformat()
    note = folder / f"{day}.md"
    note.write_text(
        "---\ntype: daily\nenergy: 3\nreading: false\ndeep_work: false\n"
        "walk: false\ninbox: false\n---\n\n# " + day + "\n",
        encoding="utf-8",
    )
    cfg = (env["MM_HOME"] and Path(env["MM_HOME"]) / "mm.toml")
    cfg.write_text(
        cfg.read_text(encoding="utf-8")
        + f'\n[obsidian]\nenabled = true\nvault = "{vault}"\nfolder = "Journal"\n',
        encoding="utf-8",
    )
    mm(env, "status")

    frames = [frame(f"cat '{day}.md'", ansi_frontmatter(note.read_text(encoding="utf-8")),
                    "Your Obsidian daily note. Plain checkbox properties — "
                    "mm did not invent a format for you.")]
    frames.append(frame("mm status", mm(env, "status"),
                        "Same habits, one list, two front ends."))

    body = note.read_text(encoding="utf-8").replace("reading: false", "reading: true")
    note.write_text(body, encoding="utf-8")
    frames.append(frame("# you tick the box in Obsidian", ansi_frontmatter(body),
                        "Tick it in the app you already have open."))
    frames.append(frame("mm status", mm(env, "status"),
                        "Gone from the queue, streak credited. No import step."))

    out = mm(env, "done")
    frames.append(frame("mm done", out,
                        "Now go the other way: close it in the terminal."))
    frames.append(frame(f"cat '{day}.md'", ansi_frontmatter(note.read_text(encoding="utf-8")),
                        "mm ticked the box for you. Untick it and the habit "
                        "comes back — your edit always wins."))
    return frames


def ansi_demo_config(*only: str) -> str:
    """The demo schedule as a file listing. `only` keeps just those habit blocks,
    because a full config dump is a wall nobody reads."""
    text = (TOOLS / "demo.mm.toml").read_text(encoding="utf-8")
    if only:
        lines = text.splitlines()
        starts = [i for i, l in enumerate(lines) if l.strip() == "[[habits]]"]
        keep = []
        for start in starts:
            end = next((j for j in range(start + 1, len(lines))
                        if lines[j].startswith("[")), len(lines))
            block = lines[start:end]
            name = next((re.search(r'"([^"]+)"', l).group(1) for l in block
                         if l.startswith("name")), None)
            if name not in only:
                continue
            # Pull up only the comment lines directly above: they explain the flag.
            head = start
            while head > 0 and lines[head - 1].startswith("#"):
                head -= 1
            keep.append("\n".join(lines[head:start] + block).rstrip())
        text = "\n\n".join(keep) + "\n"
    lines = []
    for line in text.splitlines():
        if line.startswith("#") or not line.strip():
            lines.append(f"\033[2m{line}\033[0m")
        elif line.startswith("[["):
            lines.append(f"\033[36m{line}\033[0m")
        else:
            lines.append(line)
    return "\n".join(lines)


def ansi_frontmatter(text: str) -> str:
    out = []
    for line in text.splitlines():
        if line.strip() in ("---",):
            out.append(f"\033[2m{line}\033[0m")
        elif line.endswith(": true"):
            out.append(f"\033[32m{line}\033[0m")
        elif line.endswith(": false"):
            out.append(f"\033[2m{line}\033[0m")
        else:
            out.append(line)
    return "\n".join(out)


SCENARIOS = [
    ("ritual", "The ritual", "Two commands, and a day that queues itself.", scenario_ritual),
    ("gates", "Gates", "The easy thing is not on the menu.", scenario_gates),
    ("interrupt", "Interrupts", "Urgency preempts, then unwinds.", scenario_interrupt),
    ("habits", "Habits", "Configure once, queued forever.", scenario_habits),
    ("obsidian", "Obsidian", "Your daily note, synced both ways.", scenario_obsidian),
]


def load_committed() -> dict | None:
    """Parse the JSON payload out of the committed demo-data.js."""
    if not OUT.exists():
        return None
    text = OUT.read_text(encoding="utf-8")
    try:
        return json.loads(text[text.index("{"):text.rindex(";")])
    except (ValueError, json.JSONDecodeError):
        return None


def check(fresh: dict) -> int:
    """Compare a fresh capture against the committed one, structurally.

    Output text is deliberately not compared: it legitimately varies with the
    date and with elapsed-time counters. What must not drift is the shape —
    which scenarios exist, and which commands they run. That is what breaks
    when a command is renamed or removed.
    """
    old = load_committed()
    if old is None:
        print("demo-data.js is missing or unparseable; run capture.py", file=sys.stderr)
        return 1

    def shape(d):
        return [(s["key"], [f["cmd"] for f in s["frames"]]) for s in d["scenarios"]]

    problems = []
    if old.get("version") != fresh["version"]:
        problems.append(f"version: committed {old.get('version')!r}, CLI is {fresh['version']!r}")
    if shape(old) != shape(fresh):
        problems.append("scenario or command list changed")
        for (ok, ocmds), (nk, ncmds) in zip(shape(old), shape(fresh)):
            if (ok, ocmds) != (nk, ncmds):
                problems.append(f"  {ok}: {ocmds} -> {ncmds}")

    if problems:
        print("demo-data.js is stale:", file=sys.stderr)
        for p in problems:
            print("  " + p, file=sys.stderr)
        print("\nre-record it:  python3 site/tools/capture.py", file=sys.stderr)
        return 1
    print("demo-data.js is in step with the CLI", file=sys.stderr)
    return 0


def main() -> int:
    checking = "--check" in sys.argv[1:]

    version = subprocess.run(
        [sys.executable, "-m", "mm", "--version"],
        capture_output=True, text=True,
        env={**os.environ, "PYTHONPATH": str(REPO)},
    ).stdout.strip()

    data = {"version": version, "scenarios": []}
    with tempfile.TemporaryDirectory(prefix="mm-capture-") as tmpdir:
        tmp = Path(tmpdir)
        for key, label, blurb, fn in SCENARIOS:
            print(f"  capturing {key} …", file=sys.stderr)
            data["scenarios"].append({
                "key": key, "label": label, "blurb": blurb, "frames": fn(tmp),
            })

    if checking:
        return check(data)

    banner = (
        "// GENERATED FILE — do not edit by hand.\n"
        "// Every frame below is real output from the mm CLI, captured by\n"
        "// site/tools/capture.py inside a pseudo-terminal. Regenerate with:\n"
        "//     python3 site/tools/capture.py\n"
    )
    OUT.write_text(
        banner + "window.MM_DEMO = " + json.dumps(data, indent=1, ensure_ascii=False) + ";\n",
        encoding="utf-8",
    )
    frames = sum(len(s["frames"]) for s in data["scenarios"])
    print(f"wrote {OUT.relative_to(REPO)} — {len(data['scenarios'])} scenarios, {frames} frames "
          f"({version})", file=sys.stderr)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
