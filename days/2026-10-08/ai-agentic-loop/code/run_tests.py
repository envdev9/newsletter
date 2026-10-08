"""Testy nadzorcy v2. Uruchom: python3 -B run_tests.py  (bez zaleznosci, stdlib unittest)."""
from __future__ import annotations

import os
import shutil
import tempfile
import unittest

import world as W
from agentloop import (Action, Budget, Done, Journal, JournalCorrupt, ResolveError, SimulatedCrash,
                       Supervisor, VirtualClock, fold, resolve)


def crash_at(point, step):
    fired = []

    def hook(p, s):
        if p == point and s == step and not fired:
            fired.append(1)
            raise SimulatedCrash()
    return hook


class Base(unittest.TestCase):
    def setUp(self):
        self.dir = tempfile.mkdtemp(prefix="prasowka-loop2-")
        self.jpath = os.path.join(self.dir, "journal.jsonl")
        self.w = W.World()
        W.policy_nondeterministic_after_done.asked = 0

    def tearDown(self):
        shutil.rmtree(self.dir, ignore_errors=True)

    def sup(self, budget=None, world=None, repair=True, **kw):
        w = world or self.w
        return Supervisor(w.tools(), budget or Budget(), Journal(self.jpath, repair=repair), **kw)

    def raw(self):
        with open(self.jpath, "rb") as f:
            return f.read()

    def recs(self, repair=True):
        return Journal(self.jpath, repair=repair).read()


class TestRegression14(Base):
    """Zachowania z #14, ktore musza przetrwac refaktor."""

    def test_happy_path(self):
        r = self.sup().run(W.policy_happy)
        self.assertEqual((r.status, len(r.steps), r.replayed), ("DONE", 3, False))

    def test_exact_loop(self):
        r = self.sup().run(lambda s: Action("run_tests", {}))
        self.assertEqual((r.status, len(r.steps)), ("LOOP", 3))

    def test_crash_after_effect_dedups(self):
        with self.assertRaises(SimulatedCrash):
            self.sup(crash_hook=crash_at("after_effect", 2)).run(W.policy_notify_then_finish)
        r = self.sup().run(W.policy_notify_then_finish)
        self.assertEqual((r.status, self.w.notify_calls, len(self.w.outbox)), ("DONE", 3, 2))

    def test_unsafe_tool_needs_human(self):
        with self.assertRaises(SimulatedCrash):
            self.sup(crash_hook=crash_at("after_effect", 2)).run(W.policy_charge_twice)
        self.assertEqual(self.sup().run(W.policy_charge_twice).status, "NEEDS_HUMAN")
        self.assertEqual(self.w.charges, [100])

    def test_read_only_pending_is_reexecuted(self):
        with self.assertRaises(SimulatedCrash):
            self.sup(crash_hook=crash_at("after_effect", 1)).run(lambda s: Action("fetch", {}) if not s else Done())
        r = self.sup().run(lambda s: Action("fetch", {}) if not s else Done())
        self.assertEqual((r.status, self.w.fetch_calls), ("DONE", 2))


class TestTornTail(Base):
    TORN = b'{"t": "intent", "step": 2, "to'

    def make_torn(self):
        with open(self.jpath, "wb") as f:
            f.write(b'{"t": "intent", "step": 1, "tool": "notify", "args": {"msg": "start"}, "key": "k1", "vt": 0.0}\n')
            f.write(b'{"t": "result", "step": 1, "ok": true, "out": "sent", "attempts": 1, "vt": 0.0}\n')
            f.write(self.TORN)

    def test_legacy_mode_loses_records_after_torn_tail(self):
        self.make_torn()
        r = self.sup(repair=False).run(W.policy_notify_then_finish)
        self.assertEqual(r.status, "DONE")                       # bieg "dziala"...
        legacy = self.recs(repair=False)
        self.assertEqual(len(legacy), 2)                         # ...ale po restarcie widac tylko 2 rekordy
        self.assertNotIn("end", [x["t"] for x in legacy])        # w tym brak zamkniecia biegu

    def test_repair_truncates_and_keeps_everything(self):
        self.make_torn()
        j = Journal(self.jpath)
        r = Supervisor(self.w.tools(), Budget(), j).run(W.policy_notify_then_finish)
        self.assertEqual(r.status, "DONE")
        self.assertEqual(j.repaired_bytes, len(self.TORN))
        kinds = [x["t"] for x in self.recs()]
        self.assertEqual(kinds, ["intent", "result", "intent", "result", "end"])
        self.assertTrue(self.raw().endswith(b"\n"))

    def test_valid_json_without_newline_is_kept(self):
        with open(self.jpath, "wb") as f:
            f.write(b'{"t": "intent", "step": 1, "tool": "fetch", "args": {}, "key": "k", "vt": 0.0}\n')
            f.write(b'{"t": "result", "step": 1, "ok": true, "out": "payload", "attempts": 1, "vt": 0.0}')
        j = Journal(self.jpath)
        j.append({"t": "end", "status": "DONE", "reason": "x", "vt": 0.0})
        self.assertEqual(j.repaired_bytes, 0)
        self.assertEqual([x["t"] for x in self.recs()], ["intent", "result", "end"])

    def test_corruption_in_the_middle_is_not_repaired(self):
        with open(self.jpath, "wb") as f:
            f.write(b'{"t": "intent", "step": 1, "tool": "fetch", "args": {}, "key": "k"}\n')
            f.write(b'NIE-JSON\n')
            f.write(b'{"t": "end", "status": "DONE", "reason": ""}\n')
        before = self.raw()
        with self.assertRaises(JournalCorrupt):
            Journal(self.jpath).read()
        self.assertEqual(self.raw(), before)                      # nic nie zmieniono

    def test_clean_journal_is_not_touched(self):
        self.sup().run(W.policy_happy)
        j = Journal(self.jpath)
        before = self.raw()
        j.append({"t": "end", "status": "DONE", "reason": "ok", "vt": 0.0})
        self.assertEqual(j.repaired_bytes, 0)
        self.assertTrue(self.raw().startswith(before))


class TestClosedRun(Base):
    def test_done_run_is_replayed_without_work(self):
        r1 = self.sup().run(W.policy_happy)
        before = self.raw()
        r2 = self.sup().run(W.policy_tripwire)                    # gdyby policy zostala wolana -> AssertionError
        self.assertTrue(r2.replayed)
        self.assertEqual((r2.status, r2.reason, len(r2.steps)), (r1.status, r1.reason, 3))
        self.assertEqual(self.raw(), before)                      # ani jednego nowego bajtu

    def test_nondeterministic_model_cannot_extend_closed_run(self):
        self.sup().run(W.policy_nondeterministic_after_done)
        calls = self.w.notify_calls
        r = self.sup().run(W.policy_nondeterministic_after_done)
        self.assertEqual((r.status, r.replayed, self.w.notify_calls), ("DONE", True, calls))

    def test_control_without_end_record_model_gets_asked_again(self):
        self.sup().run(W.policy_nondeterministic_after_done)
        calls = self.w.notify_calls
        lines = self.raw().splitlines(keepends=True)
        with open(self.jpath, "wb") as f:                          # symulacja #14: brak rekordu 'end'
            f.write(b"".join(lines[:-1]))
        self.sup().run(W.policy_nondeterministic_after_done)
        self.assertEqual(self.w.notify_calls, calls + 1)           # pojawila sie dodatkowa wysylka

    def test_loop_is_final_too(self):
        r1 = self.sup().run(lambda s: Action("run_tests", {}))
        tests = self.w.test_runs
        r2 = self.sup().run(lambda s: Action("run_tests", {}))
        self.assertEqual((r1.status, r2.status, r2.replayed, self.w.test_runs), ("LOOP", "LOOP", True, tests))

    def test_budget_end_is_resumable_and_not_duplicated(self):
        r1 = self.sup(Budget(max_steps=2)).run(W.policy_never_ends)
        self.assertEqual((r1.status, len(r1.steps)), ("BUDGET_STEPS", 2))
        self.sup(Budget(max_steps=2)).run(W.policy_never_ends)     # ten sam budzet: nic nowego
        self.assertEqual([x["t"] for x in self.recs()].count("end"), 1)
        r3 = self.sup(Budget(max_steps=4)).run(W.policy_never_ends)
        self.assertEqual((r3.status, len(r3.steps), r3.resumed_from, r3.replayed), ("BUDGET_STEPS", 4, 2, False))
        self.assertEqual([x["t"] for x in self.recs()].count("end"), 2)
        st = fold(self.recs())
        self.assertEqual(st.last_end["reason"], "limit 4 krokow")


class TestClock(Base):
    def stuck(self, max_wall, restore=True, clock=None):
        w = W.World(fetch_failures=10_000)
        b = Budget(max_wall=max_wall, backoff_base=4, backoff_cap=30, max_steps=500)
        clock = clock or VirtualClock()
        r = Supervisor(w.tools(), b, Journal(self.jpath), clock=clock, seed=3, restore_clock=restore).run(
            W.policy_fetch_forever)
        return r, clock

    def test_vt_is_written_and_monotonic(self):
        self.stuck(10)
        vts = [x["vt"] for x in self.recs()]
        self.assertEqual(vts, sorted(vts))
        self.assertGreaterEqual(vts[-1], 10)

    def test_wall_time_accumulates_across_resume(self):
        r1, c1 = self.stuck(10)
        self.assertEqual(r1.status, "BUDGET_WALL")
        r2, c2 = self.stuck(20)
        self.assertEqual(r2.status, "BUDGET_WALL")
        self.assertGreaterEqual(c2.now, 20)
        self.assertGreaterEqual(r2.vt, r1.vt)
        self.assertEqual(c2.sleeps and len(c2.sleeps) > 0, True)

    def test_control_without_restore_spends_the_whole_budget_again(self):
        _, c1 = self.stuck(10)
        self.assertGreaterEqual(c1.now, 10)
        shutil.copy(self.jpath, self.jpath + ".bak")
        _, c2 = self.stuck(20, restore=True)
        shutil.copy(self.jpath + ".bak", self.jpath)       # ten sam stan dziennika dla kontroli
        _, c3 = self.stuck(20, restore=False)
        self.assertGreater(sum(c3.sleeps), sum(c2.sleeps))
        self.assertGreater(sum(c3.sleeps), 20 - 1e-9)      # bez przywrocenia: caly budzet od zera


class TestResolve(Base):
    def crash_charge(self, point):
        with self.assertRaises(SimulatedCrash):
            self.sup(crash_hook=crash_at(point, 2)).run(W.policy_charge_twice)

    def test_needs_human_is_final_and_idempotent(self):
        self.crash_charge("after_effect")
        r1 = self.sup().run(W.policy_charge_twice)
        before = self.raw()
        r2 = self.sup().run(W.policy_charge_twice)
        self.assertEqual((r1.status, r2.status, r2.replayed), ("NEEDS_HUMAN", "NEEDS_HUMAN", True))
        self.assertEqual(self.raw(), before)

    def test_human_says_executed(self):
        self.crash_charge("after_effect")
        self.sup().run(W.policy_charge_twice)
        resolve(Journal(self.jpath), 2, "executed", out="charged 100 (potwierdzone w panelu platnosci)")
        r = self.sup().run(W.policy_charge_twice)
        self.assertEqual(r.status, "DONE")
        self.assertEqual(self.w.charges, [100])                    # nie obciazono drugi raz
        self.assertEqual((r.steps[1].out, r.steps[1].attempts), ("charged 100 (potwierdzone w panelu platnosci)", 0))

    def test_human_says_not_executed(self):
        self.crash_charge("after_intent")
        self.assertEqual(self.w.charges, [])
        self.assertEqual(self.sup().run(W.policy_charge_twice).status, "NEEDS_HUMAN")
        resolve(Journal(self.jpath), 2, "not_executed")
        r = self.sup().run(W.policy_charge_twice)
        self.assertEqual((r.status, self.w.charges), ("DONE", [100]))

    def test_resolve_validation(self):
        self.crash_charge("after_effect")
        j = Journal(self.jpath)
        with self.assertRaises(ResolveError):
            resolve(j, 1, "executed", out="x")                     # krok 1 ma wynik, nie wisi
        with self.assertRaises(ResolveError):
            resolve(j, 2, "executed")                              # brak obserwacji
        with self.assertRaises(ResolveError):
            resolve(j, 2, "nie-wiem")
        self.assertEqual([x["t"] for x in self.recs()].count("resolve"), 0)

    def test_resolve_survives_second_resume(self):
        self.crash_charge("after_effect")
        self.sup().run(W.policy_charge_twice)
        resolve(Journal(self.jpath), 2, "executed", out="ok-human")
        self.sup().run(W.policy_charge_twice)
        r = self.sup().run(W.policy_tripwire)
        self.assertEqual((r.status, r.replayed, len(r.steps)), ("DONE", True, 2))


class TestOriginalResultOnDedup(Base):
    def test_resumed_observations_equal_uninterrupted(self):
        with self.assertRaises(SimulatedCrash):
            self.sup(crash_hook=crash_at("after_effect", 2)).run(W.policy_notify_then_finish)
        r1 = self.sup().run(W.policy_notify_then_finish)
        w2 = W.World()
        p2 = os.path.join(self.dir, "j2.jsonl")
        r2 = Supervisor(w2.tools(), Budget(), Journal(p2)).run(W.policy_notify_then_finish)
        self.assertEqual([(s.action, s.ok, s.out) for s in r1.steps], [(s.action, s.ok, s.out) for s in r2.steps])
        self.assertEqual((self.w.notify_calls, len(self.w.outbox)), (3, 2))


if __name__ == "__main__":
    unittest.main(verbosity=2)
