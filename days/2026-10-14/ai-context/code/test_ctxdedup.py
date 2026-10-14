#!/usr/bin/env python3
"""Testy ctxdedup.py (stdlib). Uruchom: python3 -B test_ctxdedup.py"""
import random
import sys

import ctxdedup as D

passed = failed = 0


def check(cond, msg):
    global passed, failed
    if cond:
        passed += 1
    else:
        failed += 1
        print("FAIL:", msg)


# --- diff / apply
a = "l1\nl2\nl3\nl4\n"
check(D.apply_diff(a, D.make_diff(a, a)) == a, "diff pusty = identycznosc")
b = "l1\nl2 zmienione\nl3\nl4\nl5\n"
check(D.apply_diff(a, D.make_diff(a, b)) == b, "diff: zmiana + dopisanie")
check(D.apply_diff("", D.make_diff("", "x\ny\n")) == "x\ny\n", "diff: z pustego")
check(D.apply_diff("x\ny\n", D.make_diff("x\ny\n", "")) == "", "diff: do pustego")
try:
    D.apply_diff("inne\nzupelnie\n", D.make_diff(a, b))
    check(False, "diff na zlej bazie powinien rzucic ValueError")
except ValueError:
    check(True, "diff na zlej bazie rzuca ValueError")

rng = random.Random(1234)
ok = 0
for _ in range(300):
    n = rng.randint(0, 40)
    old = ["w%d\n" % rng.randint(0, 9) for _ in range(n)]
    new = list(old)
    for _ in range(rng.randint(0, 6)):
        op = rng.choice("dir")
        if op == "d" and new:
            del new[rng.randrange(len(new))]
        elif op == "i":
            new.insert(rng.randint(0, len(new)), "n%d\n" % rng.randint(0, 99))
        elif op == "r" and new:
            new[rng.randrange(len(new))] = "r%d\n" % rng.randint(0, 99)
    o, nw = "".join(old), "".join(new)
    if D.apply_diff(o, D.make_diff(o, nw)) == nw:
        ok += 1
check(ok == 300, "fuzz 300 losowych edycji: diff odtwarza tekst (%d/300)" % ok)

# --- tok
check(D.tok("") == 0 and D.tok("abcd") == 1 and D.tok("abcde") == 2, "tok = ceil(bajty/4)")

# --- sesja i polityki
steps, final = D.build_session()
check(len(steps) == len(D.SCRIPT) == 17, "17 krokow sesji")
check(all(s["kind"] != "run" or s["result"].endswith("[exit 0]") for s in steps), "testy w sesji przechodza (exit 0)")
check(final["ctxsearch.py"].count("def rrf(rank_lists, k=60):") == 1, "po sesji k=60 przywrocone")

snaps = {p: D.simulate(steps, p)[0] for p in D.POLICIES}
cost = {p: D.cost_of(snaps[p]) for p in D.POLICIES}
check(cost["none"]["final_ctx"] > cost["append"]["final_ctx"] * 2, "append: kontekst koncowy > 2x mniejszy")
check(cost["append"]["rewritten"] < cost["retro"]["rewritten"], "append zapisuje do cache mniej niz retro")
check(cost["append"]["weighted"] < cost["none"]["weighted"], "append tanszy niz none (cache 0.1/1.25)")
check(cost["retro"]["token_turns"] < cost["append"]["token_turns"], "retro ma mniej token-tur niz append")
check(cost["retro"]["weighted"] > cost["append"]["weighted"], "ale retro placi wiecej za zapis")

# historia nietknieta przy append: kontekst w turze t jest prefiksem kontekstu w turze t+1
for p in ("none", "append", "append+"):
    pre = all(snaps[p][i] == snaps[p][i + 1][:len(snaps[p][i])] for i in range(len(snaps[p]) - 1))
    check(pre, "%s: historia nigdy nie jest mutowana (prefiks)" % p)
pre = all(snaps["retro"][i] == snaps["retro"][i + 1][:len(snaps["retro"][i])] for i in range(len(snaps["retro"]) - 1))
check(not pre, "retro mutuje historie (kontekst nie jest prefiksem)")

for p in D.POLICIES:
    tot, bad = D.verify_policy(steps, p)
    check(tot == 8 and bad == 0, "%s: wszystkie 8 odczytow odtwarzalnych z kontekstu" % p)
    _, ev = D.simulate(steps, p)
    check(D.reconstruct(ev, "ctxsearch.py") == final["ctxsearch.py"], "%s: stan koncowy ctxsearch.py" % p)

# test negatywny: zepsuty diff w kontekscie wykrywany
_, ev = D.simulate(steps, "append")
for e in ev:
    if e.get("meta") == "diff":
        e["text"] = e["text"].replace("@@ -", "@@ -9", 1)
        break
try:
    r = D.reconstruct(ev, "ctxsearch.py")
    check(r != final["ctxsearch.py"], "zepsuty diff nie odtwarza pliku")
except ValueError:
    check(True, "zepsuty diff wykryty (ValueError)")

_, ev = D.simulate(steps, "append+")
check(sum(1 for e in ev if e["kind"] == "run" and e["meta"] == "same") == 4, "append+: 4 identyczne wyniki testow jako stub")
_, ev = D.simulate(steps, "append")
check([e["meta"] for e in ev if e["kind"] == "read"] ==
      ["full", "full", "same", "diff", "same", "diff", "diff", "diff"], "append: sekwencja full/same/diff odczytow")

print("OK: %d asercji, %d niepowodzen" % (passed, failed) if not failed else "BLAD: %d niepowodzen z %d" % (failed, passed + failed))
sys.exit(1 if failed else 0)
