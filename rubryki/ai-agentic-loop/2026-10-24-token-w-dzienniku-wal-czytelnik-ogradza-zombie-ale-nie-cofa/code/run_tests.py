"""Testy #29. Uruchom: python3 -B run_tests.py (ok. 10 s; testy procesowe zalezne od czasu)."""
import os
import shutil
import tempfile
import unittest

import scen
from wal import Journal, compact, fold


def rec(op, tok, who="X", step=None, id_=None):
    r = {"op": op, "tok": tok, "who": who, "id": id_ or f"{who}{tok}{op}{step}"}
    if step is not None:
        r["step"] = step
    return r


class TestFold(unittest.TestCase):
    def test_stale_dropped_naive_accepts(self):
        recs = [rec("barrier", 1, "A"), rec("step", 1, "A", 0), rec("barrier", 2, "B"),
                rec("step", 2, "B", 1), rec("step", 1, "A", 1), rec("done", 1, "A")]
        f, n = fold(recs), fold(recs, fence=False)
        self.assertEqual(f.steps[1]["who"], "B")
        self.assertEqual(len(f.dropped), 2)
        self.assertIsNone(f.done_by)
        self.assertEqual(n.steps[1]["who"], "A")
        self.assertEqual(n.done_by, "A")

    def test_window_before_barrier_is_accepted(self):
        # zombie pisze po wygasnieciu, ALE przed barierka B: rekord jest widziany przez B w jego stanie
        recs = [rec("barrier", 1, "A"), rec("step", 1, "A", 0), rec("step", 1, "A", 1), rec("barrier", 2, "B")]
        st = fold(recs)
        self.assertEqual(sorted(st.steps), [0, 1])
        self.assertEqual(st.dropped, [])

    def test_b_view_equals_final_for_accepted_prefix(self):
        recs = [rec("barrier", 1, "A"), rec("step", 1, "A", 0), rec("barrier", 2, "B")]
        seen_by_b = fold(recs)
        full = fold(recs + [rec("step", 1, "A", 1), rec("step", 1, "A", 2), rec("step", 2, "B", 1)])
        self.assertEqual(sorted(seen_by_b.steps), [0])
        self.assertEqual(full.steps[1]["who"], "B")
        self.assertNotIn(2, full.steps)

    def test_torn_tail_skipped(self):
        d = tempfile.mkdtemp(prefix="prasowka-fence-")
        try:
            p = os.path.join(d, "j")
            j = Journal(p)
            j.append(rec("barrier", 1, "A"))
            with open(p, "ab") as f:
                f.write(b'{"op":"step","tok":1,"ste')
            recs, bad = j.read()
            self.assertEqual((len(recs), bad), (1, 1))
        finally:
            shutil.rmtree(d, ignore_errors=True)


class TestCompact(unittest.TestCase):
    def setUp(self):
        self.d = tempfile.mkdtemp(prefix="prasowka-fence-")
        self.j = Journal(os.path.join(self.d, "j"))
        for r in [rec("barrier", 1, "A"), rec("step", 1, "A", 0), rec("barrier", 2, "B"), rec("step", 2, "B", 1)]:
            self.j.append(r)

    def tearDown(self):
        shutil.rmtree(self.d, ignore_errors=True)

    def test_snapshot_carries_hw(self):
        compact(self.j)
        self.j.append(rec("step", 1, "A", 1, "zombie"))
        st = fold(self.j.read()[0])
        self.assertEqual((st.steps[1]["who"], st.hw, st.dropped), ("B", 2, ["zombie"]))

    def test_snapshot_without_hw_is_a_bug(self):
        compact(self.j, carry_hw=False)
        self.j.append(rec("step", 1, "A", 1, "zombie"))
        st = fold(self.j.read()[0])
        self.assertEqual(st.steps[1]["who"], "A")          # zombie przeszedl
        self.assertEqual(st.dropped, [])

    def test_fold_after_compact_equals_before(self):
        before = fold(self.j.read()[0]).summary()
        compact(self.j)
        self.assertEqual(fold(self.j.read()[0]).summary()["steps"], before["steps"])
        self.assertEqual(fold(self.j.read()[0]).hw, before["hw"])

    def test_old_fd_write_lost(self):
        fd = os.open(self.j.path, os.O_WRONLY | os.O_APPEND)
        compact(self.j)
        os.write(fd, b'{"op":"step","step":9,"tok":1,"who":"A","id":"late"}\n')
        os.close(fd)
        self.assertEqual(len(self.j.read()[0]), 1)


class TestProcesses(unittest.TestCase):
    def test_blind_duplicates_effects_but_journal_fenced(self):
        r = scen.run("blind", "A pre:2")
        self.assertEqual(r["dup_steps"], [2, 3, 4, 5])           # skutki zewnetrzne: reader-fencing ich nie cofa
        self.assertEqual(r["fenced"]["done_by"], "B")
        self.assertTrue(all(v.startswith("B/") for k, v in r["fenced"]["steps"].items() if k >= 2))
        self.assertEqual(r["naive"]["done_by"], "A")             # naiwny fold: ostatni zapis wygrywa
        self.assertEqual(r["fenced"]["dropped"], 5)

    def test_intent_before_check_window(self):
        r = scen.run("intent", "A pre:2")
        self.assertEqual((r["dup_steps"], r["missing_steps"]), ([], []))
        self.assertEqual(r["fenced"]["dropped"], 1)

    def test_intent_in_window_late_but_once(self):
        r = scen.run("intent", "A checked:2", pause=0.4)
        self.assertEqual((r["dup_steps"], r["missing_steps"]), ([], []))
        self.assertEqual(r["effects"][-1].split()[0], "A")       # skutek kroku 2 przyszedl na koncu, po B
        self.assertEqual(r["effects"][-1].split("step=")[1], "2")

    def test_intent_in_window_kill_loses_effect(self):
        r = scen.run("intent", "A checked:2", pause=0.4, kill=True)
        self.assertEqual(r["missing_steps"], [2])
        self.assertEqual(r["fenced"]["steps"][2], "A/t1")        # dziennik twierdzi, ze krok 2 zrobiony


class TestCleanup(unittest.TestCase):
    def test_zz_no_leftover_dirs(self):
        left = [n for n in os.listdir(tempfile.gettempdir()) if n.startswith("prasowka-fence-")]
        self.assertEqual(left, [])


if __name__ == "__main__":
    unittest.main(verbosity=1)
