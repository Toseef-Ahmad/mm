"""Queue/stack/quick persistence. One JSON file, atomic writes, quiet recovery."""
import copy
import json
import os
import tempfile
from datetime import datetime

from .paths import P
from .util import now_iso

EMPTY_STATE = {
    "queue": [], "stack": [], "quick": [], "backlog": [], "log": [], "next_id": 1, "active": None,
    "archive": [], "sessions": [], "_snapshots": [], "onboarded_date": None,
    "gate_days": [],
}


def load():
    P.ensure()
    if not os.path.exists(P.state):
        return copy.deepcopy(EMPTY_STATE)
    if os.path.getsize(P.state) == 0:
        return copy.deepcopy(EMPTY_STATE)
    try:
        with open(P.state) as f:
            data = json.load(f)
        for k, v in EMPTY_STATE.items():
            data.setdefault(k, v if not isinstance(v, (list, dict)) else type(v)())
        return data
    except (json.JSONDecodeError, OSError) as e:
        backup = P.state + f".corrupt-{int(datetime.now().timestamp())}"
        try:
            os.replace(P.state, backup)
        except OSError:
            pass
        print(f"⚠️  State file was corrupted ({e}). Backed up to {backup}. Starting fresh.", file=__import__("sys").stderr)
        return copy.deepcopy(EMPTY_STATE)


def save(state):
    P.ensure()
    fd, tmp = tempfile.mkstemp(dir=P.dir, prefix=".state-", suffix=".tmp")
    try:
        with os.fdopen(fd, "w") as f:
            json.dump(state, f, indent=2)
            f.flush()
            os.fsync(f.fileno())
        os.replace(tmp, P.state)
    finally:
        if os.path.exists(tmp):
            os.remove(tmp)


def log_event(state, msg):
    state["log"].append({"ts": now_iso(), "event": msg})
    state["log"] = state["log"][-1000:]


def snapshot(state):
    snap = copy.deepcopy({k: v for k, v in state.items() if k != "_snapshots"})
    state["_snapshots"].append(snap)
    state["_snapshots"] = state["_snapshots"][-15:]
