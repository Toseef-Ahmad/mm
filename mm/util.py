"""Time, color, lock."""
import os
import sys
from datetime import datetime, timezone

from .paths import P

try:
    import fcntl
    HAVE_FCNTL = True
except ImportError:
    HAVE_FCNTL = False

try:
    import msvcrt
    HAVE_MSVCRT = True
except ImportError:
    HAVE_MSVCRT = False


def _windows_console():
    """UTF-8 and ANSI, so task text and color survive the Windows console."""
    if sys.platform != "win32":
        return
    for stream in (sys.stdout, sys.stderr):
        try:
            stream.reconfigure(encoding="utf-8", errors="replace")
        except (AttributeError, OSError, ValueError):
            pass
    try:
        import ctypes
        kernel32 = ctypes.windll.kernel32
        enable_vt = 0x0004
        mode = ctypes.c_uint()
        for handle_id in (-11, -12):
            handle = kernel32.GetStdHandle(handle_id)
            if kernel32.GetConsoleMode(handle, ctypes.byref(mode)):
                kernel32.SetConsoleMode(handle, mode.value | enable_vt)
    except (AttributeError, OSError, ValueError):
        pass


_windows_console()

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


class Lock:
    def __enter__(self):
        P.ensure()
        if HAVE_FCNTL:
            self.fh = open(P.lock, "w")
            fcntl.flock(self.fh, fcntl.LOCK_EX)
        elif HAVE_MSVCRT:
            # Region locks need at least one byte, and "w" would truncate a lock another process holds.
            self.fh = open(P.lock, "a+b")
            self.fh.seek(0, os.SEEK_END)
            if self.fh.tell() == 0:
                self.fh.write(b"\0")
                self.fh.flush()
            self.fh.seek(0)
            msvcrt.locking(self.fh.fileno(), msvcrt.LK_LOCK, 1)
        else:
            self.fh = open(P.lock, "w")
        return self

    def __exit__(self, *exc):
        try:
            if HAVE_FCNTL:
                fcntl.flock(self.fh, fcntl.LOCK_UN)
            elif HAVE_MSVCRT:
                self.fh.seek(0)
                msvcrt.locking(self.fh.fileno(), msvcrt.LK_UNLCK, 1)
        finally:
            self.fh.close()
