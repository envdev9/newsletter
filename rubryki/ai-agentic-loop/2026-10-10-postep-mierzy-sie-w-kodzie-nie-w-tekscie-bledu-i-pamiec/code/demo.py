"""Demo: detektor postepu na hashu drzewa + snapshoty stanu. Output trafia do artykulu.
Uruchom: python3 -B demo.py   (tylko stdlib; katalogi tymczasowe w /tmp sa sprzatane)."""
from __future__ import annotations

import os
import shutil
import tempfile

import world as W
from agentloop import (Budget, Journal, SimulatedCrash, Supervisor, compact, fold, tree_hash)


class Sandbox:
    def __init__(self, **world_kw):
        self.dir = tempfile.mkdtemp(prefix="prasowka-loop3-")
        self.w = W.World(os.path.join(self.dir, "repo"), **world_kw)
        self.jpath = os.path.join(self.dir, "journal.jsonl")

    def sup(self, budget=None, with_tree=True, **kw):
        obs = (lambda: tree_hash(self.w.root)) if with_tree else None
        return Supervisor(self.w.tools(), budget or Budget(), Journal(self.jpath), observer=obs, **kw)

    def close(self):
        shutil.rmtree(self.dir, ignore_errors=True)


def show(r, indent="  "):
    print(f"{indent}=> {r.status}: {r.reason}")
    print(f"{indent}   krokow lacznie={r.total}, w oknie={len(r.steps)}, koszt={r.cost}, replayed={r.replayed}")


def crash_at(point, step):
    fired = []

    def hook(p, s):
        if p == point and s == step and not fired:
            fired.append(1)
            raise SimulatedCrash()
    return hook


def naive_unchanged(recs, n):
    """Naiwny detektor: 'drzewo bez zmian w jakimkolwiek oknie n krokow'. Do porownania."""
    ths = [r["th"] for r in recs if r["t"] == "result" and "th" in r]
    return any(len(set(ths[i:i + n])) == 1 for i in range(len(ths) - n + 1))


def main() -> None:
    print("== 1. hash drzewa: co sie liczy jako zmiana")
    sb = Sandbox()
    h0 = tree_hash(sb.w.root)
    sb.w.write("obj/Debug/Foo.dll", "binarka 1")
    print(f"  zapis do obj/ (artefakt buildu)    : hash {'ten sam' if tree_hash(sb.w.root) == h0 else 'ZMIENIONY'}")
    os.utime(os.path.join(sb.w.root, "Foo.cs"), (1, 1))
    print(f"  zmiana mtime pliku                 : hash {'ten sam' if tree_hash(sb.w.root) == h0 else 'ZMIENIONY'}")
    sb.w.write("Foo.cs", W.FOO_BROKEN + " ")
    h1 = tree_hash(sb.w.root)
    print(f"  jedna spacja w Foo.cs              : hash {'ten sam' if h1 == h0 else 'ZMIENIONY'}")
    sb.w.write("Foo.cs", W.FOO_BROKEN)
    print(f"  cofniecie do poprzedniej tresci    : hash {'wrocil do pierwotnego' if tree_hash(sb.w.root) == h0 else 'inny'}")
    sb.close()

    for title, pol in (("2. 'kreci sie': testy na tym samym kodzie", W.policy_spin_same_tree),
                       ("3. oscylacja v1 <-> v2 (obie wersje nie dzialaja)", W.policy_oscillate)):
        print(f"\n== {title}")
        for with_tree in (False, True):
            sb = Sandbox()
            r = sb.sup(with_tree=with_tree).run(pol)
            print(f"  detektor drzewa {'WL' if with_tree else 'WYL'}: testow uruchomionych={sb.w.test_runs}")
            show(r, "    ")
            sb.close()

    print("\n== 4. brak falszywych alarmow (drzewo-detektor WL, naiwny 'drzewo bez zmian w oknie 4 krokow' obok)")
    for name, pol in (("progres (3 proby naprawy)", W.policy_progress),
                      ("rozeznanie: 8 odczytow, potem naprawa", W.policy_explore_then_fix)):
        sb = Sandbox()
        r = sb.sup().run(pol)
        print(f"  {name}: {r.status} ({r.reason}); naiwny detektor by zadzialal: "
              f"{naive_unchanged(Journal(sb.jpath).read(), 4)}")
        sb.close()
    sb = Sandbox()
    sb.sup().run(W.policy_explore_then_fix)
    ths = [x["th"][:8] for x in Journal(sb.jpath).read() if x["t"] == "result"]
    print(f"  hashe drzewa po kolejnych krokach rozeznania: {ths}")
    sb.close()

    print("\n== 5. kompaktowanie: 30 krokow, compact_every=8, keep=3")
    sb = Sandbox()
    r_full = sb.sup(Budget(max_steps=50)).run(W.policy_long_task)
    full_bytes, full_recs = os.path.getsize(sb.jpath), len(Journal(sb.jpath).read())
    print(f"  bez kompaktowania : {r_full.status}, krokow={r_full.total}, koszt={r_full.cost}, "
          f"dziennik={full_bytes} B / {full_recs} rekordow, efektow notify={len(sb.w.outbox)}")
    sb.close()
    sb = Sandbox()
    r_c = sb.sup(Budget(max_steps=50), compact_every=8, compact_keep=3).run(W.policy_long_task)
    recs = Journal(sb.jpath).read()
    print(f"  z kompaktowaniem  : {r_c.status}, krokow={r_c.total}, koszt={r_c.cost}, "
          f"dziennik={os.path.getsize(sb.jpath)} B / {len(recs)} rekordow, efektow notify={len(sb.w.outbox)}")
    print(f"  rodzaje rekordow  : {[x['t'] for x in recs]}")
    st = fold(recs)
    print(f"  stan z dziennika  : total={st.summary.total}, okno={[s.n for s in st.steps]}")
    sb.close()

    print("\n== 6. crash W TRAKCIE kompaktowania (compact_every=8, keep=3)")
    for point in ("compact_tmp_written", "compact_replaced"):
        sb = Sandbox()
        try:
            sb.sup(Budget(max_steps=50), compact_every=8, compact_keep=3,
                   crash_hook=crash_at(point, 8)).run(W.policy_long_task)
        except SimulatedCrash:
            pass
        tmp = os.path.exists(sb.jpath + ".tmp")
        kinds = [x["t"] for x in Journal(sb.jpath).read()]
        r = sb.sup(Budget(max_steps=50), compact_every=8, compact_keep=3).run(W.policy_long_task)
        print(f"  crash po '{point}': plik .tmp zostal={tmp}, rekordow po crashu={len(kinds)} "
              f"(pierwszy: {kinds[0]})")
        print(f"    wznowienie: {r.status}, krokow={r.total}, koszt={r.cost}, efektow notify={len(sb.w.outbox)}")
        sb.close()

    print("\n== 7. detektory przezywaja kompaktowanie (tree_fail w snapshocie), compact_every=3 keep=1")
    sb = Sandbox()
    r = sb.sup(compact_every=3, compact_keep=1).run(W.policy_spin_same_tree)
    show(r, "  ")
    kinds = [x["t"] for x in Journal(sb.jpath).read()]
    print(f"  dziennik: {kinds}")
    sb.close()

    print("\n== 8. archiwum przed kompaktowaniem (audyt)")
    sb = Sandbox()
    sb.sup(Budget(max_steps=50), compact_every=10, compact_keep=2, archive=True).run(W.policy_long_task)
    names = sorted(n for n in os.listdir(sb.dir) if n.startswith("journal"))
    print(f"  pliki: {names}")
    first = Journal(os.path.join(sb.dir, names[1])).read()
    print(f"  najstarsze archiwum: {len(first)} rekordow, rodzaje: {sorted(set(x['t'] for x in first))}, "
          f"wynikow krokow: {len([x for x in first if x['t'] == 'result'])}")
    sb.close()

    print("\n== 9. granica: 'model', ktory potrzebuje starej historii")
    for every in (0, 3):
        sb = Sandbox()
        r = sb.sup(compact_every=every, compact_keep=1 if every else 3).run(W.policy_needs_old_history)
        print(f"  compact_every={every}: {r.reason}")
        sb.close()


if __name__ == "__main__":
    main()
