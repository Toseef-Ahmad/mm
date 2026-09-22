"""Queue / stack / quick only. Isolated MM_HOME. Stdlib only."""
import contextlib
import io
import json
import os
import shutil
import sys
import tempfile
import unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import mm  # noqa: E402


class MMTestCase(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.mkdtemp(prefix="mm-test-")
        mm.use_home(self.tmp)

    def tearDown(self):
        shutil.rmtree(self.tmp, ignore_errors=True)

    def cli(self, *argv):
        buf = io.StringIO()
        old_argv = sys.argv
        sys.argv = ["mm", *argv]
        try:
            with contextlib.redirect_stdout(buf), contextlib.redirect_stderr(buf):
                mm.main()
        finally:
            sys.argv = old_argv
        return buf.getvalue()

    def state(self):
        return mm.load()

    def texts(self, container):
        return [it["text"] for it in self.state()[container]]

    def ids(self, container):
        return [it["id"] for it in self.state()[container]]


class TestItemTag(MMTestCase):
    def test_clean_item_has_no_tag(self):
        self.assertEqual(mm.item_tag({"id": 1, "text": "CS302"}), "")

    def test_blocked_and_suspended_show(self):
        self.assertIn("blocked: waiting on API",
                      mm.item_tag({"id": 1, "text": "x", "blocked": True,
                                   "blocked_reason": "waiting on API"}))
        self.assertIn("suspended", mm.item_tag({"id": 2, "text": "y", "suspended": True}))


class TestEmptyBox(MMTestCase):
    def test_next_on_empty_tells_you_to_add(self):
        out = self.cli()
        self.assertIn("add something", out.lower())
        self.assertEqual(self.texts("queue"), [])
        self.assertEqual(self.texts("stack"), [])
        self.assertEqual(self.texts("quick"), [])

    def test_status_does_not_inject(self):
        self.cli("status")
        st = self.state()
        self.assertEqual(st["queue"], [])
        self.assertEqual(st["stack"], [])
        self.assertEqual(st["quick"], [])
        self.assertEqual(st["archive"], [])

    def test_state_file_is_only_what_was_added(self):
        self.cli("add", "CS302")
        path = os.path.join(self.tmp, "state.json")
        self.assertTrue(os.path.isfile(path))
        with open(path) as f:
            data = json.load(f)
        self.assertEqual([it["text"] for it in data["queue"]], ["CS302"])
        self.assertEqual(data["stack"], [])
        self.assertEqual(data["quick"], [])


class TestQueue(MMTestCase):
    def test_add_is_fifo(self):
        self.cli("add", "first")
        self.cli("add", "second")
        self.assertEqual(self.texts("queue"), ["first", "second"])
        out = self.cli()
        self.assertIn("first", out)
        kind, _idx, item = mm.find_active(self.state())
        self.assertEqual(kind, "queue")
        self.assertEqual(item["text"], "first")

    def test_done_advances_fifo(self):
        self.cli("add", "A")
        self.cli("add", "B")
        out = self.cli("done")
        self.assertIn("done", out.lower())
        self.assertIn("B", out)
        self.assertEqual(self.texts("queue"), ["B"])
        self.assertEqual(self.state()["archive"][0]["text"], "A")


class TestInterruptStack(MMTestCase):
    def test_priority_is_lifo_and_preempts_queue(self):
        self.cli("add", "queue work")
        self.cli("add", "-p", "first fire")
        self.cli("add", "-p", "second fire")
        self.assertEqual(self.texts("stack"), ["first fire", "second fire"])
        kind, _idx, item = mm.find_active(self.state())
        self.assertEqual(kind, "stack")
        self.assertEqual(item["text"], "second fire")
        self.cli("done")
        kind, _idx, item = mm.find_active(self.state())
        self.assertEqual(item["text"], "first fire")
        self.cli("done")
        kind, _idx, item = mm.find_active(self.state())
        self.assertEqual(kind, "queue")
        self.assertEqual(item["text"], "queue work")

    def test_add_p_prints_interrupt(self):
        out = self.cli("add", "-p", "prod is down")
        self.assertIn("interrupt", out.lower())


class TestQuick(MMTestCase):
    def test_quick_is_not_next(self):
        self.cli("add", "-q", "email Sam")
        self.assertEqual(self.texts("quick"), ["email Sam"])
        kind, _idx, item = mm.find_active(self.state())
        self.assertIsNone(item)
        out = self.cli()
        self.assertIn("quick waiting", out.lower())
        self.assertIn("all clear", out.lower())

    def test_flush_quick_clears(self):
        self.cli("add", "-q", "one")
        self.cli("add", "-q", "two")
        out = self.cli("flush-quick")
        self.assertIn("Flushing 2", out)
        self.assertEqual(self.texts("quick"), [])


class TestBlockSuspend(MMTestCase):
    def test_block_skips_and_unblock_restores(self):
        self.cli("add", "A")
        self.cli("add", "B")
        self.cli()  # start A
        self.cli("block", "waiting on CI")
        kind, _idx, item = mm.find_active(self.state())
        self.assertEqual(item["text"], "B")
        a = self.state()["queue"][-1]
        self.assertTrue(a["blocked"])
        self.cli("unblock", str(a["id"]))
        a = next(it for it in self.state()["queue"] if it["text"] == "A")
        self.assertFalse(a["blocked"])

    def test_suspend_and_resume(self):
        self.cli("add", "park me")
        self.cli("add", "keep going")
        self.cli()
        self.cli("suspend")
        kind, _idx, item = mm.find_active(self.state())
        self.assertEqual(item["text"], "keep going")
        parked = next(it for it in self.state()["queue"] if it["text"] == "park me")
        self.assertTrue(parked["suspended"])
        self.cli("resume", str(parked["id"]))
        parked = next(it for it in self.state()["queue"] if it["text"] == "park me")
        self.assertFalse(parked.get("suspended"))


class TestHousekeeping(MMTestCase):
    def test_move_edit_note_find_rm(self):
        self.cli("add", "original")
        iid = self.ids("queue")[0]
        self.cli("move", str(iid), "stack")
        self.assertEqual(self.texts("stack"), ["original"])
        self.assertEqual(self.texts("queue"), [])
        self.cli("edit", str(iid), "renamed")
        self.assertEqual(self.texts("stack"), ["renamed"])
        self.cli("note", str(iid), "a note")
        out = self.cli("find", "note")
        self.assertIn("renamed", out)
        self.cli("rm", str(iid))
        self.assertEqual(self.texts("stack"), [])

    def test_undo_restores_last_add(self):
        self.cli("add", "keep")
        self.cli("add", "drop")
        self.cli("undo")
        self.assertEqual(self.texts("queue"), ["keep"])


class TestLook(MMTestCase):
    def test_status_lists_three_containers(self):
        self.cli("add", "q-item")
        self.cli("add", "-p", "s-item")
        self.cli("add", "-q", "quick-item")
        out = self.cli("status")
        self.assertIn("interrupt", out)
        self.assertIn("queue", out)
        self.assertIn("quick", out)
        self.assertIn("q-item", out)
        self.assertIn("s-item", out)
        self.assertIn("quick-item", out)

    def test_stats_archive_export_log(self):
        self.cli("add", "task")
        self.cli("done")
        stats = self.cli("stats")
        self.assertIn("done", stats)
        arch = self.cli("archive")
        self.assertIn("task", arch)
        exported = self.cli("export", "json")
        rows = json.loads(exported)
        self.assertTrue(any(r["text"] == "task" and r["status"] == "done" for r in rows))
        log = self.cli("log")
        self.assertIn("enqueued", log)
        self.assertIn("done", log)

    def test_peek_does_not_start_timer(self):
        self.cli("add", "look")
        self.cli("peek")
        self.assertIsNone(self.state()["active"])
        self.cli("next")
        self.assertIsNotNone(self.state()["active"])


class TestRemovedPlanner(MMTestCase):
    def test_planner_verbs_are_gone(self):
        for cmd in ("onboard", "reset", "init", "rules", "habit", "book",
                    "capacity", "backlog", "session"):
            with self.assertRaises(SystemExit):
                self.cli(cmd)

    def test_next_does_not_seed_from_leftover_toml(self):
        with open(os.path.join(self.tmp, "mm.toml"), "w") as f:
            f.write('[[habits]]\nname = "ghost"\nrepeat = 1\n')
        self.cli()
        self.assertEqual(self.texts("queue"), [])
        self.assertEqual(self.texts("stack"), [])


if __name__ == "__main__":
    unittest.main()
