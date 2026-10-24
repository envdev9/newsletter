"""Demo #19: dwoch pisarzy na jednym dzienniku - pomiary na prawdziwych procesach.
python3 -B demo.py [powtorzenia]     (domyslnie 20; kazda sekcja powtarzana tyle razy)
"""
from __future__ import annotations

import errno
import fcntl
import os
import random
import signal
import subprocess
import sys
import time

from harness import (HERE, contend, dead_pid, effects, finish, journal_stats, kill_and_takeover, spawn,
                     two_writers, workdir)
from joblock import ExclLock, FlockLock, LockBusy, pid_alive, proc_start_ticks, read_meta

R = int(sys.argv[1]) if len(sys.argv) > 1 else 20
STEPS = 12


def rng_range(xs):
    return f"{min(xs)}..{max(xs)}"


def section1() -> None:
    print(f"== 1. dwoch pisarzy, BEZ blokady ({R} powtorzen, {STEPS} krokow, oczekiwane efekty: {STEPS})")
    for tool in ("plain", "keyed"):
        eff, uniq, fold_tot, intents = [], [], [], []
        for _ in range(R):
            with workdir() as d:
                two_writers(d, "none", STEPS, tool)
                e = effects(d)
                s = journal_stats(d)
                eff.append(len(e)); uniq.append(len({x[1] for x in e}))
                fold_tot.append(s["fold_total"]); intents.append(s["intents"])
        dup = sum(1 for e, u in zip(eff, uniq) if e != STEPS)
        print(f"  narzedzie {tool:5}: efekty {rng_range(eff)} (srednio {sum(eff)/R:.1f}), "
              f"unikalne klucze {rng_range(uniq)}, intents w dzienniku {rng_range(intents)}, "
              f"fold.total {rng_range(fold_tot)}; bieg z duplikatem: {dup}/{R}")


def section2() -> None:
    print(f"== 2. dwoch pisarzy, flock na pliku .lock ({R} powtorzen)")
    for mode in ("flock", "flock-nb"):
        eff, ok, busy, replayed, waits = [], 0, 0, 0, []
        for _ in range(R):
            with workdir() as d:
                rs = two_writers(d, mode, STEPS, "plain")
                eff.append(len(effects(d)))
                ok += sum(1 for r in rs if r.get("status") == "DONE" and not r.get("replayed"))
                replayed += sum(1 for r in rs if r.get("replayed"))
                busy += sum(1 for r in rs if r.get("busy"))
                waits += [r["waited"] for r in rs]
        print(f"  {mode:8}: efekty {rng_range(eff)}; DONE-wykonane {ok}, DONE-odtworzone {replayed}, "
              f"BUSY(75) {busy}; najdluzsze czekanie {max(waits)*1000:.0f} ms")


def section3() -> None:
    print(f"== 3. kill -9 wlasciciela w losowym momencie, przejecie przez drugi proces ({R} powtorzen)")
    rnd = random.Random(19)
    for tool in ("keyed", "plain"):
        statuses: dict[str, int] = {}
        pend = 0
        effs, walls = [], []
        for _ in range(R):
            with workdir() as d:
                r = kill_and_takeover(d, rnd.randint(2, STEPS - 2), "flock", tool, STEPS)
                statuses[r.get("status", "?")] = statuses.get(r.get("status", "?"), 0) + 1
                pend += r["pending_at_kill"]
                effs.append((r["effects"], r["unique_keys"]))
                walls.append(r["b_wall"])
        print(f"  narzedzie {tool:5}: statusy B {statuses}; wiszacy intent w chwili smierci A: {pend}/{R}; "
              f"efekty (lacznie, unikalne) {sorted(set(effs))}; sredni czas B {sum(walls)/R:.2f} s")


def section4() -> None:
    print("== 4. martwy zamek: O_EXCL bez/ze sprawdzaniem wlasciciela vs flock")
    with workdir() as d:
        a = spawn("worker.py", "--dir", d, "--mode", "excl", "--steps", "12", "--delay", "0.004")
        t0 = time.time()
        while len(effects(d)) < 3 and time.time() - t0 < 10:
            time.sleep(0.001)
        os.kill(a.pid, signal.SIGKILL); a.wait(); a.stdout.close(); a.stderr.close()
        meta = read_meta(os.path.join(d, "journal.jsonl.lock"))
        print(f"  po kill -9: plik zamka zostal, pid w nim {meta['pid']}, zyje? {pid_alive(meta['pid'])}")
        b = finish(spawn("worker.py", "--dir", d, "--mode", "excl", "--steps", "12", "--lock-timeout", "1.5"))
        print(f"  B (excl, bez sprawdzania, 1,5 s): busy={b.get('busy')} rc={b['rc']} po {b['waited']} s")
        c = finish(spawn("worker.py", "--dir", d, "--mode", "excl-stale", "--steps", "12", "--lock-timeout", "5"))
        print(f"  C (excl-stale): status={c.get('status')} resumed_from={c.get('resumed_from')} "
              f"efekty={len(effects(d))} unikalne={len({e[1] for e in effects(d)})}")
    with workdir() as d:
        a = spawn("worker.py", "--dir", d, "--mode", "flock", "--steps", "12", "--delay", "0.004")
        t0 = time.time()
        while len(effects(d)) < 3 and time.time() - t0 < 10:
            time.sleep(0.001)
        os.kill(a.pid, signal.SIGKILL); a.wait(); a.stdout.close(); a.stderr.close()
        b = finish(spawn("worker.py", "--dir", d, "--mode", "flock", "--steps", "12", "--lock-timeout", "1.5"))
        print(f"  B (flock): status={b.get('status')} czekal {b['waited']*1000:.0f} ms, efekty={len(effects(d))}")


def section5() -> None:
    print(f"== 5. wyscig przejecia martwego zamka ({R*5} prob, 2 procesy, zamek startuje jako martwy)")
    N = R * 5
    for kind, delay, label in (("excl-stale", 0.0, "O_EXCL + stale, naturalne okno"),
                               ("excl-stale", 0.01, "O_EXCL + stale, okno 10 ms (haczyk testowy)"),
                               ("flock", 0.0, "flock")):
        res = []
        for _ in range(N):
            with workdir() as d:
                res.append(contend(d, kind, delay, stale_pid=dead_pid()))
        ov = sum(r["overlap"] for r in res)
        lost = sum(r["counter"] != r["expected"] for r in res)
        print(f"  {label:46}: obaj w sekcji naraz {ov}/{N}, zgubiona aktualizacja licznika {lost}/{N}")


def section6() -> None:
    print("== 6. ponowne uzycie PID: kill(pid,0) vs pid + czas startu")
    me = os.getpid()
    real = proc_start_ticks(me)
    print(f"  moj pid {me}: naiwnie zyje={pid_alive(me)}; z poprawnym startem={pid_alive(me, real)}; "
          f"z cudzym startem (symulacja reuse)={pid_alive(me, real + 12345)}")
    print(f"  zombie liczone jako martwe: ", end="")
    p = subprocess.Popen([sys.executable, "-c", "pass"])
    time.sleep(0.3)                                   # dziecko zakonczone, nie odebrane przez wait() = zombie
    print(f"pid {p.pid}: kill(0) widzi proces ({os.path.exists(f'/proc/{p.pid}')}), pid_alive={pid_alive(p.pid)}")
    p.wait()


def section7() -> None:
    print("== 7. flock na SAMYM dzienniku vs na osobnym .lock, gdy compact robi os.replace")
    with workdir() as d:
        j = os.path.join(d, "journal.jsonl")
        for label, lockpath in (("flock na journal.jsonl", j), ("flock na journal.jsonl.lock", j + ".lock")):
            open(j, "w").close()
            fd1 = os.open(lockpath, os.O_RDWR | os.O_CREAT)
            fcntl.flock(fd1, fcntl.LOCK_EX | fcntl.LOCK_NB)
            tmp = j + ".tmp"
            with open(tmp, "w") as f:
                f.write("{}\n")
            os.replace(tmp, j)                          # compact() robi dokladnie to
            fd2 = os.open(lockpath, os.O_RDWR | os.O_CREAT)
            try:
                fcntl.flock(fd2, fcntl.LOCK_EX | fcntl.LOCK_NB)
                verdict = "DRUGI TEZ DOSTAL ZAMEK (dwoch wlascicieli)"
            except OSError as e:
                verdict = "drugi odrzucony" if e.errno in (errno.EAGAIN, errno.EACCES) else repr(e)
            print(f"  {label:30}: po os.replace -> {verdict}")
            os.close(fd1); os.close(fd2)
    print("== 7b. unlink pliku .lock przy zwalnianiu")
    with workdir() as d:
        lp = os.path.join(d, "x.lock")
        fa = os.open(lp, os.O_RDWR | os.O_CREAT)
        fcntl.flock(fa, fcntl.LOCK_EX)
        fb = os.open(lp, os.O_RDWR | os.O_CREAT)           # B otworzyl stary i-wezel, czeka na flock
        os.unlink(lp); os.close(fa)                        # A zwalnia i usuwa plik
        fcntl.flock(fb, fcntl.LOCK_EX | fcntl.LOCK_NB)     # B dostaje zamek na OSIEROCONYM i-wezle
        fc = os.open(lp, os.O_RDWR | os.O_CREAT)           # C tworzy nowy plik pod ta sama nazwa
        try:
            fcntl.flock(fc, fcntl.LOCK_EX | fcntl.LOCK_NB)
            print("  B i C trzymaja 'ten sam' zamek jednoczesnie: tak (dwoch wlascicieli)")
        except OSError:
            print("  B i C trzymaja 'ten sam' zamek jednoczesnie: nie")
        os.close(fb); os.close(fc)


def section8() -> None:
    print("== 8. zamek dziedziczony przez dziecko po fork() vs subprocess.Popen")
    for how in ("fork", "popen"):
        with workdir() as d:
            code = (
                "import os,sys,time,subprocess\n"
                f"sys.path.insert(0, {HERE!r})\n"
                "from joblock import FlockLock\n"
                f"l = FlockLock({os.path.join(d, 'j.lock')!r}).acquire()\n"
                f"how = {how!r}\n"
                "if how == 'fork':\n"
                "    pid = os.fork()\n"
                "    if pid == 0:\n"
                "        time.sleep(60); os._exit(0)\n"
                "else:\n"
                "    pid = subprocess.Popen(['sleep', '60']).pid\n"
                "print(pid, flush=True)\n"
                "time.sleep(60)\n")
            p = subprocess.Popen([sys.executable, "-B", "-c", code], stdout=subprocess.PIPE, text=True)
            child = int(p.stdout.readline())
            os.kill(p.pid, signal.SIGKILL); p.wait(); p.stdout.close()
            try:
                FlockLock(os.path.join(d, "j.lock")).acquire().release()
                verdict = "zamek wolny"
            except LockBusy as e:
                verdict = f"ZAMEK DALEJ ZAJETY; w metadanych pid {e.holder['pid']}, zyje? {pid_alive(e.holder['pid'])}"
            finally:
                os.kill(child, signal.SIGKILL)
            print(f"  wlasciciel zabity, dziecko ({how}) zyje: {verdict}")


def section9() -> None:
    print(f"== 9. dwoch pisarzy + kompaktowanie (compact_every=4), {R} powtorzen, narzedzie keyed")
    for mode in ("none", "flock"):
        crashed = intact = 0
        eff, errs = [], {}
        for _ in range(R):
            with workdir() as d:
                rs = two_writers(d, mode, 20, "keyed", compact_every=4)
                eff.append(len(effects(d)))
                for r in rs:
                    if r["rc"] not in (0, 75):
                        crashed += 1
                        k = (r.get("stderr", "").strip().splitlines() or ["?"])[-1][:70]
                        errs[k] = errs.get(k, 0) + 1
                st = journal_stats(d)
                intact += (st["fold_total"] == 20 and eff[-1] == 20)
        print(f"  {mode:5}: efekty {rng_range(eff)} (oczekiwane 20); procesy zakonczone wyjatkiem {crashed}/{2*R}; "
              f"bieg poprawny (20 krokow w dzienniku i 20 efektow) {intact}/{R}")
        for k, v in errs.items():
            print(f"         {v}x {k}")


if __name__ == "__main__":
    only = sys.argv[2].split(",") if len(sys.argv) > 2 else None     # np. "9" albo "3,5"
    for i, fn in enumerate((section1, section2, section3, section4, section5, section6, section7, section8,
                            section9), 1):
        if only and str(i) not in only:
            continue
        fn()
        sys.stdout.flush()
