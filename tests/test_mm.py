"""Tests for the MM universal focus engine.

Each test runs against a fresh, isolated MM_HOME tmpdir by monkeypatching mm's
module-level path constants, then drives the real CLI dispatch via mm.main().
No network, no shared state, stdlib only.
"""
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
        mm.STATE_DIR = self.tmp
        mm.STATE_PATH = os.path.join(self.tmp, "state.json")
        mm.LOCK_PATH = mm.STATE_PATH + ".lock"
        mm.BOOKS_PATH = os.path.join(self.tmp, "books.json")
        mm.BOOKS_CONFIG_PATH = os.path.join(self.tmp, "books_config.json")
        mm.RULES_PATH = os.path.join(self.tmp, "mm.rules.json")
        self._orig_weekday = mm.today_weekday_key
        mm.today_weekday_key = lambda: "Mon"  # deterministic weekday

    def tearDown(self):
        mm.today_weekday_key = self._orig_weekday
        shutil.rmtree(self.tmp, ignore_errors=True)

    # --- helpers ---
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

    def write_rules(self, rules):
        with open(mm.RULES_PATH, "w", encoding="utf-8") as f:
            json.dump(rules, f)

    def write_state(self, state):
        with open(mm.STATE_PATH, "w", encoding="utf-8") as f:
            json.dump(state, f)

    def texts(self, container):
        return [it["text"] for it in self.state()[container]]


class TestItemTag(MMTestCase):
    def test_shows_track_group_and_gate(self):
        books = {
            "books": [{"id": 2, "title": "CS201", "pages": 500, "page": 0,
                       "status": "queued", "group": "cs-core"}],
            "next_id": 3, "daily_units": 2,
        }
        with open(mm.BOOKS_PATH, "w", encoding="utf-8") as f:
            json.dump(books, f)
        item = {"id": 1, "text": "📖 [2] CS201 (0/500p)", "track": "books",
                "gate": True, "ref": 2, "group": "cs-core"}
        tag = mm.item_tag(item, books)
        self.assertIn("books", tag)
        self.assertIn("group:cs-core", tag)
        self.assertIn("gate", tag)

    def test_group_lookup_from_ref_when_missing_on_item(self):
        books = {
            "books": [{"id": 2, "title": "CS201", "pages": 500, "page": 0,
                       "status": "queued", "group": "cs-core"}],
            "next_id": 3, "daily_units": 2,
        }
        item = {"id": 1, "text": "📖 [2] CS201", "track": "books", "gate": True, "ref": 2}
        tag = mm.item_tag(item, books)
        self.assertIn("group:cs-core", tag)


class TestUniversalTracks(MMTestCase):
    def test_non_books_track_onboards_with_real_labels(self):
        self.write_rules({
            "onboard": {"strict_gate": True, "order": ["chores"]},
            "tracks": {
                "chores": {"type": "list", "dominant": True, "position": "gate",
                           "label": "🧹 {value}", "items": ["Clean desk", "Empty inbox"]},
            },
        })
        self.cli("onboard")
        q = self.state()["queue"]
        self.assertEqual([it["text"] for it in q], ["🧹 Clean desk", "🧹 Empty inbox"])
        for it in q:
            self.assertTrue(it.get("gate"))
            self.assertTrue(it.get("dominant"))
            self.assertEqual(it.get("track"), "chores")

    def test_multi_item_weekday(self):
        self.write_rules({
            "onboard": {"strict_gate": False, "order": ["learn"]},
            "tracks": {
                "learn": {"type": "weekday", "position": "back", "label": "📘 {value}",
                          "table": {"Mon": ["A", "B", "C"]}},
            },
        })
        self.cli("onboard")
        self.assertEqual(self.texts("queue"), ["📘 A", "📘 B", "📘 C"])


class TestCapacity(MMTestCase):
    def _small_queue_rules(self):
        self.write_rules({
            "onboard": {"strict_gate": True, "order": ["g", "b"]},
            "capacity": {"queue": {"max": 2, "on_full": "backlog"},
                         "stack": {"max": 1, "on_full": "reject"},
                         "quick": {"max": 50, "on_full": "warn"}},
            "tracks": {
                "g": {"type": "list", "dominant": True, "position": "gate",
                      "label": "G {value}", "items": ["G1"]},
                "b": {"type": "list", "position": "back", "label": "B {value}",
                      "items": ["B1", "B2", "B3"]},
            },
        })

    def test_overflow_goes_to_backlog(self):
        self._small_queue_rules()
        self.cli("onboard")
        # 1 gate (bypasses cap) + 1 back fills to max=2; rest overflow to backlog
        self.assertEqual(self.texts("queue"), ["G G1", "B B1"])
        self.assertEqual(self.texts("backlog"), ["B B2", "B B3"])

    def test_done_auto_promotes_from_backlog(self):
        self._small_queue_rules()
        self.cli("onboard")
        self.cli("done")  # finish the gate item -> frees a slot, next promotes
        q = self.texts("queue")
        self.assertIn("B B1", q)
        self.assertIn("B B2", q)  # promoted from backlog
        self.assertEqual(self.texts("backlog"), ["B B3"])

    def test_stack_reject_when_full(self):
        self.write_rules({
            "onboard": {"order": []},
            "capacity": {"queue": {"max": 10, "on_full": "backlog"},
                         "stack": {"max": 1, "on_full": "reject"},
                         "quick": {"max": 50, "on_full": "warn"}},
            "tracks": {},
        })
        self.cli("add", "-p", "first urgent")
        out = self.cli("add", "-p", "second urgent")
        self.assertIn("full", out.lower())
        self.assertEqual(len(self.state()["stack"]), 1)

    def test_manual_add_overflows_to_backlog(self):
        self.write_rules({
            "onboard": {"order": []},
            "capacity": {"queue": {"max": 1, "on_full": "backlog"},
                         "stack": {"max": 5, "on_full": "reject"},
                         "quick": {"max": 50, "on_full": "warn"}},
            "tracks": {},
        })
        self.cli("add", "task one")
        self.cli("add", "task two")
        self.assertEqual(self.texts("queue"), ["task one"])
        self.assertEqual(self.texts("backlog"), ["task two"])


class TestGate(MMTestCase):
    def _rules(self, strict=True):
        self.write_rules({
            "onboard": {"strict_gate": strict, "order": ["g", "b"]},
            "capacity": {"queue": {"max": 20, "on_full": "backlog"},
                         "stack": {"max": 5, "on_full": "reject"},
                         "quick": {"max": 50, "on_full": "warn"}},
            "tracks": {
                "g": {"type": "list", "dominant": True, "position": "gate",
                      "label": "G {value}", "items": ["G1"]},
                "b": {"type": "list", "position": "back", "label": "B {value}",
                      "items": ["B1"]},
            },
        })

    def test_gate_blocks_nongate_in_find_active(self):
        self._rules()
        self.cli("onboard")
        container, _idx, item = mm.find_active(self.state())
        self.assertEqual(container, "queue")
        self.assertEqual(item["text"], "G G1")  # non-gate B1 is unreachable

    def test_stack_still_preempts_gate(self):
        self._rules()
        self.cli("onboard")
        self.cli("add", "-p", "URGENT meeting")
        container, _idx, item = mm.find_active(self.state())
        self.assertEqual(container, "stack")
        self.assertEqual(item["text"], "URGENT meeting")

    def test_onboard_refuses_while_gate_open(self):
        self._rules(strict=True)
        self.cli("onboard")
        # Simulate a new day with yesterday's dominant work still undone.
        st = self.state()
        st["onboarded_date"] = "2000-01-01"
        self.write_state(st)
        out = self.cli("onboard")
        self.assertIn("Can't onboard", out)
        self.assertEqual(self.state().get("onboarded_date"), "2000-01-01")  # unchanged

    def test_nondominant_leftover_does_not_block(self):
        self.write_rules({
            "onboard": {"strict_gate": True, "order": ["b"]},
            "tracks": {"b": {"type": "list", "position": "back", "label": "B {value}",
                             "items": ["B1", "B2"]}},
        })
        self.cli("onboard")
        self.assertFalse(mm.has_open_gate(self.state()))
        container, _idx, item = mm.find_active(self.state())
        self.assertEqual(item["text"], "B B1")

    def test_carryover_gate_persists_and_no_duplicate(self):
        self._rules(strict=False)
        self.cli("onboard")
        st = self.state()
        st["onboarded_date"] = "2000-01-01"  # pretend it's a new day
        self.write_state(st)
        self.cli("onboard")  # soft gate: allowed
        # G1 still present exactly once (dedupe), still gating.
        self.assertEqual(self.texts("queue").count("G G1"), 1)
        self.assertTrue(mm.has_open_gate(self.state()))


class TestRobustness(MMTestCase):
    def test_empty_state_file_starts_fresh_quietly(self):
        # A 0-byte state.json must not spam a .corrupt- backup — just start fresh.
        open(mm.STATE_PATH, "w").close()
        self.cli("status")
        self.assertEqual(self.state()["queue"], [])
        leftovers = [f for f in os.listdir(self.tmp) if ".corrupt-" in f]
        self.assertEqual(leftovers, [])

    def test_missing_rules_disables_onboard_without_crashing(self):
        # No rules file at all → onboard queues nothing, no traceback.
        out = self.cli("onboard")
        self.assertIn("Onboarded", out)
        self.assertEqual(self.state()["queue"], [])


class TestRulesCommands(MMTestCase):
    def test_validate_ok(self):
        self.write_rules({
            "onboard": {"order": ["x"]},
            "tracks": {"x": {"type": "list", "position": "back", "label": "{value}", "items": ["a"]}},
        })
        out = self.cli("rules", "validate")
        self.assertIn("valid", out.lower())

    def test_validate_bad_type_exits(self):
        self.write_rules({
            "onboard": {"order": ["x"]},
            "tracks": {"x": {"type": "nonsense", "position": "back"}},
        })
        with self.assertRaises(SystemExit):
            self.cli("rules", "validate")

    def test_rules_show_does_not_mutate(self):
        self.write_rules({
            "onboard": {"order": ["x"]},
            "tracks": {"x": {"type": "list", "position": "gate", "dominant": True,
                             "label": "{value}", "items": ["a", "b"]}},
        })
        self.cli("rules", "show")
        self.assertEqual(self.state()["queue"], [])  # show never queues

    def test_capacity_set(self):
        self.write_rules({"onboard": {"order": []}, "tracks": {}})
        self.cli("capacity", "queue", "3")
        with open(mm.RULES_PATH, encoding="utf-8") as f:
            rules = json.load(f)
        self.assertEqual(rules["capacity"]["queue"]["max"], 3)


if __name__ == "__main__":
    unittest.main(verbosity=2)
