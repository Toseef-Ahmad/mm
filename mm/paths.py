"""Filesystem layout. One object, one home directory.

Tests call `use_home(tmpdir)` so nothing ever touches ~/.mm.
Production reads $MM_HOME (default ~/.mm).
"""
import os


class Home:
    def configure(self, directory=None):
        if directory:
            self.dir = directory
            self.state = os.path.join(directory, "state.json")
            self.lock = self.state + ".lock"
            self.books = os.path.join(directory, "books.json")
            self.books_config = os.path.join(directory, "books_config.json")
            self.habits = os.path.join(directory, "habits.json")
            self.rules_json = os.path.join(directory, "mm.rules.json")
            self.rules_toml = os.path.join(directory, "mm.toml")
            return self
        self.dir = os.environ.get("MM_HOME", os.path.expanduser("~/.mm"))
        self.state = os.environ.get("MM_STATE", os.path.join(self.dir, "state.json"))
        self.lock = self.state + ".lock"
        self.books = os.environ.get("MM_BOOKS", os.path.join(self.dir, "books.json"))
        self.books_config = os.environ.get("MM_BOOKS_CONFIG", os.path.join(self.dir, "books_config.json"))
        self.habits = os.environ.get("MM_HABITS", os.path.join(self.dir, "habits.json"))
        self.rules_json = os.environ.get("MM_RULES", os.path.join(self.dir, "mm.rules.json"))
        self.rules_toml = os.path.join(self.dir, "mm.toml")
        return self

    def ensure(self):
        os.makedirs(self.dir, exist_ok=True)

    @property
    def rules(self):
        """Active config file: TOML wins when present, JSON remains the fallback."""
        if os.path.exists(self.rules_toml):
            return self.rules_toml
        return self.rules_json

    @property
    def rules_kind(self):
        if os.path.exists(self.rules_toml):
            return "toml"
        if os.path.exists(self.rules_json):
            return "json"
        return None


P = Home().configure()


def use_home(directory):
    """Point the whole process at an isolated directory (tests, extra instances)."""
    P.configure(directory)
    return P
