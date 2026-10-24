"""Demo: cykl zycia dziennika. Uruchom: python3 -B demo.py"""
from __future__ import annotations

import os
import shutil
import tempfile

import world as W
from agentloop import Budget, Journal, SimulatedCrash, Supervisor, VirtualClock, resolve


def show(title, r):
    print(f"\n== {title}")
    for s in r.steps:
        first = s.out.splitlines()[0][:48] if s.out else ""
        print(f"  krok {s.n}: {s.action.tool:<8} ok={s.ok!s:<5} proby={s.attempts} {first}")
    print(f"  => {r.status}: {r.reason} (replayed={r.replayed}, vt={r.vt:.2f}s)")


def crash_at(point, step):
    fired = []

    def hook(p, s):
        if p == point and s == step and not fired:
            fired.append(1)
            raise SimulatedCrash()
    return hook


def kinds(path, repair=True):
    return [x["t"] for x in Journal(path, repair=repair).read()]


def main():
    d = tempfile.mkdtemp(prefix="prasowka-loop2-demo-")
    P = lambda name: os.path.join(d, name)

    # ---- 1. urwany ogon: zachowanie z #14 vs naprawa
    torn = (b'{"t": "intent", "step": 1, "tool": "notify", "args": {"msg": "start"}, "key": "k1", "vt": 0.0}\n'
            b'{"t": "result", "step": 1, "ok": true, "out": "sent", "attempts": 1, "vt": 0.0}\n'
            b'{"t": "intent", "step": 2, "to')
    for label, repair in (("#14 (repair=False)", False), ("v2  (repair=True)", True)):
        p = P(f"torn-{repair}.jsonl")
        with open(p, "wb") as f:
            f.write(torn)
        w = W.World()
        j = Journal(p, repair=repair)
        r = Supervisor(w.tools(), Budget(), j).run(W.policy_notify_then_finish)
        print(f"\n== 1. urwany ogon, {label}")
        print(f"  bieg: {r.status}; rekordow czytelnych po zakonczeniu: {len(Journal(p, repair=repair).read())}; "
              f"obcieto bajtow: {j.repaired_bytes}")
        print(f"  rodzaje: {kinds(p, repair)}")
        w2 = W.World()
        r2 = Supervisor(w2.tools(), Budget(), Journal(p, repair=repair)).run(W.policy_notify_then_finish)
        print(f"  kolejne wznowienie: replayed={r2.replayed}, wywolan narzedzi={w2.notify_calls}")

    # ---- 2. zamkniety bieg
    w = W.World()
    p = P("closed.jsonl")
    Supervisor(w.tools(), Budget(), Journal(p)).run(W.policy_happy)
    size = os.path.getsize(p)
    r = Supervisor(w.tools(), Budget(), Journal(p)).run(W.policy_tripwire)
    show("2. wznowienie zamknietego biegu (policy rzuca wyjatek, gdyby ja wolano)", r)
    print(f"  rozmiar dziennika przed/po: {size}/{os.path.getsize(p)} B; testow uruchomionych: {w.test_runs}")

    # ---- 3. kontrola: bez rekordu 'end'
    W.policy_nondeterministic_after_done.asked = 0
    w = W.World()
    p = P("noend.jsonl")
    Supervisor(w.tools(), Budget(), Journal(p)).run(W.policy_nondeterministic_after_done)
    print(f"\n== 3. kontrola: model zmienia zdanie po DONE")
    print(f"  z rekordem 'end': wywolan notify po pierwszym biegu = {w.notify_calls}")
    r = Supervisor(w.tools(), Budget(), Journal(p)).run(W.policy_nondeterministic_after_done)
    print(f"  drugie wznowienie (replayed={r.replayed}): wywolan notify = {w.notify_calls}")
    with open(p, "rb") as f:
        lines = f.read().splitlines(keepends=True)
    with open(p, "wb") as f:
        f.write(b"".join(lines[:-1]))                      # usuwamy 'end' (jak w #14 po DONE+restart)
    r = Supervisor(w.tools(), Budget(), Journal(p)).run(W.policy_nondeterministic_after_done)
    print(f"  bez rekordu 'end': status={r.status}, wywolan notify = {w.notify_calls} (model dorzucil krok)")

    # ---- 4. czas
    print("\n== 4. czas scienny po wznowieniu (serwer stale 503, max_wall 10 s -> 20 s)")
    for restore in (True, False):
        p = P(f"clock-{restore}.jsonl")
        mk = lambda mw, c: Supervisor(W.World(fetch_failures=10_000).tools(),
                                      Budget(max_wall=mw, backoff_base=4, backoff_cap=30, max_steps=500),
                                      Journal(p), clock=c, seed=3, restore_clock=restore)
        c1 = VirtualClock()
        r1 = mk(10, c1).run(W.policy_fetch_forever)
        c2 = VirtualClock()
        r2 = mk(20, c2).run(W.policy_fetch_forever)
        print(f"  restore_clock={restore!s:<5}: bieg 1 {r1.status} vt={r1.vt:.2f}s | bieg 2 {r2.status} "
              f"vt={r2.vt:.2f}s, snu w biegu 2: {sum(c2.sleeps):.2f}s w {len(c2.sleeps)} przerwach")

    # ---- 5. NEEDS_HUMAN -> resolve
    for outcome, point in (("executed", "after_effect"), ("not_executed", "after_intent")):
        w = W.World()
        p = P(f"human-{outcome}.jsonl")
        try:
            Supervisor(w.tools(), Budget(), Journal(p), crash_hook=crash_at(point, 2)).run(W.policy_charge_twice)
        except SimulatedCrash:
            pass
        r = Supervisor(w.tools(), Budget(), Journal(p)).run(W.policy_charge_twice)
        show(f"5. crash {point} na 'charge' (bez klucza)", r)
        r_again = Supervisor(w.tools(), Budget(), Journal(p)).run(W.policy_charge_twice)
        print(f"  ponowne uruchomienie bez decyzji: {r_again.status}, replayed={r_again.replayed}, obciazenia={w.charges}")
        if outcome == "executed":
            resolve(Journal(p), 2, "executed", out="charged 100 (potwierdzone w panelu platnosci)")
        else:
            resolve(Journal(p), 2, "not_executed")
        print(f"  czlowiek: resolve(step=2, {outcome})")
        r = Supervisor(w.tools(), Budget(), Journal(p)).run(W.policy_charge_twice)
        show("   po decyzji czlowieka", r)
        print(f"  obciazenia: {w.charges}; dziennik: {kinds(p)}")

    # ---- 6. oryginalny wynik przy dedupie
    w = W.World()
    p = P("dedup.jsonl")
    try:
        Supervisor(w.tools(), Budget(), Journal(p), crash_hook=crash_at("after_effect", 2)).run(
            W.policy_notify_then_finish)
    except SimulatedCrash:
        pass
    r = Supervisor(w.tools(), Budget(), Journal(p)).run(W.policy_notify_then_finish)
    show("6. crash po efekcie; powtorka z tym samym kluczem", r)
    print(f"  wywolan notify={w.notify_calls}, efektow={len(w.outbox)}")

    shutil.rmtree(d, ignore_errors=True)


if __name__ == "__main__":
    main()
