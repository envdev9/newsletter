"""Demo: wypisuje przebieg kazdego scenariusza. Uruchom: python3 demo.py"""
from __future__ import annotations

import os
import shutil
import tempfile

import world as W
from agentloop import Budget, Journal, SimulatedCrash, Supervisor, VirtualClock


def show(title, r):
    print(f"\n== {title}")
    for s in r.steps:
        first = s.out.splitlines()[0][:60] if s.out else ""
        print(f"  krok {s.n}: {s.action.tool:<10} ok={s.ok!s:<5} proby={s.attempts} {first}")
    print(f"  => {r.status}: {r.reason} (koszt={r.cost}, wznowiono_od={r.resumed_from})")


def main():
    d = tempfile.mkdtemp(prefix="prasowka-loop-demo-")
    n = [0]

    def sup(w, **kw):
        n[0] += 1
        b = kw.pop("budget", Budget())
        path = kw.pop("path", os.path.join(d, f"j{n[0]}.jsonl"))
        return Supervisor(w.tools(), b, Journal(path), **kw)

    show("1. zapetlenie: ta sama akcja", sup(W.World()).run(W.policy_same_action))
    show("2. cykl edit/test", sup(W.World()).run(W.policy_ping_pong))
    show("3. rozne akcje, ten sam blad", sup(W.World()).run(W.policy_varied_but_stuck))
    show("4. budzet krokow", sup(W.World(), budget=Budget(max_steps=5)).run(W.policy_never_ends))

    w = W.World(fetch_failures=3)
    clock = VirtualClock()
    r = sup(w, clock=clock).run(W.policy_fetch_once)
    show("5. retry z backoffem (3 awarie 503)", r)
    print("  opoznienia (full jitter, seed=7):", [round(x, 3) for x in clock.sleeps])

    w = W.World()
    path = os.path.join(d, "resume.jsonl")
    fired = []

    def hook(p, s):
        if p == "after_effect" and s == 2 and not fired:
            fired.append(1)
            raise SimulatedCrash()
    try:
        sup(w, path=path, crash_hook=hook).run(W.policy_notify_then_finish)
    except SimulatedCrash:
        print("\n== 6. crash po efekcie, przed zapisem wyniku (notify z kluczem)")
        print("  dziennik po crashu:")
        for rec in Journal(path).read():
            print("   ", rec)
    r = sup(w, path=path).run(W.policy_notify_then_finish)
    show("   wznowienie", r)
    print(f"  wywolan notify={w.notify_calls}, efektow w outbox={len(w.outbox)}")

    w = W.World()
    path = os.path.join(d, "unsafe.jsonl")
    fired.clear()

    def hook2(p, s):
        if p == "after_effect" and s == 2 and not fired:
            fired.append(1)
            raise SimulatedCrash()
    try:
        sup(w, path=path, crash_hook=hook2).run(W.policy_charge_twice)
    except SimulatedCrash:
        pass
    r = sup(w, path=path).run(W.policy_charge_twice)
    show("7. crash po 'charge' (narzedzie bez klucza)", r)
    print(f"  obciazenia: {w.charges}")

    shutil.rmtree(d, ignore_errors=True)


if __name__ == "__main__":
    main()
