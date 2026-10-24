#!/usr/bin/env python3
"""Testy ctxledger.py. Uruchomienie: python3 -B test_ctxledger.py  (stdlib, ok. 1-2 min: prawdziwe testy + sweep)."""
import os
import re
import sys

import ctxledger as L
from ctxdedup import make_diff

N, FAILED = 0, []


def check(cond, msg):
    global N
    N += 1
    if not cond:
        FAILED.append(msg)
        print("FAIL:", msg)


def ev(kind, path, meta, text, **kw):
    d = {"id": len(kw.get("_ids", [])) + 1, "kind": kind, "path": path, "meta": meta, "text": text}
    d.update({k: v for k, v in kw.items() if k != "_ids"})
    return d


# ---- check_read: jednostkowo
A = "a\nb\nc\nd\ne\n"
B = "a\nb\nC\nd\ne\n"
dAB = make_diff(A, B)
check(L.check_read([ev("read", "f", "full", A)], "f", A) == "ok", "pelny odczyt -> ok")
check(L.check_read([ev("read", "f", "full", A), ev("read", "f", "diff", dAB)], "f", B) == "ok", "pelny + diff -> ok")
check(L.check_read([ev("read", "f", "diff", dAB)], "f", B) == "dangling", "diff bez bazy -> dangling")
check(L.check_read([ev("read", "f", "same", "stub")], "f", A) == "dangling", "stub bez bazy -> dangling")
check(L.check_read([ev("read", "f", "diff", dAB), ev("read", "f", "full", B)], "f", B) == "ok",
      "osierocony diff, potem pelny odczyt -> ok (pelny odczyt leczy)")
check(L.check_read([ev("read", "f", "full", A)], "f", B) == "wrong", "stara wersja zamiast nowej -> wrong")
check(L.check_read([ev("read", "f", "full", "x\ny\n"), ev("read", "f", "diff", dAB)], "f", B) == "wrong",
      "diff na zlej bazie -> wrong")
check(L.check_read([], "f", A) == "dangling", "pusty kontekst -> dangling")
check(L.check_read([ev("read", "g", "full", A)], "f", A) == "dangling", "inny plik nie liczy sie")

# ---- check_grep: jednostkowo
g1 = ev("grep", None, "full", "", shown=[("f", 1, "x"), ("f", 2, "y")], omitted=[])
g2 = ev("grep", None, "full", "", shown=[("f", 3, "z")], omitted=[("f", 1), ("f", 2)])
truth = [("f", 1, "x"), ("f", 2, "y"), ("f", 3, "z")]
check(L.check_grep([g1, g2], g2, truth) == "ok", "grep: pominiete linie odtwarzalne")
check(L.check_grep([g2], g2, truth) == "dangling", "grep: pominiete linie bez zrodla -> dangling")
g3 = ev("grep", None, "full", "", shown=[("f", 1, "STARE")], omitted=[])
check(L.check_grep([g3, g2], g2, truth) == "dangling", "grep: brak linii 2 -> dangling")
g4 = ev("grep", None, "full", "", shown=[("f", 1, "STARE"), ("f", 2, "y")], omitted=[])
check(L.check_grep([g4, g2], g2, truth) == "wrong", "grep: przestarzala linia -> wrong")

# ---- formatowanie
check(L.fmt_grep([]) == "(brak dopasowan)", "pusty wynik grep")
check(L.fmt_grep([("f", 3, "z")]) == "f:3:z", "format linii grep")
h = L.omit_header([("a.py", 1), ("a.py", 5), ("b.py", 2)], 7)
check(h == "[pominieto 3 z 7 linii - widoczne wyzej, numery: a.py: 1,5; b.py: 2]", "naglowek pominiec: %r" % h)

# ---- prawdziwa sesja
steps = L.build_session()
check(len(steps) == 19, "19 krokow")
check([s["kind"] for s in steps].count("grep") == 8, "8 grep")
fx = open(os.path.join(L.FIXTURE, "ctxsearch.py"), encoding="utf-8").read().split("\n")
mine = [("ctxsearch.py", i + 1, t) for i, t in enumerate(fx) if re.search("def ", t)]
check(steps[0]["lines"] == mine, "grep 'def ' == niezalezne skanowanie pliku (%d linii)" % len(mine))
check(steps[3]["lines"] == steps[0]["lines"], "krok 4 identyczny z 1")
check(set(steps[4]["lines"]) - set(steps[0]["lines"]) and not (set(steps[4]["lines"]) <= set(steps[0]["lines"])),
      "krok 5 ma linie spoza kroku 1 (class)")
check(set(steps[4]["lines"]) & set(steps[0]["lines"]), "krok 5 ma czesc wspolna z krokiem 1")
n_before = {l for _, l, _ in steps[1]["lines"] if True}
check(steps[1]["lines"] != steps[6]["lines"], "po edycji grep rrf rozni sie (zmieniona linia)")
shift = [(a, b) for a, b in zip(steps[6]["lines"], steps[9]["lines"]) if a[0] == "ctxsearch.py"]
check(shift and all(b[1] == a[1] + 1 for a, b in shift), "wstawiona linia przesuwa numery o 1 (%d wynikow)" % len(shift))
check(steps[7]["result"].startswith("OK: 40 asercji") and steps[7]["result"].endswith("[exit 0]"), "testy fixture przechodza")

# ---- polityki: zero bledow tam gdzie powinno
for keep in L.KEEP_SCENARIOS:
    for name in ("none", "epoch", "chain", "chain-bez-grep", "chain-tylko-grep"):
        c, st, bad = L.summarize(steps, L.POL[name], keep)
        check(bad == 0, "%s keep=%d: zero bledow" % (name, keep))
c0, st0, bad0 = L.summarize(steps, L.POL["ignore"], 0)
check(st0["read"]["dangling"] == 2 and st0["grep"]["dangling"] == 2 and bad0 == 4,
      "ignore keep=0: 2 wiszace odczyty + 2 wiszace grep (%r)" % (st0,))
c6, st6, bad6 = L.summarize(steps, L.POL["last"], 6)
check(st6["read"]["dangling"] == 2 and bad6 == 2, "last keep=6: osierocony diff -> 2 wiszace odczyty")
cc6 = L.summarize(steps, L.POL["chain"], 6)[0]
ce6 = L.summarize(steps, L.POL["epoch"], 6)[0]
check(cc6["weighted"] < ce6["weighted"], "chain tanszy od epoch przy ogonie 6")
cn = L.summarize(steps, L.POL["none"], 0)[0]
check(cc6["weighted"] < cn["weighted"], "chain tanszy od none (koszt wazony)")

# ---- brak kompakcji: wszystkie polityki dedupe sa rownowazne
nc = len(steps) + 5
base = L.simulate(steps, L.POL["ignore"], 0, nc)
for name in ("epoch", "last", "chain"):
    other = L.simulate(steps, L.POL[name], 0, nc)
    check(other[0] == base[0], "bez kompakcji %s == ignore (snapshoty identyczne)" % name)
check(base[2]["read"]["dangling"] + base[2]["grep"]["dangling"] == 0, "bez kompakcji brak wiszacych")

# ---- ogon obejmuje wszystko: chain == ignore co do pominiec
cb = L.simulate(steps, L.POL["chain"], 10000)[2]
ib = L.simulate(steps, L.POL["ignore"], 10000)[2]
check(cb["omitted_lines"] == ib["omitted_lines"] and cb["diff_reads"] == ib["diff_reads"],
      "ogon obejmuje cale okno: chain nie traci dedupikacji")

# ---- wlasnosc: kompakcja w kazdym miejscu x ogony
rows = {r[0]: r for r in L.sweep_table(steps, list(range(1, len(steps))), (0, 2, 4, 6, 8, 12))}
for name in ("none", "epoch", "chain", "chain-bez-grep", "chain-tylko-grep"):
    check(rows[name][3] == 0, "sweep %s: zero bledow w %d kombinacjach" % (name, rows[name][1]))
check(rows["ignore"][2] > 0 and rows["ignore"][3] > 0, "sweep ignore: bledy wystepuja (test negatywny)")
check(rows["last"][2] > 0, "sweep last: bledy wystepuja (test negatywny)")
check(rows["chain"][5] <= rows["epoch"][5], "sweep: chain nie drozszy od epoch (srednio)")
check(rows["none"][4] == rows["chain"][4], "te same liczby sprawdzen dla none i chain")

# ---- determinizm
check(L.summarize(steps, L.POL["chain"], 6)[0] == L.summarize(steps, L.POL["chain"], 6)[0], "deterministyczne")

if FAILED:
    print("BLAD: %d z %d" % (len(FAILED), N))
    sys.exit(1)
print("OK: %d asercji, 0 niepowodzen" % N)
