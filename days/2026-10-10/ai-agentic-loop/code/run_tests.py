"""Testy nadzorcy v3. Uruchom: python3 -B run_tests.py  (bez zaleznosci, stdlib unittest)."""
from __future__ import annotations

import json
import os
import shutil
import tempfile
import unittest

import world as W
from agentloop import (WINDOW, Action, Budget, Done, Journal, JournalCorrupt, SimulatedCrash, Supervisor,
                       Tool, compact, detect_tree_stall, fold, resolve, tree_hash)


def crash_at(point, step):
    fired = []

    def hook(p, s):
        if p == point and s == step and not fired:
            fired.append(1)
            raise SimulatedCrash()
    return hook


class Base(unittest.TestCase):
    def setUp(self):
        self.dir = tempfile.mkdtemp(prefix="prasowka-loop3-")
        self.jpath = os.path.join(self.dir, "journal.jsonl")
        self.w = W.World(os.path.join(self.dir, "repo"))

    def tearDown(self):
        shutil.rmtree(self.dir, ignore_errors=True)

    def sup(self, budget=None, tree=True, world=None, **kw):
        w = world or self.w
        obs = (lambda: tree_hash(w.root)) if tree else None
        return Supervisor(w.tools(), budget or Budget(), Journal(self.jpath), observer=obs, **kw)

    def recs(self):
        return Journal(self.jpath).read()

    def kinds(self):
        return [r["t"] for r in self.recs()]


class TestTreeHash(Base):
    def test_ignores_build_artifacts(self):
        h = tree_hash(self.w.root)
        self.w.write("obj/Debug/a.dll", "x")
        self.w.write("bin/b.dll", "y")
        self.w.write(".git/HEAD", "ref")
        self.assertEqual(tree_hash(self.w.root), h)

    def test_ignores_mtime(self):
        h = tree_hash(self.w.root)
        os.utime(os.path.join(self.w.root, "Foo.cs"), (12345, 12345))
        self.assertEqual(tree_hash(self.w.root), h)

    def test_content_change_and_revert(self):
        h = tree_hash(self.w.root)
        self.w.write("Foo.cs", W.FOO_BROKEN + " ")
        self.assertNotEqual(tree_hash(self.w.root), h)
        self.w.write("Foo.cs", W.FOO_BROKEN)
        self.assertEqual(tree_hash(self.w.root), h)

    def test_rename_changes_hash(self):
        h = tree_hash(self.w.root)
        os.rename(os.path.join(self.w.root, "notes.txt"), os.path.join(self.w.root, "n2.txt"))
        self.assertNotEqual(tree_hash(self.w.root), h)

    def test_new_untracked_file_counts(self):
        h = tree_hash(self.w.root)
        self.w.write("New.cs", "class N {}")
        self.assertNotEqual(tree_hash(self.w.root), h)

    def test_empty_dir_ignored(self):
        h = tree_hash(self.w.root)
        os.makedirs(os.path.join(self.w.root, "empty"))
        self.assertEqual(tree_hash(self.w.root), h)


class TestTreeStallDetector(Base):
    def test_threshold_unit(self):
        b = Budget(tree_repeat=3)
        self.assertIsNone(detect_tree_stall({"h": 2}, "h", b))
        self.assertIn("TREE_STALL", detect_tree_stall({"h": 3}, "h", b))
        self.assertIsNone(detect_tree_stall({"h": 9}, None, b))   # krok nie byl porazka weryfikacji

    def test_spin_stalls_after_3_failed_verifications(self):
        r = self.sup().run(W.policy_spin_same_tree)
        self.assertEqual((r.status, r.total, self.w.test_runs), ("NO_PROGRESS", 5, 3))
        self.assertTrue(r.reason.startswith("TREE_STALL"))

    def test_text_detectors_are_blind_here(self):
        r = self.sup(tree=False).run(W.policy_spin_same_tree)
        self.assertEqual((r.status, r.total), ("BUDGET_STEPS", 20))

    def test_oscillation_stalls_at_third_return(self):
        r = self.sup().run(W.policy_oscillate)
        self.assertEqual((r.status, r.total, self.w.test_runs), ("NO_PROGRESS", 10, 5))
        self.assertTrue(r.reason.startswith("TREE_STALL"))

    def test_oscillation_blind_without_tree(self):
        r = self.sup(tree=False).run(W.policy_oscillate)
        self.assertEqual(r.status, "BUDGET_STEPS")

    def test_progress_is_not_flagged(self):
        r = self.sup().run(W.policy_progress)
        self.assertEqual((r.status, r.total, self.w.test_runs), ("DONE", 7, 4))

    def test_exploration_without_verification_is_not_flagged(self):
        r = self.sup().run(W.policy_explore_then_fix)
        self.assertEqual((r.status, r.total), ("DONE", 10))

    def test_tree_repeat_is_configurable(self):
        r = self.sup(Budget(tree_repeat=2)).run(W.policy_spin_same_tree)
        self.assertEqual((r.status, r.total), ("NO_PROGRESS", 3))

    def test_failure_of_non_verifying_tool_not_counted(self):
        def boom(a, k):
            raise RuntimeError("zepsute")
        tools = self.w.tools()
        tools["boom"] = Tool("boom", boom)           # verifies=False
        s = Supervisor(tools, Budget(max_steps=8, no_progress=99), Journal(self.jpath),
                       observer=lambda: tree_hash(self.w.root))
        r = s.run(lambda h: Action("boom", {"i": h.total}))
        self.assertEqual(r.status, "BUDGET_STEPS")

    def test_records_th_always_and_tf_only_on_verification_failure(self):
        self.sup().run(W.policy_progress)
        results = [x for x in self.recs() if x["t"] == "result"]
        self.assertTrue(all("th" in x for x in results))
        failed_tests = [x for x in results if "tf" in x]
        self.assertEqual(len(failed_tests), 3)       # 3 padniete run_tests, 4. przeszedl
        self.assertNotIn("tf", results[-1])

    def test_no_observer_no_th(self):
        self.sup(tree=False).run(W.policy_progress)
        self.assertFalse(any("th" in x for x in self.recs()))

    def test_tree_counter_survives_crash_and_restart(self):
        with self.assertRaises(SimulatedCrash):
            self.sup(crash_hook=crash_at("after_intent", 3)).run(W.policy_spin_same_tree)
        r = self.sup().run(W.policy_spin_same_tree)
        self.assertEqual((r.status, r.total, self.w.test_runs), ("NO_PROGRESS", 5, 3))


class TestSnapshots(Base):
    def full_run(self, **kw):
        return self.sup(Budget(max_steps=50), **kw).run(W.policy_long_task)

    def test_compacted_run_equals_full_run(self):
        r_full = self.full_run()
        effects_full = len(self.w.outbox)
        shutil.rmtree(self.dir)
        self.setUp()
        r_c = self.full_run(compact_every=8, compact_keep=3)
        self.assertEqual((r_c.status, r_c.total, r_c.cost, len(self.w.outbox)),
                         (r_full.status, r_full.total, r_full.cost, effects_full))

    def test_journal_shrinks_and_has_snapshot(self):
        self.full_run()
        full = os.path.getsize(self.jpath)
        shutil.rmtree(self.dir)
        self.setUp()
        self.full_run(compact_every=8, compact_keep=3)
        self.assertLess(os.path.getsize(self.jpath), full * 0.3)
        self.assertEqual(self.kinds()[0], "snapshot")
        self.assertLessEqual(len(self.recs()), 6)

    def test_offline_compact_preserves_fold(self):
        self.full_run()
        before = fold(self.recs())
        info = compact(Journal(self.jpath), keep=4)
        after = fold(self.recs())
        self.assertEqual(after.summary, before.summary)
        self.assertEqual(after.last_end, before.last_end)
        self.assertEqual([s.n for s in after.steps], [27, 28, 29, 30])
        self.assertEqual(after.steps, before.steps[-4:])
        self.assertEqual(info["after_recs"], 1)

    def test_compaction_is_idempotent(self):
        self.full_run()
        compact(Journal(self.jpath), keep=3)
        a = fold(self.recs())
        compact(Journal(self.jpath), keep=3)
        self.assertEqual(fold(self.recs()), a)

    def test_pending_intent_survives_snapshot(self):
        with self.assertRaises(SimulatedCrash):
            self.sup(Budget(max_steps=50), crash_hook=crash_at("after_effect", 6)).run(W.policy_long_task)
        self.assertIsNotNone(fold(self.recs()).pending)
        compact(Journal(self.jpath), keep=2)
        self.assertEqual(fold(self.recs()).pending["step"], 6)
        r = self.sup(Budget(max_steps=50)).run(W.policy_long_task)
        self.assertEqual((r.status, r.total, len(self.w.outbox)), ("DONE", 30, 15))

    def test_needs_human_and_resolve_work_after_compaction(self):
        with self.assertRaises(SimulatedCrash):
            self.sup(crash_hook=crash_at("after_effect", 2)).run(W.policy_charge_twice)
        self.assertEqual(self.sup().run(W.policy_charge_twice).status, "NEEDS_HUMAN")
        compact(Journal(self.jpath), keep=1)
        self.assertEqual(fold(self.recs()).last_end["status"], "NEEDS_HUMAN")
        r = self.sup().run(W.policy_charge_twice)
        self.assertEqual((r.status, r.replayed), ("NEEDS_HUMAN", True))
        resolve(Journal(self.jpath), 2, "executed", out="charged 100 (potwierdzone)")
        r = self.sup().run(W.policy_charge_twice)
        self.assertEqual((r.status, self.w.charges), ("DONE", [100]))

    def test_closed_run_replays_from_snapshot_without_policy(self):
        self.full_run(compact_every=8, compact_keep=3)

        def tripwire(h):
            raise AssertionError("policy wolana na zamknietym biegu")
        r = self.sup(Budget(max_steps=50)).run(tripwire)
        self.assertEqual((r.status, r.replayed, r.total), ("DONE", True, 30))

    def test_crash_between_tmp_and_replace(self):
        with self.assertRaises(SimulatedCrash):
            self.full_run(compact_every=8, compact_keep=3, crash_hook=crash_at("compact_tmp_written", 8))
        self.assertTrue(os.path.exists(self.jpath + ".tmp"))
        self.assertNotIn("snapshot", self.kinds())             # stary, KOMPLETNY dziennik
        r = self.full_run(compact_every=8, compact_keep=3)
        self.assertEqual((r.status, r.total, len(self.w.outbox)), ("DONE", 30, 15))

    def test_crash_after_replace(self):
        with self.assertRaises(SimulatedCrash):
            self.full_run(compact_every=8, compact_keep=3, crash_hook=crash_at("compact_replaced", 8))
        self.assertEqual(self.kinds(), ["snapshot"])
        r = self.full_run(compact_every=8, compact_keep=3)
        self.assertEqual((r.status, r.total, r.cost, len(self.w.outbox)), ("DONE", 30, 1900, 15))

    def test_stale_tmp_does_not_leak_into_state(self):
        self.full_run(compact_every=8, compact_keep=3)
        with open(self.jpath + ".tmp", "w") as f:
            f.write("smieci, nie JSON\n")
        self.assertEqual(fold(self.recs()).summary.total, 30)
        compact(Journal(self.jpath), keep=2)                    # nadpisuje .tmp
        self.assertFalse(os.path.exists(self.jpath + ".tmp"))

    def test_loop_detector_state_survives_compaction(self):
        r = self.sup(compact_every=2, compact_keep=1).run(lambda h: Action("read_file", {"path": "Foo.cs"}))
        self.assertEqual((r.status, r.total), ("LOOP", 3))

    def test_tree_counter_survives_compaction(self):
        r = self.sup(compact_every=3, compact_keep=1).run(W.policy_spin_same_tree)
        self.assertEqual((r.status, r.total, self.w.test_runs), ("NO_PROGRESS", 5, 3))
        self.assertEqual(self.kinds()[0], "snapshot")

    def test_summary_window_is_capped(self):
        self.full_run()
        s = fold(self.recs()).summary
        self.assertEqual((len(s.fps), len(s.sigs)), (WINDOW, WINDOW))

    def test_budget_survives_compaction(self):
        r = self.sup(Budget(max_steps=12), compact_every=4, compact_keep=1).run(W.policy_long_task)
        self.assertEqual((r.status, r.total), ("BUDGET_STEPS", 12))

    def test_archive_keeps_audit_trail(self):
        self.full_run(compact_every=10, compact_keep=2, archive=True)
        names = sorted(n for n in os.listdir(self.dir) if ".archive-" in n)
        self.assertEqual(names, ["journal.jsonl.archive-00010", "journal.jsonl.archive-00018",
                                 "journal.jsonl.archive-00026"])
        first = Journal(os.path.join(self.dir, names[0])).read()
        self.assertEqual(len([x for x in first if x["t"] == "intent"]), 10)

    def test_mid_corruption_blocks_compaction_and_leaves_file(self):
        self.full_run()
        with open(self.jpath, "rb") as f:
            lines = f.read().split(b"\n")
        lines[5] = b"{ to nie jest json"
        with open(self.jpath, "wb") as f:
            f.write(b"\n".join(lines))
        with open(self.jpath, "rb") as f:
            before = f.read()
        with self.assertRaises(JournalCorrupt):
            compact(Journal(self.jpath), keep=3)
        with open(self.jpath, "rb") as f:
            self.assertEqual(f.read(), before)

    def test_torn_tail_after_snapshot_is_repaired(self):
        self.full_run(compact_every=8, compact_keep=3)
        with open(self.jpath, "ab") as f:
            f.write(b'{"t": "intent", "step": 31, "to')
        r = self.sup(Budget(max_steps=50)).run(W.policy_long_task)
        self.assertEqual((r.status, r.replayed), ("DONE", True))

    def test_keep_must_be_smaller_than_every(self):
        with self.assertRaises(ValueError):
            self.sup(compact_every=3, compact_keep=3)

    def test_policy_needing_old_history_changes_behavior(self):
        r0 = self.sup().run(W.policy_needs_old_history)
        shutil.rmtree(self.dir)
        self.setUp()
        r1 = self.sup(compact_every=3, compact_keep=1).run(W.policy_needs_old_history)
        self.assertIn("krok: 1", r0.reason)
        self.assertNotIn("krok: 1", r1.reason)


class TestRegression(Base):
    def test_happy_path(self):
        r = self.sup().run(W.policy_progress)
        self.assertEqual((r.status, r.replayed), ("DONE", False))

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

    def test_end_record_not_duplicated_on_replay(self):
        self.sup().run(W.policy_progress)
        n = self.kinds().count("end")
        self.sup().run(W.policy_progress)
        self.assertEqual(self.kinds().count("end"), n)


if __name__ == "__main__":
    unittest.main(verbosity=1)
