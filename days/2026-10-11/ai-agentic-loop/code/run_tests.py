"""Testy #18. Uruchom: python3 -B run_tests.py  (stdlib unittest + binarka git)."""
from __future__ import annotations

import os
import shutil
import subprocess
import tempfile
import unittest

import timeline as TL
import world as W
from agentloop import Budget, Journal, SimulatedCrash, Supervisor, compact, fold, tree_hash
from gittree import GitError, GitTreeObserver


def crash_at(point, step):
    fired = []

    def hook(p, s):
        if p == point and s == step and not fired:
            fired.append(1)
            raise SimulatedCrash()
    return hook


class Base(unittest.TestCase):
    def setUp(self):
        self.dir = tempfile.mkdtemp(prefix="prasowka-loop4-")
        self.jpath = os.path.join(self.dir, "journal.jsonl")
        self.w = W.World(os.path.join(self.dir, "repo"))

    def tearDown(self):
        shutil.rmtree(self.dir, ignore_errors=True)

    def sup(self, budget=None, observer=None, **kw):
        return Supervisor(self.w.tools(), budget or Budget(max_steps=50), Journal(self.jpath),
                          observer=observer, **kw)


class TestGitTree(Base):
    def setUp(self):
        super().setUp()
        self.obs = GitTreeObserver(self.w.root)
        self.addCleanup(self.obs.close)

    def test_deterministic_and_40_hex(self):
        h = self.obs()
        self.assertEqual(len(h), 40)
        self.assertEqual(self.obs(), h)

    def test_matches_real_git_for_same_content(self):
        """Ten sam hash, ktory dostalibysmy z `git add -A && git write-tree` w zwyklym repo."""
        env = dict(os.environ, GIT_CONFIG_GLOBAL=os.devnull, GIT_CONFIG_NOSYSTEM="1")
        other = os.path.join(self.dir, "other")
        os.makedirs(other)
        for rel in ("Foo.cs", "notes.txt"):
            shutil.copy(os.path.join(self.w.root, rel), os.path.join(other, rel))
        subprocess.run(["git", "init", "-q"], cwd=other, env=env, check=True)
        subprocess.run(["git", "add", "-A"], cwd=other, env=env, check=True)
        out = subprocess.run(["git", "write-tree"], cwd=other, env=env, check=True,
                             capture_output=True, text=True).stdout.strip()
        self.assertEqual(self.obs(), out)

    def test_ignores_artifacts_mtime_empty_dir(self):
        h = self.obs()
        self.w.write("obj/Debug/a.dll", "x")
        self.w.write("bin/b.dll", "y")
        os.utime(os.path.join(self.w.root, "Foo.cs"), (12345, 12345))
        os.makedirs(os.path.join(self.w.root, "empty"))
        self.assertEqual(self.obs(), h)

    def test_content_change_and_revert(self):
        h = self.obs()
        self.w.write("Foo.cs", W.FOO_BROKEN + " ")
        self.assertNotEqual(self.obs(), h)
        self.w.write("Foo.cs", W.FOO_BROKEN)
        self.assertEqual(self.obs(), h)

    def test_exec_bit_changes_hash_unlike_python_hash(self):
        h, p = self.obs(), tree_hash(self.w.root)
        os.chmod(os.path.join(self.w.root, "Foo.cs"), 0o755)
        self.assertNotEqual(self.obs(), h)
        self.assertEqual(tree_hash(self.w.root), p)

    def test_rename_and_new_file(self):
        h = self.obs()
        os.rename(os.path.join(self.w.root, "notes.txt"), os.path.join(self.w.root, "n2.txt"))
        h2 = self.obs()
        self.assertNotEqual(h2, h)
        self.w.write("New.cs", "class N {}")
        self.assertNotEqual(self.obs(), h2)

    def test_gitignore_vs_persistent_index(self):
        """Plik, ktory byl sledzony zanim trafil do .gitignore, dalej wchodzi do hasha (trwaly indeks)."""
        self.w.write("build.log", "1")
        self.obs()
        self.w.write(".gitignore", "build.log\n")
        h = self.obs()
        self.w.write("build.log", "2")
        self.assertNotEqual(self.obs(), h)
        with GitTreeObserver(self.w.root, persistent_index=False) as fresh:
            h2 = fresh()
            self.w.write("build.log", "3")
            self.assertEqual(fresh(), h2)

    def test_gitignore_set_before_first_call_works(self):
        self.w.write(".gitignore", "*.log\n")
        self.w.write("a.log", "1")
        h = self.obs()
        self.w.write("a.log", "2")
        self.assertEqual(self.obs(), h)

    def test_nested_repo_is_a_blind_spot(self):
        nested = os.path.join(self.w.root, "vendor")
        os.makedirs(nested)
        env = dict(os.environ, GIT_CONFIG_GLOBAL=os.devnull, GIT_CONFIG_NOSYSTEM="1")
        for args in (["init", "-q"], ["config", "user.email", "a@example.invalid"],
                     ["config", "user.name", "a"]):
            subprocess.run(["git", *args], cwd=nested, env=env, check=True, capture_output=True)
        with open(os.path.join(nested, "x.cs"), "w") as f:
            f.write("a")
        subprocess.run(["git", "add", "."], cwd=nested, env=env, check=True, capture_output=True)
        subprocess.run(["git", "commit", "-q", "-m", "i"], cwd=nested, env=env, check=True,
                       capture_output=True)
        h, p = self.obs(), tree_hash(self.w.root)
        with open(os.path.join(nested, "x.cs"), "w") as f:
            f.write("b")
        self.assertEqual(self.obs(), h)            # git: slepy punkt
        self.assertNotEqual(tree_hash(self.w.root), p)

    def test_does_not_touch_user_repo_index(self):
        env = dict(os.environ, GIT_CONFIG_GLOBAL=os.devnull, GIT_CONFIG_NOSYSTEM="1")
        subprocess.run(["git", "init", "-q"], cwd=self.w.root, env=env, check=True)
        before = subprocess.run(["git", "status", "--porcelain"], cwd=self.w.root, env=env,
                                capture_output=True, text=True).stdout
        self.obs()
        after = subprocess.run(["git", "status", "--porcelain"], cwd=self.w.root, env=env,
                               capture_output=True, text=True).stdout
        self.assertEqual(before, after)
        self.assertFalse(os.path.exists(os.path.join(self.w.root, ".git", "index")))

    def test_close_removes_gitdir(self):
        o = GitTreeObserver(self.w.root)
        d = o.gitdir
        o()
        o.close()
        self.assertFalse(os.path.exists(d))

    def test_missing_root_raises(self):
        o = GitTreeObserver(os.path.join(self.dir, "nie-ma"))
        self.addCleanup(o.close)
        with self.assertRaises((GitError, FileNotFoundError, NotADirectoryError)):
            o()

    def test_supervisor_tree_stall_same_as_python_hash(self):
        r = self.sup(observer=self.obs).run(W.policy_spin_same_tree)
        self.assertEqual((r.status, r.total, self.w.test_runs), ("NO_PROGRESS", 5, 3))
        self.assertIn("TREE_STALL", r.reason)

    def test_supervisor_oscillation_and_no_false_alarm(self):
        r = self.sup(observer=self.obs).run(W.policy_oscillate)
        self.assertEqual((r.status, r.total), ("NO_PROGRESS", 10))
        self.assertIn("TREE_STALL", r.reason)
        os.remove(self.jpath)
        w2 = W.World(os.path.join(self.dir, "repo"))
        r2 = Supervisor(w2.tools(), Budget(max_steps=50), Journal(self.jpath),
                        observer=self.obs).run(W.policy_explore_then_fix)
        self.assertEqual(r2.status, "DONE")


class TestTimeline(Base):
    def run_compacted(self, **kw):
        kw.setdefault("compact_every", 8)
        kw.setdefault("compact_keep", 3)
        return self.sup(archive=True, **kw).run(W.policy_long_task)

    def reference(self):
        d = tempfile.mkdtemp(prefix="prasowka-loop4-ref-")
        self.addCleanup(shutil.rmtree, d, True)
        w = W.World(os.path.join(d, "repo"))
        jp = os.path.join(d, "journal.jsonl")
        Supervisor(w.tools(), Budget(max_steps=50), Journal(jp)).run(W.policy_long_task)
        return Journal(jp).read()

    def test_timeline_equals_uncompacted_journal(self):
        ref = self.reference()
        self.run_compacted()
        tl = TL.verify(self.jpath)
        self.assertEqual(tl.events, ref)
        self.assertEqual(tl.duplicates_dropped, 0)
        self.assertGreaterEqual(tl.snapshots_seen, 3)

    def test_fold_of_timeline_matches_live(self):
        self.run_compacted()
        full = fold(TL.merge(self.jpath).events)
        live = fold(Journal(self.jpath).read())
        self.assertEqual(full.summary.to_dict(), live.summary.to_dict())
        self.assertEqual(full.summary.total, 30)
        self.assertEqual([s.n for s in full.steps[-len(live.steps):]], [s.n for s in live.steps])

    def test_missing_first_middle_segment_is_gap(self):
        self.run_compacted()
        segs = TL.segments(self.jpath)
        for victim in (segs[0], segs[2]):
            os.rename(victim, victim + ".gone")
            with self.assertRaises(TL.TimelineGap):
                TL.verify(self.jpath)
            os.rename(victim + ".gone", victim)
        TL.verify(self.jpath)

    def test_missing_archive_for_one_compaction_is_gap(self):
        """Zywy plik zaczyna sie snapshotem, a archiwum, z ktorego pochodzi, zniknelo - luka."""
        j = Journal(self.jpath)
        s = self.sup()
        s.run(W.policy_long_task)                      # pelny dziennik, 30 krokow
        compact(j, 3, archive=True)                    # archiwum: segment z krokami 1-30
        compact(j, 2, archive=False)                   # snapshot bez archiwum (nie ma ogona zdarzen)
        TL.verify(self.jpath)                          # to jeszcze ma sens: snapshot po archiwum
        os.rename(self.jpath + ".archive-00030", self.jpath + ".archive-00030.gone")
        with self.assertRaises(TL.TimelineGap):
            TL.merge(self.jpath)

    def test_mismatch_when_live_file_diverges(self):
        self.run_compacted()
        segs = TL.segments(self.jpath)
        recs = Journal(segs[1]).read()
        j2 = Journal(segs[1] + ".new")
        for r in recs:
            if r["t"] == "result" and r["step"] == 12:
                r = dict(r, out="PODMIENIONE")
            j2.append(r)
        os.replace(segs[1] + ".new", segs[1])
        # zmiana tresci archiwum nie zmienia kluczy zdarzen, ale zmienia 'cost' w foldzie osi
        with self.assertRaises(TL.TimelineMismatch):
            TL.verify(self.jpath)

    def test_crash_between_link_and_replace_duplicates_are_dropped(self):
        try:
            self.run_compacted(crash_hook=crash_at("compact_archived", 8))
        except SimulatedCrash:
            pass
        a = self.jpath + ".archive-00008"
        self.assertTrue(os.path.samefile(a, self.jpath))     # ten sam inode
        n_before = len(Journal(a).read())
        self.run_compacted()
        self.assertGreater(len(Journal(a).read()), n_before)  # archiwum ROSNIE po wznowieniu
        tl = TL.verify(self.jpath)
        self.assertGreater(tl.duplicates_dropped, 0)
        self.assertEqual(fold(tl.events).summary.total, 30)
        self.assertEqual(tl.events, self.reference())

    def test_explain_step_and_write_full(self):
        self.run_compacted()
        tl = TL.verify(self.jpath)
        e = TL.explain_step(tl, 9)
        self.assertEqual(e["intent"]["step"], 9)
        self.assertTrue(e["result"]["ok"])
        self.assertIsNone(TL.explain_step(tl, 999))
        out = os.path.join(self.dir, "full.jsonl")
        n = TL.write_full(self.jpath, out)
        self.assertEqual(n, 61)
        self.assertEqual(len(Journal(out).read()), 61)

    def test_no_archives_is_just_live(self):
        self.sup().run(W.policy_long_task)
        tl = TL.verify(self.jpath)
        self.assertEqual(len(tl.segments), 1)
        self.assertEqual(tl.snapshots_seen, 0)


if __name__ == "__main__":
    unittest.main(verbosity=1)
