"""Testy nadzorcy petli. Uruchom: python3 run_tests.py  (bez zaleznosci, stdlib unittest)."""
from __future__ import annotations

import os
import random
import shutil
import tempfile
import unittest

import world as W
from agentloop import (Action, Budget, Done, Journal, SimulatedCrash, Supervisor, VirtualClock,
                       backoff_delay, detect_loop, detect_no_progress, error_signature, fingerprint)


class Base(unittest.TestCase):
    def setUp(self):
        self.dir = tempfile.mkdtemp(prefix="prasowka-loop-")
        self.jpath = os.path.join(self.dir, "journal.jsonl")
        self.w = W.World()

    def tearDown(self):
        shutil.rmtree(self.dir, ignore_errors=True)

    def sup(self, budget=None, world=None, **kw):
        w = world or self.w
        return Supervisor(w.tools(), budget or Budget(), Journal(self.jpath), **kw)


class TestPureFunctions(unittest.TestCase):
    def test_signature_ignores_numbers(self):
        self.assertEqual(error_signature("FAIL at Foo.cs:12\nstack"), error_signature("FAIL at Foo.cs:97"))

    def test_fingerprint_key_order_independent(self):
        self.assertEqual(fingerprint(Action("t", {"a": 1, "b": 2})), fingerprint(Action("t", {"b": 2, "a": 1})))

    def test_backoff_bounded_and_deterministic(self):
        r1, r2 = random.Random(1), random.Random(1)
        d1 = [backoff_delay(i, 1.0, 8.0, r1) for i in range(8)]
        d2 = [backoff_delay(i, 1.0, 8.0, r2) for i in range(8)]
        self.assertEqual(d1, d2)
        for i, d in enumerate(d1):
            self.assertLessEqual(d, min(8.0, 2 ** i))
            self.assertGreaterEqual(d, 0)

    def test_detect_loop_exact_and_cycle_and_none(self):
        b = Budget()
        self.assertIsNotNone(detect_loop(["a", "a", "a"], b))
        self.assertIsNone(detect_loop(["a", "a", "b"], b))
        self.assertIn("okresu 2", detect_loop(["x", "a", "b", "a", "b", "a", "b"], b))
        self.assertIn("okresu 3", detect_loop(["a", "b", "c"] * 3, b))
        self.assertIsNone(detect_loop(["a", "b", "a", "b", "a", "c"], b))   # cykl przerwany

    def test_no_progress_skips_successes(self):
        b = Budget(no_progress=3)
        self.assertIsNotNone(detect_no_progress(["E", None, "E", None, "E"], b))
        self.assertIsNone(detect_no_progress(["E", None, "F", None, "E"], b))


class TestLoopDetection(Base):
    def test_happy_path(self):
        r = self.sup().run(W.policy_happy)
        self.assertEqual((r.status, len(r.steps)), ("DONE", 3))
        self.assertFalse(r.steps[0].ok)                     # pierwszy test pada - to obserwacja
        self.assertIn("CS0103", r.steps[0].out)
        self.assertTrue(r.steps[2].ok)

    def test_exact_repeat_stops_at_third(self):
        r = self.sup().run(W.policy_same_action)
        self.assertEqual((r.status, len(r.steps)), ("LOOP", 3))
        self.assertEqual(self.w.test_runs, 3)

    def test_ping_pong_stops_after_three_cycles(self):
        r = self.sup().run(W.policy_ping_pong)
        self.assertEqual(r.status, "LOOP")
        self.assertIn("okresu 2", r.reason)
        self.assertEqual(len(r.steps), 6)

    def test_varied_actions_caught_by_no_progress(self):
        r = self.sup().run(W.policy_varied_but_stuck)
        self.assertEqual(r.status, "NO_PROGRESS")
        self.assertEqual(len(r.steps), 8)
        # kontrola: detektor odciskow NIE zlapal tej petli (kazda edycja inna)
        self.assertEqual(len({fingerprint(s.action) for s in r.steps if s.action.tool == "edit_file"}), 4)


class TestBudget(Base):
    def test_step_budget(self):
        r = self.sup(Budget(max_steps=5)).run(W.policy_never_ends)
        self.assertEqual((r.status, len(r.steps)), ("BUDGET_STEPS", 5))

    def test_cost_budget(self):
        r = self.sup(Budget(max_cost=40)).run(W.policy_never_ends)
        self.assertEqual(r.status, "BUDGET_COST")
        self.assertGreaterEqual(r.cost, 40)
        self.assertLess(len(r.steps), 20)

    def test_wall_budget_consumed_by_backoff(self):
        w = W.World(fetch_failures=100)
        clock = VirtualClock()
        pol = lambda steps: Action("fetch", {"n": len(steps)})
        r = Supervisor(w.tools(), Budget(max_wall=10, backoff_base=4, backoff_cap=30, max_steps=50),
                       Journal(self.jpath), clock=clock, seed=3).run(pol)
        self.assertEqual(r.status, "BUDGET_WALL")
        self.assertGreaterEqual(clock.now, 10)


class TestRetry(Base):
    def test_transient_then_success(self):
        w = W.World(fetch_failures=2)
        clock = VirtualClock()
        r = self.sup(world=w, clock=clock).run(W.policy_fetch_once)
        self.assertEqual(r.status, "DONE")
        self.assertEqual((r.steps[0].ok, r.steps[0].attempts, w.fetch_calls), (True, 3, 3))
        self.assertEqual(len(clock.sleeps), 2)

    def test_gives_up_after_max_attempts(self):
        w = W.World(fetch_failures=99)
        r = self.sup(world=w).run(W.policy_fetch_once)
        self.assertFalse(r.steps[0].ok)
        self.assertEqual((r.steps[0].attempts, w.fetch_calls), (4, 4))
        self.assertIn("TransientError", r.steps[0].out)

    def test_non_transient_not_retried(self):
        r = self.sup().run(lambda s: Action("run_tests", {}) if not s else Done())
        self.assertEqual((r.steps[0].attempts, self.w.test_runs), (1, 1))

    def test_unknown_tool_is_observation_not_crash(self):
        r = self.sup().run(lambda s: Action("rm_rf", {}) if not s else Done())
        self.assertFalse(r.steps[0].ok)
        self.assertIn("unknown tool", r.steps[0].out)


def crash_at(point, step):
    fired = []

    def hook(p, s):
        if p == point and s == step and not fired:
            fired.append(1)
            raise SimulatedCrash()
    return hook


class TestResume(Base):
    def test_crash_after_effect_with_key_dedups(self):
        with self.assertRaises(SimulatedCrash):
            self.sup(crash_hook=crash_at("after_effect", 2)).run(W.policy_notify_then_finish)
        self.assertEqual(self.w.notify_calls, 2)             # krok 2 wykonany, wyniku brak w dzienniku
        r = self.sup().run(W.policy_notify_then_finish)      # nowy proces, ten sam dziennik
        self.assertEqual((r.status, r.resumed_from, len(r.steps)), ("DONE", 1, 2))
        self.assertEqual(self.w.notify_calls, 3)             # powtorzone WYWOLANIE...
        self.assertEqual(len(self.w.outbox), 2)              # ...ale EFEKT raz
        self.assertIn("dedup", r.steps[1].out)

    def test_control_restart_without_journal_duplicates(self):
        with self.assertRaises(SimulatedCrash):
            self.sup(crash_hook=crash_at("after_effect", 2)).run(W.policy_notify_then_finish)
        os.remove(self.jpath)                                 # "restart od zera"
        self.sup(run_id="inny").run(W.policy_notify_then_finish)
        self.assertEqual(len(self.w.outbox), 4)               # duplikaty: start i koniec dwa razy

    def test_crash_after_intent_executes_once(self):
        with self.assertRaises(SimulatedCrash):
            self.sup(crash_hook=crash_at("after_intent", 1)).run(W.policy_notify_then_finish)
        self.assertEqual(self.w.notify_calls, 0)
        r = self.sup().run(W.policy_notify_then_finish)
        self.assertEqual((r.status, self.w.notify_calls, len(self.w.outbox)), ("DONE", 2, 2))

    def test_unsafe_tool_needs_human_and_no_double_charge(self):
        with self.assertRaises(SimulatedCrash):
            self.sup(crash_hook=crash_at("after_effect", 2)).run(W.policy_charge_twice)
        self.assertEqual(self.w.charges, [100])
        r = self.sup().run(W.policy_charge_twice)
        self.assertEqual(r.status, "NEEDS_HUMAN")
        self.assertEqual(self.w.charges, [100])               # nie obciazono drugi raz

    def test_unsafe_tool_crash_after_intent_also_needs_human(self):
        with self.assertRaises(SimulatedCrash):
            self.sup(crash_hook=crash_at("after_intent", 2)).run(W.policy_charge_twice)
        self.assertEqual(self.w.charges, [])                  # tu nic sie nie wykonalo...
        r = self.sup().run(W.policy_charge_twice)
        self.assertEqual(r.status, "NEEDS_HUMAN")             # ...ale dziennik tego nie odroznia
        self.assertEqual(self.w.charges, [])

    def test_read_only_pending_is_reexecuted(self):
        w = W.World()
        with self.assertRaises(SimulatedCrash):
            self.sup(world=w, crash_hook=crash_at("after_effect", 1)).run(W.policy_fetch_once)
        r = self.sup(world=w).run(W.policy_fetch_once)
        self.assertEqual((r.status, w.fetch_calls), ("DONE", 2))

    def test_torn_journal_tail_ignored(self):
        self.sup().run(W.policy_happy)
        with open(self.jpath, "a", encoding="utf-8") as f:
            f.write('{"t": "intent", "step": 4, "to')       # urwany zapis
        self.assertEqual(Journal(self.jpath).read()[-1]["t"], "end")

    def test_budget_accumulates_across_resume(self):
        with self.assertRaises(SimulatedCrash):
            self.sup(crash_hook=crash_at("after_effect", 3)).run(W.policy_never_ends)
        r = self.sup(Budget(max_steps=4)).run(W.policy_never_ends)
        self.assertEqual((r.status, len(r.steps), r.resumed_from), ("BUDGET_STEPS", 4, 2))
        # resumed_from = kroki z kompletnym wynikiem w dzienniku (2); krok 3 byl 'pending' i wykonano go ponownie

    def test_resumed_history_equals_uninterrupted(self):
        with self.assertRaises(SimulatedCrash):
            self.sup(crash_hook=crash_at("after_effect", 2)).run(W.policy_happy)
        r1 = self.sup().run(W.policy_happy)
        w2 = W.World()
        p2 = os.path.join(self.dir, "j2.jsonl")
        r2 = Supervisor(w2.tools(), Budget(), Journal(p2)).run(W.policy_happy)
        self.assertEqual([(s.action, s.ok) for s in r1.steps], [(s.action, s.ok) for s in r2.steps])
        self.assertEqual(r1.status, r2.status)


if __name__ == "__main__":
    unittest.main(verbosity=2)
