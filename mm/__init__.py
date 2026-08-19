"""mm — decide what's next, never when."""

__version__ = "2.1.0"

from .books import load_books
from .cli import main
from .model import find_active, has_open_gate, item_tag
from .paths import P, use_home
from .state import load, save
from .util import today_str, today_weekday_key


def __getattr__(name):
    """Path aliases so tests and callers can read the live home."""
    mapping = {
        "STATE_DIR": lambda: P.dir,
        "STATE_PATH": lambda: P.state,
        "LOCK_PATH": lambda: P.lock,
        "BOOKS_PATH": lambda: P.books,
        "BOOKS_CONFIG_PATH": lambda: P.books_config,
        "HABITS_PATH": lambda: P.habits,
        "RULES_PATH": lambda: P.rules_json,
    }
    if name in mapping:
        return mapping[name]()
    raise AttributeError(f"module 'mm' has no attribute {name!r}")
