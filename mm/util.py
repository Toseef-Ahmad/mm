"""Time, color, lock — the boring primitives everything else shares."""
import os
import sys
from datetime import datetime, timezone

from .paths import P

try:
    import fcntl
    HAVE_FCNTL = True
except ImportError:
    HAVE_FCNTL = False

WEEKDAY_KEYS = ["Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun"]

_COLOR = sys.stdout.isatty() and not os.environ.get("NO_COLOR") and os.environ.get("TERM") != "dumb"


def _paint(s, code):
    return f"\033[{code}m{s}\033[0m" if _COLOR else s


def dim(s):    return _paint(s, "2")
def bold(s):   return _paint(s, "1")
def accent(s): return _paint(s, "36")
def good(s):   return _paint(s, "32")
def warn(s):   return _paint(s, "33")


def now_iso():
    return datetime.now(timezone.utc).astimezone().isoformat(timespec="seconds")


def today_str():
    return datetime.now(timezone.utc).astimezone().date().isoformat()


def today_weekday_key():
    """Locale-independent weekday key. strftime('%a') follows LC_TIME and
    silently returns non-English abbreviations — weekday tracks would vanish
    with no error. This never depends on locale."""
    return WEEKDAY_KEYS[datetime.now().weekday()]


class Lock:
    """Advisory file lock so two terminals never corrupt state.json together."""
    def __enter__(self):
        P.ensure()
        self.fh = open(P.lock, "w")
        if HAVE_FCNTL:
            fcntl.flock(self.fh, fcntl.LOCK_EX)
        return self

    def __exit__(self, *exc):
        if HAVE_FCNTL:
            fcntl.flock(self.fh, fcntl.LOCK_UN)
        self.fh.close()
