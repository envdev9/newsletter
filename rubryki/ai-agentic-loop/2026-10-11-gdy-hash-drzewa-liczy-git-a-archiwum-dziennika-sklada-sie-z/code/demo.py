"""Demo #18: hash drzewa przez `git write-tree` + os zdarzen z segmentow archiwum.
Uruchom: python3 -B demo.py   (stdlib + git; katalogi tymczasowe w /tmp sa sprzatane)."""
from __future__ import annotations

import os
import shutil
import statistics
import subprocess
import tempfile
import time

import timeline as TL
import world as W
from agentloop import Budget, Journal, SimulatedCrash, Supervisor, fold, tree_hash
from gittree import GitTreeObserver


def crash_at(point, step):
    fired = []

    def hook(p, s):
        if p == point and s == step and not fired:
            fired.append(1)
            raise SimulatedCrash()
    return hook


class Sandbox:
    def __init__(self):
        self.dir = tempfile.mkdtemp(prefix="prasowka-loop4-")
        self.w = W.World(os.path.join(self.dir, "repo"))
        self.jpath = os.path.join(self.dir, "journal.jsonl")

    def sup(self, budget=None, observer=None, **kw):
        return Supervisor(self.w.tools(), budget or Budget(), Journal(self.jpath), observer=observer, **kw)

    def close(self):
        shutil.rmtree(self.dir, ignore_errors=True)


def show(r, indent="  "):
    print(f"{indent}=> {r.status}: {r.reason}")
    print(f"{indent}   krokow={r.total}, w oknie={len(r.steps)}, koszt={r.cost}")


def same(a, b):
    return "taki sam" if a == b else "ZMIENIONY"


def table_row(label, w, py0, git0, obs):
    py, gi = tree_hash(w.root), obs()
    print(f"  {label:<36} python: {same(py, py0):<9} git: {same(gi, git0)}")


def part_git_vs_content() -> None:
    print("== 1. co jest zmiana: tree_hash (python, stala lista ignore) vs git write-tree")
    sb = Sandbox()
    root = sb.w.root
    with GitTreeObserver(root) as obs:
        py0, git0 = tree_hash(root), obs()
        print(f"  git tree (pierwsze 12 znakow): {git0[:12]}  dlugosc hasha: python {len(py0)} / git {len(git0)} hex")
        sb.w.write("obj/Debug/Foo.dll", "binarka")
        table_row("zapis do obj/", sb.w, py0, git0, obs)
        os.utime(os.path.join(root, "Foo.cs"), (1, 1))
        table_row("zmiana mtime", sb.w, py0, git0, obs)
        os.makedirs(os.path.join(root, "pusty"))
        table_row("pusty katalog", sb.w, py0, git0, obs)
        os.chmod(os.path.join(root, "Foo.cs"), 0o755)
        table_row("chmod +x (bez zmiany tresci)", sb.w, py0, git0, obs)
        os.chmod(os.path.join(root, "Foo.cs"), 0o644)
        table_row("chmod z powrotem 644", sb.w, py0, git0, obs)
        sb.w.write("build.log", "log z timestampem 1")
        table_row("nowy plik build.log", sb.w, py0, git0, obs)
        sb.w.write(".gitignore", "build.log\n")
        gi1, py1 = obs(), tree_hash(root)
        sb.w.write("build.log", "log z timestampem 2")
        print("  dopisano .gitignore z build.log, potem kolejna zmiana logu:")
        print(f"    trwaly indeks (plik juz sledzony)  : git {same(obs(), gi1)}   <- pulapka")
        print(f"    python tree_hash                   : {same(tree_hash(root), py1)}")
    with GitTreeObserver(root, persistent_index=False) as fresh:
        g2 = fresh()
        sb.w.write("build.log", "log z timestampem 3")
        print(f"    swiezy indeks za kazdym razem      : git {same(fresh(), g2)}")
    sb.close()


def part_nested_repo() -> None:
    print("\n== 2. pulapka: zagniezdzone repo (submodul/vendored clone) w drzewie")
    sb = Sandbox()
    nested = os.path.join(sb.w.root, "vendor", "lib")
    os.makedirs(nested)
    env = dict(os.environ, GIT_CONFIG_GLOBAL=os.devnull, GIT_CONFIG_NOSYSTEM="1")
    for args in (["init", "-q"], ["config", "user.email", "x@example.invalid"], ["config", "user.name", "x"]):
        subprocess.run(["git", *args], cwd=nested, env=env, check=True, capture_output=True)
    with open(os.path.join(nested, "lib.cs"), "w") as f:
        f.write("class Lib { }\n")
    subprocess.run(["git", "add", "."], cwd=nested, env=env, check=True, capture_output=True)
    subprocess.run(["git", "commit", "-q", "-m", "init"], cwd=nested, env=env, check=True, capture_output=True)
    with GitTreeObserver(sb.w.root) as obs:
        git0, py0 = obs(), tree_hash(sb.w.root)
        with open(os.path.join(nested, "lib.cs"), "w") as f:
            f.write("class Lib { int Zmiana; }\n")
        print(f"  zmiana pliku w zagniezdzonym repo (niezacommitowana): git {same(obs(), git0)}, "
              f"python {same(tree_hash(sb.w.root), py0)}")
    sb.close()


def part_supervisor() -> None:
    print("\n== 3. nadzorca z GitTreeObserver jako observer (te same scenariusze co w #17)")
    for title, pol in (("kreci sie na tym samym kodzie", W.policy_spin_same_tree),
                       ("oscylacja v1 <-> v2", W.policy_oscillate),
                       ("progres (3 proby)", W.policy_progress),
                       ("rozeznanie: 8 odczytow + naprawa", W.policy_explore_then_fix)):
        for kind in ("python", "git"):
            sb = Sandbox()
            if kind == "git":
                with GitTreeObserver(sb.w.root) as obs:
                    r = sb.sup(observer=obs).run(pol)
            else:
                r = sb.sup(observer=lambda: tree_hash(sb.w.root)).run(pol)
            print(f"  {title:<34} {kind:<6}: {r.status:<11} krokow={r.total:<3} testow={sb.w.test_runs} "
                  f"koszt={r.cost}")
            sb.close()


def make_big_tree(root: str, n: int) -> None:
    for i in range(n):
        d = os.path.join(root, f"p{i % 50:02d}", f"s{i % 7}")
        os.makedirs(d, exist_ok=True)
        with open(os.path.join(d, f"F{i:05d}.cs"), "w") as f:
            f.write(f"// plik {i}\n" + ("class C%d { int X() => %d; }\n" % (i, i)) * 40)


def timed(fn, n=5):
    xs = []
    for _ in range(n):
        t = time.perf_counter()
        fn()
        xs.append((time.perf_counter() - t) * 1000)
    return statistics.median(xs)


def part_bench() -> None:
    for n in (200, 5000):
        print(f"\n== 4. koszt: {n} plikow (~1.2 KB), mediana z 5 wywolan, 1 maszyna, ms")
        d = tempfile.mkdtemp(prefix="prasowka-loop4-big-")
        try:
            make_big_tree(d, n)
            py = timed(lambda: tree_hash(d))
            print(f"  python tree_hash (czyta wszystkie bajty)  : {py:8.1f}")
            with GitTreeObserver(d, persistent_index=False) as fresh:
                t = time.perf_counter()
                fresh()
                cold = (time.perf_counter() - t) * 1000
                print(f"  git, swiezy indeks za kazdym razem        : {timed(fresh):8.1f}   (1. wywolanie {cold:.1f})")
            with GitTreeObserver(d) as obs:
                t = time.perf_counter()
                obs()
                cold = (time.perf_counter() - t) * 1000
                warm = timed(obs)
                p = os.path.join(d, "p00", "s0", "F00000.cs")
                k = [0]

                def touch_one():
                    k[0] += 1
                    with open(p, "a") as f:
                        f.write(f"// {k[0]}\n")
                    obs()
                one = timed(touch_one)
                print(f"  git, trwaly indeks: 1. wywolanie          : {cold:8.1f}")
                print(f"  git, trwaly indeks: nic sie nie zmienilo  : {warm:8.1f}")
                print(f"  git, trwaly indeks: zmiana jednego pliku  : {one:8.1f}")
                print(f"  baza obiektow git po tym wszystkim        : {obs.object_bytes() // 1024} KiB "
                      f"(tresc drzewa ~{n * 1200 // 1024} KiB)")
        finally:
            shutil.rmtree(d, ignore_errors=True)


def part_timeline() -> None:
    print("\n== 5. os zdarzen z archiwow: 30 krokow, compact_every=8, keep=3, archive=True")
    ref = Sandbox()
    ref.sup(Budget(max_steps=50)).run(W.policy_long_task)
    full_ref = Journal(ref.jpath).read()
    sb = Sandbox()
    sb.sup(Budget(max_steps=50), compact_every=8, compact_keep=3, archive=True).run(W.policy_long_task)
    names = sorted(n for n in os.listdir(sb.dir) if n.startswith("journal"))
    print(f"  pliki: {names}")
    live = Journal(sb.jpath).read()
    print(f"  zywy plik: {len(live)} rekordow ({[r['t'] for r in live][:3]}...)")
    tl = TL.verify(sb.jpath)
    print(f"  os: {len(tl.events)} zdarzen z {len(tl.segments)} segmentow, snapshotow pominietych: "
          f"{tl.snapshots_seen}, duplikatow: {tl.duplicates_dropped}")
    print(f"  os == dziennik BEZ kompaktowania (rekord po rekordzie): {tl.events == full_ref} "
          f"({len(full_ref)} rekordow)")
    e = TL.explain_step(tl, 3)
    print(f"  explain_step(3): narzedzie={e['intent']['tool']}, klucz={e['intent']['key']}, "
          f"wynik ok={e['result']['ok']}, resolve={e['resolve']}")
    ref.close()

    print("\n== 6. luka: usuniecie segmentu archiwum")
    for victim in (names[1], names[2]):
        os.rename(os.path.join(sb.dir, victim), os.path.join(sb.dir, victim + ".gone"))
        try:
            TL.verify(sb.jpath)
            print(f"  bez {victim}: brak wykrycia (!)")
        except TL.TimelineGap as ex:
            print(f"  bez {victim}: TimelineGap: {ex}")
        os.rename(os.path.join(sb.dir, victim + ".gone"), os.path.join(sb.dir, victim))
    sb.close()

    print("\n== 7. crash MIEDZY twardym dowiazaniem a os.replace (hook 'compact_archived')")
    sb = Sandbox()
    try:
        sb.sup(Budget(max_steps=50), compact_every=8, compact_keep=3, archive=True,
               crash_hook=crash_at("compact_archived", 8)).run(W.policy_long_task)
    except SimulatedCrash:
        pass
    a1 = os.path.join(sb.dir, "journal.jsonl.archive-00008")
    print(f"  po crashu: archive-00008 i journal.jsonl to ten sam plik (inode): "
          f"{os.path.samefile(a1, sb.jpath)}, rekordow w archiwum: {len(Journal(a1).read())}")
    sb.sup(Budget(max_steps=50), compact_every=8, compact_keep=3, archive=True).run(W.policy_long_task)
    names = sorted(n for n in os.listdir(sb.dir) if n.startswith("journal"))
    print(f"  po wznowieniu: {names}")
    print(f"  rekordow w archive-00008 po wznowieniu: {len(Journal(a1).read())} "
          f"(w momencie kompaktowania bylo 16)")
    naive = sum(len([r for r in Journal(os.path.join(sb.dir, n)).read() if r['t'] != 'snapshot'])
                for n in names)
    tl = TL.verify(sb.jpath)
    print(f"  naiwne sklejenie segmentow: {naive} zdarzen; os po deduplikacji: {len(tl.events)} "
          f"(duplikatow: {tl.duplicates_dropped}), rownowaznosc z zywym plikiem OK")
    print(f"  kroki w osi: {fold(tl.events).summary.total}")
    sb.close()


def main() -> None:
    part_git_vs_content()
    part_nested_repo()
    part_supervisor()
    part_bench()
    part_timeline()


if __name__ == "__main__":
    main()
