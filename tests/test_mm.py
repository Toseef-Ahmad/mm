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
import mm.habits  # noqa: E402


class MMTestCase(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.mkdtemp(prefix="mm-test-")
        mm.use_home(self.tmp)
        import mm.ops as ops
        self._ops = ops
        self._orig_weekday = ops.today_weekday_key
        ops.today_weekday_key = lambda: "Mon"

    def tearDown(self):
        self._ops.today_weekday_key = self._orig_weekday
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
    def test_clean_item_has_no_tag_noise(self):
        # A normal gate item shows nothing extra — track/group/gate are section context.
        item = {"id": 1, "text": "CS201  0/500p", "track": "books", "gate": True}
        self.assertEqual(mm.item_tag(item), "")

    def test_blocked_and_suspended_states_show(self):
        self.assertIn("blocked: waiting on API",
                      mm.item_tag({"id": 1, "text": "x", "blocked": True,
                                   "blocked_reason": "waiting on API"}))
        self.assertIn("suspended", mm.item_tag({"id": 2, "text": "y", "suspended": True}))

    def test_gate_locked_items_say_so_in_status(self):
        """A non-gate item can sit on top via `order`; the pointer still skips it,
        so the line has to explain itself."""
        self.write_rules({
            "onboard": {"strict_gate": False, "order": []},
            "tracks": {},
            "habits": [
                {"name": "Meditation", "type": "mind", "repeat": 1, "enabled": 1,
                 "archived": 0, "position": "queue", "gate": False, "weight": 1, "order": 1},
                {"name": "CS302", "type": "book", "repeat": 1, "enabled": 1,
                 "archived": 0, "position": "queue", "gate": True, "weight": 4},
            ],
        })
        out = self.cli("status")
        self.assertIn("gate-locked", out)
        med = next(ln for ln in out.splitlines() if "Meditation" in ln)
        cs = next(ln for ln in out.splitlines() if "CS302" in ln)
        self.assertIn("gate-locked", med)
        self.assertNotIn("gate-locked", cs)
        self.assertIn("→", cs)  # the pointer sits on the first reachable item


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
        self.assertIn("onboarded", out.lower())
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


class TestOnboardEscapeHatches(MMTestCase):
    def _rules(self, strict=True):
        self.write_rules({
            "onboard": {"strict_gate": strict, "order": ["g", "b"]},
            "tracks": {
                "g": {"type": "list", "dominant": True, "position": "gate",
                      "label": "G {value}", "items": ["G1"]},
                "b": {"type": "list", "position": "back", "label": "B {value}",
                      "items": ["B1"]},
            },
        })

    def test_force_onboards_with_open_gate(self):
        self._rules(strict=True)
        self.cli("onboard")
        st = self.state()
        st["onboarded_date"] = "2000-01-01"
        self.write_state(st)
        out = self.cli("onboard", "--force")
        self.assertNotIn("Can't onboard", out)
        self.assertEqual(self.state().get("onboarded_date"), mm.today_str())
        self.assertEqual(self.texts("queue").count("G G1"), 1)

    def test_again_reseeds_same_day(self):
        self._rules(strict=False)
        self.cli("onboard")
        blocked = self.cli("onboard")
        self.assertIn("already onboarded", blocked)
        out = self.cli("onboard", "--again")
        self.assertNotIn("already onboarded", out)
        self.assertIn("onboarded", out.lower())

    def test_reset_parks_gates_and_unlocks_onboard(self):
        self._rules(strict=True)
        self.cli("onboard")
        self.assertTrue(mm.has_open_gate(self.state()))
        out = self.cli("reset", "--park-gates")
        self.assertIn("reset", out.lower())
        self.assertFalse(mm.has_open_gate(self.state()))
        self.assertIsNone(self.state().get("onboarded_date"))
        self.assertTrue(any(it.get("suspended") for it in self.state()["queue"] if it.get("gate")))
        again = self.cli("onboard")
        self.assertNotIn("Can't onboard", again)

    def test_reset_alone_does_not_park(self):
        self._rules(strict=True)
        self.cli("onboard")
        self.cli("reset")
        self.assertTrue(mm.has_open_gate(self.state()))
        self.assertFalse(any(it.get("suspended") for it in self.state()["queue"]))
        self.assertIsNone(self.state().get("onboarded_date"))

    def test_reset_drop_gates_removes_them(self):
        self._rules(strict=True)
        self.cli("onboard")
        archive_before = len(self.state()["archive"])
        self.cli("reset", "--drop-gates")
        self.assertFalse(any(it.get("gate") and not it.get("suspended") for it in self.state()["queue"]))
        self.assertEqual(self.texts("queue"), ["B B1"])
        self.assertEqual(len(self.state()["archive"]), archive_before)

    def test_rules_strict_toggle(self):
        self.write_rules({"onboard": {"strict_gate": True, "order": []}, "tracks": {}})
        self.cli("rules", "strict", "off")
        with open(mm.RULES_PATH, encoding="utf-8") as f:
            rules = json.load(f)
        self.assertFalse(rules["onboard"]["strict_gate"])
        self.cli("rules", "strict", "on")
        with open(mm.RULES_PATH, encoding="utf-8") as f:
            rules = json.load(f)
        self.assertTrue(rules["onboard"]["strict_gate"])


class TestBooksFlexible(MMTestCase):
    def _rotation_rules(self):
        self.write_rules({
            "onboard": {"strict_gate": False, "order": ["books"]},
            "tracks": {
                "books": {"type": "rotation", "count": 2, "dominant": True,
                          "position": "gate", "label": "{value}"},
            },
        })

    def test_add_without_pages_is_checklist_and_done_closes(self):
        self._rotation_rules()
        self.cli("book", "add", "Thinking", "Mathematically")
        book = mm.load_books()["books"][0]
        self.assertEqual(book["title"], "Thinking Mathematically")
        self.assertEqual(book["pages"], 0)
        self.cli("onboard")
        self.assertEqual(self.texts("queue"), ["Thinking Mathematically"])
        out = self.cli("done")
        self.assertIn("done", out.lower())
        self.assertNotIn("not closed", out.lower())
        self.assertEqual(self.state()["queue"], [])

    def test_add_with_pages_still_requires_progress(self):
        self._rotation_rules()
        self.cli("book", "add", "CS302", "500")
        self.cli("onboard")
        out = self.cli("done")
        self.assertIn("not closed", out.lower())
        self.assertEqual(self.texts("queue"), ["CS302"])

    def test_book_daily_and_sync_prune(self):
        self.cli("book", "add", "OLD")
        self.cli("book", "daily", "4")
        self.assertEqual(mm.load_books()["daily_units"], 4)
        with open(mm.BOOKS_CONFIG_PATH, "w", encoding="utf-8") as f:
            json.dump({"daily_units": 4, "books": [
                {"title": "CS301", "pages": 0},
                {"title": "PSY101", "pages": 0},
            ]}, f)
        out = self.cli("book", "sync", "--prune")
        self.assertIn("pruned", out.lower())
        titles = [b["title"] for b in mm.load_books()["books"]]
        self.assertEqual(titles, ["CS301", "PSY101"])

    def test_book_add_updates_declared_list(self):
        self.cli("book", "add", "CS201")
        with open(mm.BOOKS_CONFIG_PATH, encoding="utf-8") as f:
            config = json.load(f)
        self.assertEqual(config["books"][0]["title"], "CS201")
        self.cli("book", "rm", "1")
        with open(mm.BOOKS_CONFIG_PATH, encoding="utf-8") as f:
            config = json.load(f)
        self.assertEqual(config["books"], [])


class TestGenericRotation(MMTestCase):
    def test_rotation_over_plain_items(self):
        self.write_rules({
            "onboard": {"strict_gate": False, "order": ["kata"]},
            "tracks": {
                "kata": {"type": "rotation", "count": 2, "dominant": True,
                         "position": "gate", "label": "{value}",
                         "items": ["A", "B", "C", "D"]},
            },
        })
        self.cli("onboard")
        q = self.texts("queue")
        self.assertEqual(len(q), 2)
        self.assertTrue(set(q).issubset({"A", "B", "C", "D"}))

    def test_toml_config_loads(self):
        from mm.config import dumps_toml
        body = dumps_toml({
            "onboard": {"strict_gate": False, "order": ["one"]},
            "tracks": {"one": {"type": "static", "position": "back",
                               "label": "{value}", "items": ["Hello"]}},
        })
        with open(mm.P.rules_toml, "w", encoding="utf-8") as f:
            f.write(body)
        self.cli("onboard")
        self.assertEqual(self.texts("queue"), ["Hello"])


class TestManual(MMTestCase):
    def test_man_page_ships_in_tree(self):
        import mm.cli as cli
        page = cli._man_page()
        self.assertIsNotNone(page)
        text = page.read_text(encoding="utf-8")
        self.assertIn(".TH MM 1", text)
        self.assertIn(".SH FILES", text)
        self.assertIn("mm.toml", text)


class TestHabits(MMTestCase):
    def _habit(self, **kw):
        row = {"name": "Walk", "type": "fitness", "repeat": 1, "enabled": 1,
               "archived": 0, "position": "queue", "gate": True, "weight": 1}
        row.update(kw)
        return row

    def _rules(self, *habits, strict=False):
        self.write_rules({
            "onboard": {"strict_gate": strict, "order": []},
            "capacity": {"queue": {"max": 20, "on_full": "backlog"},
                         "stack": {"max": 5, "on_full": "reject"},
                         "quick": {"max": 50, "on_full": "warn"}},
            "tracks": {},
            "habits": list(habits),
        })

    def test_repeat_3_not_due_on_gap_days(self):
        from mm.habits import is_due_on, streak_from_history
        h, err = mm.habits.normalize_habit(self._habit(repeat=3))
        self.assertIsNone(err)
        anchor = "2026-08-17"
        self.assertTrue(is_due_on(h, "2026-08-17", anchor))
        self.assertFalse(is_due_on(h, "2026-08-18", anchor))
        self.assertFalse(is_due_on(h, "2026-08-19", anchor))
        self.assertTrue(is_due_on(h, "2026-08-20", anchor))
        history = {"2026-08-17": "done"}
        # Gap days must not break the streak.
        self.assertEqual(streak_from_history(h, history, "2026-08-18", anchor), 1)
        self.assertEqual(streak_from_history(h, history, "2026-08-19", anchor), 1)
        # Next due not yet done — still 1, in progress.
        self.assertEqual(streak_from_history(h, history, "2026-08-20", anchor), 1)
        history["2026-08-20"] = "done"
        self.assertEqual(streak_from_history(h, history, "2026-08-20", anchor), 2)
        history["2026-08-20"] = "missed"
        self.assertEqual(streak_from_history(h, history, "2026-08-21", anchor), 0)

    def test_auto_injects_on_next_into_chosen_container(self):
        self._rules(
            self._habit(name="CS302", type="book", position="queue", gate=True),
            self._habit(name="Urgent stretch", type="fitness", position="stack", gate=False),
            self._habit(name="Floss", type="health", position="quick", gate=False),
        )
        self.cli("next")
        st = self.state()
        self.assertEqual(self.texts("queue"), ["CS302"])
        self.assertTrue(st["queue"][0].get("gate"))
        self.assertEqual(st["queue"][0].get("habit"), "CS302")
        self.assertEqual(self.texts("stack"), ["Urgent stretch"])
        self.assertEqual(self.texts("quick"), ["Floss"])

    def test_disabled_and_archived_stay_out(self):
        self._rules(
            self._habit(name="On", enabled=1),
            self._habit(name="Off", enabled=0),
            self._habit(name="Old", archived=1),
        )
        self.cli("next")
        self.assertEqual(self.texts("queue"), ["On"])

    def test_no_duplicate_while_open(self):
        self._rules(self._habit(name="CS302", type="book"))
        self.cli("next")
        self.cli("next")
        self.assertEqual(self.texts("queue"), ["CS302"])

    def test_done_records_streak_and_find_by_type(self):
        self._rules(self._habit(name="CS302", type="book"))
        self.cli("next")
        out = self.cli("done")
        self.assertIn("done", out.lower())
        self.assertIn("streak", out.lower())
        progress = mm.habits.load_progress()
        slot = progress["habits"]["CS302"]
        self.assertEqual(slot["streak"], 1)
        self.assertIn("done", slot["history"].values())
        found = self.cli("habit", "find", "book")
        self.assertIn("CS302", found)

    def test_set_position_and_search_metadata(self):
        self._rules(self._habit(name="CS302", type="book", position="queue"))
        self.cli("habit", "set", "CS302", "position", "quick")
        self.cli("habit", "set", "CS302", "repeat", "3")
        h = mm.habits.find_declared("CS302")
        self.assertEqual(h["position"], "quick")
        self.assertEqual(h["repeat"], 3)
        listed = self.cli("habit", "list", "-t", "book")
        self.assertIn("CS302", listed)

    def test_miss_resets_streak(self):
        self._rules(self._habit(name="Meditate", type="mind"))
        self.cli("next")
        self.cli("done")
        self.assertEqual(mm.habits.load_progress()["habits"]["Meditate"]["streak"], 1)
        # Force another due instance: mark history so today isn't done, inject, miss.
        progress = mm.habits.load_progress()
        progress["habits"]["Meditate"]["history"] = {}
        mm.habits.save_progress(progress)
        self.cli("habit", "miss", "Meditate")
        self.assertEqual(mm.habits.load_progress()["habits"]["Meditate"]["streak"], 0)

    def test_past_due_without_open_item_is_missed(self):
        from datetime import date, timedelta
        from mm.habits import ensure_due_habits, load_progress
        self._rules(self._habit(name="Walk", type="fitness", repeat=1))
        yesterday = (date.fromisoformat(mm.today_str()) - timedelta(days=1)).isoformat()
        today = mm.today_str()
        # Pretend it was already known yesterday, never done.
        mm.habits.save_progress({"habits": {"Walk": {
            "anchor": yesterday, "streak": 4, "best_streak": 4,
            "points": 0, "history": {},
        }}})
        st = self.state()
        ensure_due_habits(st, today=today)
        hist = load_progress()["habits"]["Walk"]["history"]
        self.assertEqual(hist.get(yesterday), "missed")
        self.assertEqual(load_progress()["habits"]["Walk"]["streak"], 0)
        self.assertTrue(any(it.get("habit") == "Walk" for it in st["queue"]))

    def test_weight_orders_queue_not_file_order(self):
        self._rules(
            self._habit(name="Low", type="book", weight=1, gate=True),
            self._habit(name="High", type="book", weight=10, gate=True),
        )
        self.cli("next")
        self.assertEqual(self.texts("queue"), ["High", "Low"])
        self.cli("habit", "set", "Low", "weight", "20")
        self.assertEqual(self.texts("queue"), ["Low", "High"])

    def test_weekday_filter(self):
        from mm.habits import is_due_on, normalize_habit
        h, err = normalize_habit(self._habit(name="Deep", days=["Mon"], repeat=1))
        self.assertIsNone(err)
        # 2026-08-17 is a Monday.
        self.assertTrue(is_due_on(h, "2026-08-17", "2026-08-17"))
        self.assertFalse(is_due_on(h, "2026-08-18", "2026-08-17"))

    def test_new_day_fresh_items_unfinished_are_missed(self):
        from mm.habits import ensure_due_habits, load_progress
        self._rules(
            self._habit(name="High", weight=10, gate=True),
            self._habit(name="Low", weight=1, gate=True),
            self._habit(name="Walk", weight=5, gate=False),
        )
        yesterday, today = "2026-08-18", "2026-08-19"
        mm.habits.save_progress({"habits": {n: {
            "anchor": yesterday, "streak": 0, "best_streak": 0, "points": 0, "history": {},
        } for n in ("High", "Low", "Walk")}})
        st = self.state()
        ensure_due_habits(st, today=yesterday)
        self.assertEqual(
            [it["habit"] for it in st["queue"]],
            ["High", "Walk", "Low"],
        )
        ensure_due_habits(st, today=today)
        self.assertEqual(
            [(it["habit"], it["habit_due"]) for it in st["queue"]],
            [("High", today), ("Walk", today), ("Low", today)],
        )
        names = [it["habit"] for it in st["queue"]]
        self.assertEqual(len(names), len(set(names)))
        hist = load_progress()["habits"]["High"]["history"]
        self.assertEqual(hist.get(yesterday), "missed")
        self.assertEqual(load_progress()["habits"]["High"]["streak"], 0)

    def test_done_yesterday_keeps_streak_and_queues_today(self):
        from mm.habits import ensure_due_habits, load_progress, record_done
        self._rules(self._habit(name="CS302", gate=True, weight=4))
        yesterday, today = "2026-08-18", "2026-08-19"
        mm.habits.save_progress({"habits": {"CS302": {
            "anchor": yesterday, "streak": 0, "best_streak": 0, "points": 0, "history": {},
        }}})
        st = self.state()
        ensure_due_habits(st, today=yesterday)
        item = st["queue"][0]
        record_done(st, item, today=yesterday)
        st["queue"].remove(item)
        ensure_due_habits(st, today=today)
        self.assertEqual(
            [(it["habit"], it["habit_due"]) for it in st["queue"]],
            [("CS302", today)],
        )
        slot = load_progress()["habits"]["CS302"]
        self.assertEqual(slot["history"].get(yesterday), "done")
        self.assertNotEqual(slot["history"].get(today), "done")
        self.assertEqual(slot["streak"], 1)

    def test_older_leftover_gap_is_missed_and_today_is_fresh(self):
        from mm.habits import ensure_due_habits, load_progress
        self._rules(self._habit(name="CS302", gate=True))
        older, gap, today = "2026-08-17", "2026-08-18", "2026-08-19"
        mm.habits.save_progress({"habits": {"CS302": {
            "anchor": older, "streak": 0, "best_streak": 0, "points": 0, "history": {},
        }}})
        st = self.state()
        ensure_due_habits(st, today=older)
        ensure_due_habits(st, today=today)
        hist = load_progress()["habits"]["CS302"]["history"]
        self.assertEqual(hist.get(older), "missed")
        self.assertEqual(hist.get(gap), "missed")
        dues = [it["habit_due"] for it in st["queue"] if it.get("habit") == "CS302"]
        self.assertEqual(dues, [today])

    def test_order_puts_habit_in_front(self):
        self._rules(
            self._habit(name="Heavy", weight=10, gate=True),
            self._habit(name="Exercise", weight=1, gate=False, order=1),
        )
        self.cli("next")
        self.assertEqual(self.texts("queue")[0], "Exercise")
        self.cli("habit", "set", "Heavy", "order", "1")
        self.cli("habit", "set", "Exercise", "order", "2")
        self.assertEqual(self.texts("queue"), ["Heavy", "Exercise"])

    def test_same_due_is_not_duplicated(self):
        from mm.habits import ensure_due_habits
        self._rules(self._habit(name="CS302", gate=True))
        st = self.state()
        ensure_due_habits(st, today="2026-08-19")
        ensure_due_habits(st, today="2026-08-19")
        self.assertEqual(len(st["queue"]), 1)


class TestObsidian(MMTestCase):
    TEMPLATE = """---
type: daily
topic:
  - personal
energy: 3
exercise: false
cs302: false
---
# <% tp.date.now("YYYY-MM-DD") %>, <% tp.date.now("dddd") %>

## Daily targets

| Target | Property | Weight |
|---|---|---|
| CS302 | `cs302` | 80 |
| Exercise | `exercise` | 70 |
"""

    def _vault(self, extra_habits=None):
        vault = os.path.join(self.tmp, "vault")
        folder = os.path.join(vault, "20 Journal", "Personal")
        tdir = os.path.join(vault, "80 System", "Templates")
        os.makedirs(folder)
        os.makedirs(tdir)
        os.makedirs(os.path.join(vault, ".obsidian"))
        with open(os.path.join(tdir, "Daily Journal Template.md"), "w", encoding="utf-8") as f:
            f.write(self.TEMPLATE)
        habits = extra_habits or [
            self._habit(name="CS302", type="book", gate=True, weight=4, obsidian="cs302"),
        ]
        self.write_rules({
            "onboard": {"strict_gate": False, "order": []},
            "capacity": {"queue": {"max": 20, "on_full": "backlog"},
                         "stack": {"max": 5, "on_full": "reject"},
                         "quick": {"max": 50, "on_full": "warn"}},
            "tracks": {},
            "habits": habits,
            "obsidian": {
                "enabled": True,
                "vault": vault,
                "folder": "20 Journal/Personal",
                "template": "80 System/Templates/Daily Journal Template.md",
            },
        })
        return vault

    def _habit(self, **kw):
        row = {"name": "Walk", "type": "fitness", "repeat": 1, "enabled": 1,
               "archived": 0, "position": "queue", "gate": True, "weight": 1}
        row.update(kw)
        return row

    def test_frontmatter_parse_and_bool_write(self):
        from mm.obsidian import parse_frontmatter, set_frontmatter_bool, resolve_templater
        props, body = parse_frontmatter(self.TEMPLATE)
        self.assertEqual(props["energy"], 3)
        self.assertFalse(props["cs302"])
        self.assertEqual(props["topic"], ["personal"])
        updated = set_frontmatter_bool(self.TEMPLATE, "cs302", True)
        self.assertRegex(updated, r"(?m)^cs302:\s*true$")
        updated = set_frontmatter_bool(updated, "screeps", False)
        p2, _ = parse_frontmatter(updated)
        self.assertFalse(p2["screeps"])
        resolved = resolve_templater(self.TEMPLATE, "2026-08-19")
        self.assertIn("2026-08-19", resolved)
        self.assertIn("Wednesday", resolved)
        self.assertNotIn("<%", resolved)

    def test_write_daily_does_not_clobber_checked_box(self):
        from mm.obsidian import write_daily, parse_frontmatter, read_note
        path = os.path.join(self.tmp, "day.md")
        with open(path, "w", encoding="utf-8") as f:
            f.write(self.TEMPLATE.replace("exercise: false", "exercise: true"))
        stale = self.TEMPLATE  # still says exercise: false
        write_daily(path, stale)
        props, _ = parse_frontmatter(read_note(path))
        self.assertTrue(props["exercise"])

    def test_uncheck_reopens_habit(self):
        from mm.obsidian import apply_obsidian, daily_note_path, obsidian_cfg, parse_frontmatter, read_note
        from mm.habits import ensure_due_habits, load_progress
        self._vault(extra_habits=[
            self._habit(name="Exercise", type="fitness", gate=False, weight=1, obsidian="exercise"),
        ])
        cfg = obsidian_cfg()
        day = mm.today_str()
        path = daily_note_path(cfg, day)
        os.makedirs(os.path.dirname(path), exist_ok=True)
        with open(path, "w", encoding="utf-8") as f:
            f.write(self.TEMPLATE.replace("exercise: false", "exercise: true"))
        st = self.state()
        apply_obsidian(st, today=day, phase="before")
        ensure_due_habits(st, today=day)
        self.assertEqual(load_progress()["habits"]["Exercise"]["history"].get(day), "done")
        self.assertFalse(any(it.get("habit") == "Exercise" for it in st["queue"]))
        with open(path, "w", encoding="utf-8") as f:
            f.write(self.TEMPLATE)
        apply_obsidian(st, today=day, phase="before")
        ensure_due_habits(st, today=day)
        apply_obsidian(st, today=day, phase="after")
        self.assertNotEqual(load_progress()["habits"]["Exercise"]["history"].get(day), "done")
        self.assertTrue(any(it.get("habit") == "Exercise" for it in st["queue"]))
        self.assertFalse(parse_frontmatter(read_note(path))[0]["exercise"])

    def test_mm_done_is_not_reversed_by_the_pull(self):
        """The note still says false when mm closes an item; that is not an uncheck."""
        from mm.obsidian import daily_note_path, obsidian_cfg, parse_frontmatter, read_note
        from mm.habits import load_progress
        self._vault(extra_habits=[
            self._habit(name="Exercise", type="fitness", gate=False, weight=1, obsidian="exercise"),
        ])
        cfg = obsidian_cfg()
        day = mm.today_str()
        path = daily_note_path(cfg, day)
        os.makedirs(os.path.dirname(path), exist_ok=True)
        with open(path, "w", encoding="utf-8") as f:
            f.write(self.TEMPLATE)
        self.cli("status")
        item = next(it for it in self.state()["queue"] if it.get("habit") == "Exercise")
        self.cli("done", str(item["id"]))
        self.assertEqual(load_progress()["habits"]["Exercise"]["history"].get(day), "done")
        self.assertFalse(any(it.get("habit") == "Exercise" for it in self.state()["queue"]))
        self.assertTrue(parse_frontmatter(read_note(path))[0]["exercise"])
        # And a second look must not treat our own pushed true as a fresh tick.
        self.cli("status")
        self.assertFalse(any(it.get("habit") == "Exercise" for it in self.state()["queue"]))

    def test_pull_marks_done_and_push_writes_true(self):
        from mm.obsidian import apply_obsidian, daily_note_path, obsidian_cfg, parse_frontmatter, read_note
        from mm.habits import ensure_due_habits, load_progress
        self._vault()
        cfg = obsidian_cfg()
        day = mm.today_str()
        path = daily_note_path(cfg, day)
        os.makedirs(os.path.dirname(path), exist_ok=True)
        note = self.TEMPLATE.replace("cs302: false", "cs302: true")
        with open(path, "w", encoding="utf-8") as f:
            f.write(note)
        st = self.state()
        apply_obsidian(st, today=day, phase="before")
        hist = load_progress()["habits"]["CS302"]["history"]
        self.assertEqual(hist.get(day), "done")
        self.assertFalse(any(it.get("habit") == "CS302" for it in st["queue"]))
        ensure_due_habits(st, today=day)
        self.assertFalse(any(it.get("habit") == "CS302" and it.get("habit_due") == day for it in st["queue"]))

        with open(mm.RULES_PATH, encoding="utf-8") as f:
            existing = json.load(f)
        existing["habits"] = [
            self._habit(name="CS302", type="book", gate=True, weight=4, obsidian="cs302"),
            self._habit(name="Exercise", type="fitness", gate=False, weight=1, obsidian="exercise"),
        ]
        self.write_rules(existing)
        progress = load_progress()
        progress.setdefault("habits", {})["Exercise"] = {
            "anchor": day, "streak": 1, "best_streak": 1, "points": 1,
            "history": {day: "done"},
        }
        mm.habits.save_progress(progress)
        apply_obsidian(st, today=day, phase="after")
        props, _ = parse_frontmatter(read_note(path))
        self.assertTrue(props["cs302"])
        self.assertTrue(props["exercise"])

    def test_reconcile_adds_habit_from_table(self):
        from mm.obsidian import apply_obsidian
        from mm.habits import find_declared
        self._vault(extra_habits=[
            self._habit(name="CS302", type="book", gate=True, weight=4, obsidian="cs302"),
        ])
        st = self.state()
        apply_obsidian(st, today=mm.today_str(), phase="before")
        ex = find_declared("Exercise")
        self.assertIsNotNone(ex)
        self.assertEqual(ex["obsidian"], "exercise")
        self.assertFalse(ex["gate"])

    def test_new_mm_habit_adds_property(self):
        from mm.obsidian import apply_obsidian, daily_note_path, obsidian_cfg, parse_frontmatter, read_note
        self._vault(extra_habits=[
            self._habit(name="CS302", type="book", gate=True, weight=4, obsidian="cs302"),
            self._habit(name="Screeps", type="course", gate=True, weight=2, obsidian="screeps"),
        ])
        st = self.state()
        day = mm.today_str()
        apply_obsidian(st, today=day, phase="before")
        cfg = obsidian_cfg()
        props, body = parse_frontmatter(read_note(daily_note_path(cfg, day)))
        self.assertIn("screeps", props)
        self.assertIn("`screeps`", body)

    def test_checkbox_types_registered_in_vault(self):
        from mm.obsidian import apply_obsidian, types_path, obsidian_cfg
        self._vault()
        apply_obsidian(self.state(), today=mm.today_str(), phase="before")
        cfg = obsidian_cfg()
        with open(types_path(cfg), encoding="utf-8") as f:
            types = json.load(f)["types"]
        self.assertEqual(types["exercise"], "checkbox")
        self.assertEqual(types["cs302"], "checkbox")
        self.assertEqual(types["energy"], "number")


if __name__ == "__main__":
    unittest.main(verbosity=2)
