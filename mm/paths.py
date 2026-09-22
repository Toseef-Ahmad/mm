"""Filesystem layout. Tests call use_home(tmpdir) so nothing touches ~/.mm."""
import os


class Home:
    def configure(self, directory=None):
        if directory:
            self.dir = directory
            self.state = os.path.join(directory, "state.json")
            self.lock = self.state + ".lock"
            return self
        self.dir = os.environ.get("MM_HOME", os.path.expanduser("~/.mm"))
        self.state = os.environ.get("MM_STATE", os.path.join(self.dir, "state.json"))
        self.lock = self.state + ".lock"
        return self

    def ensure(self):
        os.makedirs(self.dir, exist_ok=True)


P = Home().configure()


def use_home(directory):
    P.configure(directory)
    return P
