"""Testy #19 - PRAWDZIWE procesy (subprocess), powtarzane. python3 -B run_tests.py"""
from __future__ import annotations

import errno
import fcntl
import glob
import os
import random
import signal
import subprocess
import sys
import tempfile
import time
import unittest

from harness import (HERE, contend, dead_pid, effects, finish, journal_stats, kill_and_takeover, spawn,
                     two_writers, workdir)
from joblock import ExclLock, FlockLock, LockBusy, pid_alive, proc_start_ticks, read_meta

STEPS = 12


class TestFlockLockUnit(unittest.TestCase):
    def test_second_acquire_busy_then_free_after_release(self):
        with workdir() as d:
            p = os.path.join(d, "a.lock")
            a = FlockLock(p).acquire()
            with self.assertRaises(LockBusy) as cm:
                FlockLock(p, timeout=0.05).acquire()
            self.assertEqual(cm.exception.holder["pid"], os.getpid())
            a.release()
            FlockLock(p).acquire().release()

    def test_waits_for_release_within_timeout(self):
        with workdir() as d:
            p = os.path.join(d, "a.lock")
            holder = subprocess.Popen([sys.executable, "-B", "-c",
                                       f"import sys,time;sys.path.insert(0,{HERE!r});"
                                       f"from joblock import FlockLock;"
                                       f"l=FlockLock({p!r}).acquire();print('ok',flush=True);time.sleep(0.3)"],
                                      stdout=subprocess.PIPE, text=True)
            holder.stdout.readline()
            lk = FlockLock(p, timeout=5).acquire()
            self.assertGreaterEqual(lk.waited, 0.1)
            lk.release()
            holder.wait(); holder.stdout.close()


class TestPid(unittest.TestCase):
    def test_start_ticks_and_reuse(self):
        me = os.getpid()
        t = proc_start_ticks(me)
        self.assertTrue(pid_alive(me))
        self.assertTrue(pid_alive(me, t))
        self.assertFalse(pid_alive(me, t + 1), "ten sam PID z innym czasem startu = inny proces")

    def test_dead_and_zombie(self):
        self.assertFalse(pid_alive(dead_pid()))
        p = subprocess.Popen([sys.executable, "-c", "pass"])
        time.sleep(0.3)
        self.assertTrue(os.path.exists(f"/proc/{p.pid}"))
        self.assertFalse(pid_alive(p.pid), "zombie liczy sie jako martwy")
        p.wait()


class TestWriters(unittest.TestCase):
    def test_no_lock_duplicates_effects_every_time(self):
        for _ in range(3):
            with workdir() as d:
                two_writers(d, "none", STEPS, "plain")
                self.assertEqual(len(effects(d)), 2 * STEPS)
                s = journal_stats(d)
                self.assertEqual(s["intents"], 2 * STEPS)
                self.assertEqual(s["fold_total"], STEPS, "dziennik 'zapomina' drugiego pisarza")

    def test_no_lock_keyed_still_duplicates_sometimes(self):
        total = 0
        for _ in range(6):
            with workdir() as d:
                two_writers(d, "none", STEPS, "keyed")
                total += len(effects(d))
        self.assertGreater(total, 6 * STEPS, "check-then-write bez blokady nie jest atomowe")

    def test_flock_blocking_exactly_once(self):
        for _ in range(6):
            with workdir() as d:
                rs = two_writers(d, "flock", STEPS, "plain")
                self.assertEqual(len(effects(d)), STEPS)
                self.assertEqual(sorted(r["replayed"] for r in rs), [False, True])
                self.assertTrue(all(r["status"] == "DONE" for r in rs))

    def test_flock_nonblocking_loser_gets_75(self):
        for _ in range(4):
            with workdir() as d:
                rs = two_writers(d, "flock-nb", STEPS, "plain")
                self.assertEqual(sorted(r["rc"] for r in rs), [0, 75])
                loser = next(r for r in rs if r["rc"] == 75)
                self.assertTrue(loser["busy"])
                self.assertEqual(len(effects(d)), STEPS)


class TestKill(unittest.TestCase):
    def test_flock_released_by_kernel_and_keyed_resume_exactly_once(self):
        rnd = random.Random(1)
        pend = 0
        for _ in range(10):
            with workdir() as d:
                r = kill_and_takeover(d, rnd.randint(2, STEPS - 2), "flock", "keyed", STEPS)
                self.assertEqual(r["status"], "DONE")
                self.assertEqual((r["effects"], r["unique_keys"]), (STEPS, STEPS))
                pend += r["pending_at_kill"]
        self.assertGreaterEqual(pend, 0)

    def test_plain_tool_never_double_executes(self):
        rnd = random.Random(2)
        seen = set()
        for _ in range(10):
            with workdir() as d:
                r = kill_and_takeover(d, rnd.randint(2, STEPS - 2), "flock", "plain", STEPS)
                seen.add(r["status"])
                self.assertEqual(r["effects"], r["unique_keys"], "nigdy dwa razy ten sam krok")
                self.assertLessEqual(r["effects"], STEPS)
                if r["status"] == "NEEDS_HUMAN":
                    self.assertTrue(r["pending_at_kill"])
        self.assertTrue(seen <= {"DONE", "NEEDS_HUMAN"})

    def test_dead_excl_lock_blocks_unless_stale_check(self):
        with workdir() as d:
            a = spawn("worker.py", "--dir", d, "--mode", "excl", "--steps", "12", "--delay", "0.004")
            t0 = time.time()
            while len(effects(d)) < 3 and time.time() - t0 < 10:
                time.sleep(0.001)
            os.kill(a.pid, signal.SIGKILL); a.wait(); a.stdout.close(); a.stderr.close()
            meta = read_meta(os.path.join(d, "journal.jsonl.lock"))
            self.assertFalse(pid_alive(meta["pid"]))
            b = finish(spawn("worker.py", "--dir", d, "--mode", "excl", "--steps", "12", "--lock-timeout", "0.5"))
            self.assertEqual(b["rc"], 75)
            c = finish(spawn("worker.py", "--dir", d, "--mode", "excl-stale", "--steps", "12", "--lock-timeout", "5"))
            self.assertEqual(c["status"], "DONE")
            self.assertEqual(len(effects(d)), STEPS)


class TestRaces(unittest.TestCase):
    def test_flock_takeover_never_overlaps(self):
        for _ in range(25):
            with workdir() as d:
                r = contend(d, "flock", stale_pid=dead_pid())
                self.assertEqual((r["acquired"], r["overlap"], r["counter"]), (2, False, 2))

    def test_excl_stale_takeover_race_is_real(self):
        hits = 0
        for _ in range(40):
            with workdir() as d:
                r = contend(d, "excl-stale", takeover_delay=0.01, n=3, stale_pid=dead_pid())
                hits += r["overlap"]
        self.assertGreaterEqual(hits, 1, "wyscig przejecia martwego zamka powinien sie ujawnic")

    def test_lock_on_journal_inode_breaks_after_replace(self):
        with workdir() as d:
            j = os.path.join(d, "journal.jsonl")
            open(j, "w").close()
            fd1 = os.open(j, os.O_RDWR)
            fcntl.flock(fd1, fcntl.LOCK_EX | fcntl.LOCK_NB)
            open(j + ".tmp", "w").close()
            os.replace(j + ".tmp", j)
            fd2 = os.open(j, os.O_RDWR)
            fcntl.flock(fd2, fcntl.LOCK_EX | fcntl.LOCK_NB)      # nie rzuca: dwoch wlascicieli
            os.close(fd1); os.close(fd2)

    def test_separate_lock_file_survives_replace(self):
        with workdir() as d:
            j = os.path.join(d, "journal.jsonl")
            a = FlockLock(j + ".lock").acquire()
            open(j + ".tmp", "w").close()
            os.replace(j + ".tmp", j)
            with self.assertRaises(LockBusy):
                FlockLock(j + ".lock").acquire()
            a.release()

    def test_unlink_on_release_creates_two_owners(self):
        with workdir() as d:
            lp = os.path.join(d, "x.lock")
            fa = os.open(lp, os.O_RDWR | os.O_CREAT); fcntl.flock(fa, fcntl.LOCK_EX)
            fb = os.open(lp, os.O_RDWR)
            os.unlink(lp); os.close(fa)
            fcntl.flock(fb, fcntl.LOCK_EX | fcntl.LOCK_NB)
            fc = os.open(lp, os.O_RDWR | os.O_CREAT)
            fcntl.flock(fc, fcntl.LOCK_EX | fcntl.LOCK_NB)       # nie rzuca
            os.close(fb); os.close(fc)


class TestInheritance(unittest.TestCase):
    def _run(self, how: str) -> bool:
        """True gdy zamek jest wolny po zabiciu wlasciciela, ktorego dziecko zyje."""
        with workdir() as d:
            lp = os.path.join(d, "j.lock")
            code = ("import os,sys,time,subprocess\n"
                    f"sys.path.insert(0,{HERE!r})\n"
                    "from joblock import FlockLock\n"
                    f"l=FlockLock({lp!r}).acquire()\n"
                    f"how={how!r}\n"
                    "if how=='fork':\n"
                    "    pid=os.fork()\n"
                    "    if pid==0:\n"
                    "        time.sleep(60); os._exit(0)\n"
                    "else:\n"
                    "    pid=subprocess.Popen(['sleep','60']).pid\n"
                    "print(pid,flush=True)\n"
                    "time.sleep(60)\n")
            p = subprocess.Popen([sys.executable, "-B", "-c", code], stdout=subprocess.PIPE, text=True)
            child = int(p.stdout.readline())
            try:
                os.kill(p.pid, signal.SIGKILL); p.wait(); p.stdout.close()
                try:
                    FlockLock(lp).acquire().release()
                    return True
                except LockBusy:
                    return False
            finally:
                os.kill(child, signal.SIGKILL)

    def test_fork_child_keeps_lock_popen_does_not(self):
        self.assertFalse(self._run("fork"))
        self.assertTrue(self._run("popen"))


class TestCompaction(unittest.TestCase):
    def test_shared_tmp_file_crashes_unlocked_writers(self):
        crashed = 0
        for _ in range(8):
            with workdir() as d:
                rs = two_writers(d, "none", 20, "keyed", compact_every=4)
                crashed += sum(1 for r in rs if r["rc"] not in (0, 75))
        self.assertGreaterEqual(crashed, 1)

    def test_locked_writers_with_compaction_exact(self):
        for _ in range(6):
            with workdir() as d:
                rs = two_writers(d, "flock", 20, "keyed", compact_every=4)
                self.assertTrue(all(r["rc"] == 0 for r in rs))
                self.assertEqual(len(effects(d)), 20)
                self.assertEqual(journal_stats(d)["fold_total"], 20)


class TestZCleanup(unittest.TestCase):
    def test_no_leftover_workdirs(self):
        self.assertEqual(glob.glob(os.path.join(tempfile.gettempdir(), "prasowka-lock-*")), [])


if __name__ == "__main__":
    unittest.main(verbosity=2)
