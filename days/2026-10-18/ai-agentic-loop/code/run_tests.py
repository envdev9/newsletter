"""Testy #20 (unittest, prawdziwe procesy). Uruchom: python3 -B run_tests.py"""
from __future__ import annotations

import glob
import os
import shutil
import sys
import tempfile
import time
import unittest

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import scen                                                         # noqa: E402
from lease import FencedLog, Heartbeat, LeaseStore, StaleToken      # noqa: E402


class TestLeaseStore(unittest.TestCase):
    def setUp(self) -> None:
        self.tmp = tempfile.mkdtemp(prefix="prasowka-lease-ut-")
        self.store = LeaseStore(os.path.join(self.tmp, "l.json"), ttl=0.2)
        self.addCleanup(shutil.rmtree, self.tmp, True)

    def test_tokens_grow_even_after_release(self):
        toks = []
        for i in range(3):
            lease = self.store.try_acquire(f"o{i}")
            toks.append(lease.token)
            self.store.release(lease.owner, lease.token)
        self.assertEqual(toks, [1, 2, 3])

    def test_second_acquire_denied_while_alive_and_allowed_after_expiry(self):
        self.assertIsNotNone(self.store.try_acquire("A"))
        self.assertIsNone(self.store.try_acquire("B"))
        time.sleep(0.25)
        b = self.store.try_acquire("B")
        self.assertEqual(b.token, 2)

    def test_renew_fails_after_expiry_and_after_takeover(self):
        a = self.store.try_acquire("A")
        self.assertTrue(self.store.renew("A", a.token))
        time.sleep(0.25)
        self.assertFalse(self.store.renew("A", a.token))          # wygasla
        self.store.try_acquire("B")
        self.assertFalse(self.store.renew("A", a.token))          # przejeta
        self.assertFalse(self.store.is_valid("A", a.token))

    def test_release_by_stale_owner_does_not_free_new_lease(self):
        a = self.store.try_acquire("A")
        time.sleep(0.25)
        b = self.store.try_acquire("B")
        self.store.release("A", a.token)
        self.assertTrue(self.store.is_valid("B", b.token))

    def test_heartbeat_keeps_lease_and_reports_loss(self):
        a = self.store.try_acquire("A")
        hb = Heartbeat(self.store, a, interval=0.05).start()
        time.sleep(0.5)                                            # 2.5 x ttl
        self.assertTrue(self.store.is_valid("A", a.token))
        self.assertGreaterEqual(hb.renewals, 5)
        hb.stop()
        time.sleep(0.25)
        b = self.store.try_acquire("B")
        self.assertIsNotNone(b)
        hb2 = Heartbeat(self.store, a, interval=0.01).start()
        self.assertTrue(hb2.lost.wait(1.0))
        hb2.stop()


class TestFencedLog(unittest.TestCase):
    def test_rejects_lower_token_accepts_equal_and_higher(self):
        with scen.workdir() as d:
            log = FencedLog(os.path.join(d, "work.log"))
            log.append(2, "a token=2")
            log.append(2, "b token=2")
            log.append(3, "c token=3")
            with self.assertRaises(StaleToken):
                log.append(2, "late token=2")
            self.assertEqual(len(scen.read_log(d)), 3)


class TestProcesses(unittest.TestCase):
    def test_freeze_unfenced_writes_stale(self):
        r = scen.freeze("unfenced")
        self.assertEqual(r["stale"], 3)
        self.assertEqual(r["log"][:3], ["B token=2 item=0", "B token=2 item=1", "B token=2 item=2"])

    def test_freeze_checked_still_leaks_exactly_the_inflight_write(self):
        r = scen.freeze("checked")
        self.assertEqual(r["stale"], 1)                            # check-then-act: jedna zapisana "w locie"
        self.assertIn("stop:lease-lost-before-1", r["A"]["events"])

    def test_freeze_fenced_blocks_all_stale_writes(self):
        r = scen.freeze("fenced")
        self.assertEqual(r["stale"], 0)
        self.assertTrue(r["A"]["events"][0].startswith("REJECTED:0"))
        self.assertEqual(len(r["log"]), 3)

    def test_frozen_owner_flock_holds_but_lease_expires(self):
        r = scen.flock_vs_lease_freeze(ttl=0.6, flock_timeout=1.0)
        self.assertFalse(r["flock"]["got"])
        self.assertFalse(r["lease"]["busy"])
        self.assertEqual(r["lease"]["token"], 2)
        self.assertLess(r["lease"]["waited"], 1.5)

    def test_heartbeat_protects_long_work_but_no_heartbeat_does_not(self):
        self.assertTrue(scen.long_work(True)["B"]["busy"])
        self.assertFalse(scen.long_work(False)["B"]["busy"])

    def test_takeover_after_kill_takes_about_ttl_for_lease_and_far_less_for_flock(self):
        lease = scen.takeover_after_kill("lease", ttl=0.6)
        fl = scen.takeover_after_kill("flock")
        self.assertGreater(lease, 0.3)
        self.assertLess(lease, 0.7)
        self.assertLess(fl, 0.3)

    def test_race_has_exactly_one_winner(self):
        for _ in range(10):
            r = scen.race(4)
            self.assertEqual(r["winners"], 1)
            self.assertEqual(r["tokens"], [1])


class TestZCleanup(unittest.TestCase):
    def test_no_leftovers(self):
        left = glob.glob("/tmp/prasowka-lease-*")
        self.assertEqual(left, [])


if __name__ == "__main__":
    unittest.main(verbosity=1)
