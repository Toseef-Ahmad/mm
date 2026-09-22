"""mm — a runtime queue. Nothing appears unless you add it."""

__version__ = "3.0.0"

from .cli import main
from .model import find_active, item_tag
from .paths import P, use_home
from .state import load, save
from .util import today_str


def __getattr__(name):
    mapping = {
        "STATE_DIR": lambda: P.dir,
        "STATE_PATH": lambda: P.state,
        "LOCK_PATH": lambda: P.lock,
    }
    if name in mapping:
        return mapping[name]()
    raise AttributeError(f"module 'mm' has no attribute {name!r}")
