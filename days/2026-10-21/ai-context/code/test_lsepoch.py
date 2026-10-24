#!/usr/bin/env python3
"""Testy lsepoch.py: parser, okno, fuzz (losowe sesje z losowa kompakcja), test negatywny, kolejnosc ls -t/-S.
Uruchom: python3 -B test_lsepoch.py   (kilkadziesiat sekund; sesje na prawdziwym `ls` w /tmp)"""
import os
import random
import sys

sys.dont_write_bytecode = True
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import lsepoch as L

N = {"ok": 0, "fail": 0}


def check(cond, msg):
    if cond:
        N["ok"] += 1
    else:
        N["fail"] += 1
        print("FAIL:", msg)


# --- parser / klucze
check(L.key_of("lrwxrwxrwx 1 11 2026-10-01 10:00 latest -> src/m00") == "latest", "klucz symlinku")
check(L.key_of("-rw-r--r-- 1 50 2026-10-01 10:00 a b.md") == "a b.md", "klucz ze spacja")
check(L.key_of("total 12") == L.TOTAL, "klucz total")
s = L.parse("proj:\ntotal 4\n-rw-r--r-- 1 5 2026-10-01 10:00 a\ndrwxr-xr-x 2 4096 2026-10-01 10:00 d\n\nproj/d:\ntotal 0",
            "proj")
check(set(s) == {"proj", "proj/d"} and set(s["proj"]) == {L.TOTAL, "a", "d"}, "parse -R")

# --- prune: sierota i kaskada
v = {"p": {"a": "drwx a"}, "p/a": {"b": "drwx b"}, "p/a/b": {}, "p/x": {}}
L.prune(v)
check(set(v) == {"p", "p/a", "p/a/b"}, "prune usuwa katalog nieobecny u rodzica")
v["p"].pop("a")
L.prune(v)
check(set(v) == {"p"}, "prune kaskadowo usuwa potomkow")

# --- okno: delta bez bazy jest ignorowana, nie zatruwa
w = L.Window()
w.apply("*", "R", "p", "[ls -R p: delta wzgledem tury 1; sekcji: 1]\n@p/q\n~-rw-r--r-- 1 5 2026-10-01 10:00 f", 2)
check(w.views["*"] == {}, "delta bez bazy nic nie tworzy")

# --- sesja skryptowana
scr = L.script()
for pol in L.POLICIES:
    r = L.run_session(pol, scr)
    check(not r["bad"], "%s bez kompakcji: bledne tury %s" % (pol, r["bad"]))
none = L.run_session("none", scr)
proj = L.run_session("proj", scr)
check(proj["tokens"] * 9 < none["tokens"] < proj["tokens"] * 10, "proj ~9.5x tanszy (zmierzone 9.49x)")
check(L.run_session("sdelta", scr)["tokens"] == L.run_session("gdelta", scr)["tokens"],
      "gdelta == sdelta na tej sesji (wynik zerowy, patrz artykul)")

# --- test negatywny: bez swiadomosci kompakcji MUSI sie mylic
for pol in ("gdelta", "sdelta", "proj"):
    r = L.run_session(pol, scr, comp=10, tail=0)
    check(len(r["bad"]) > 0, "%s po kompakcji MUSI sie mylic" % pol)
for pol in ("chain", "carry"):
    for tail in (0, 4):
        r = L.run_session(pol, scr, comp=10, tail=tail)
        check(not r["bad"], "%s po kompakcji (ogon %d) bez bledow" % (pol, tail))

# --- delta/stub nigdy nie sa wieksze niz pelny wynik
sb = L.Sandbox()
tool = L.Tool("proj")
for turn, (ops, (kind, path)) in enumerate(scr, 1):
    sb.do_turn(ops, turn)
    full = L.ls_cmd(kind, path, sb.base)
    truth = L.parse(full, path)
    form, text = tool.emit(kind, path, truth, full, turn)
    tool.record(kind, path, form, text, truth, turn)
    check(form == "full" or L.tok(text) < L.tok(full), "tura %d: wynik (%s) nie wiekszy niz pelny" % (turn, form))
sb.close()

# --- fuzz: losowe operacje (spacje w nazwach, katalogi, symlinki), losowe zapytania, losowa kompakcja
TARGETS = [("R", "proj"), ("R", "proj"), ("R", "proj/src"), ("L", "proj"), ("L", "proj/tests"), ("L", "proj/src/m00"),
           ("R", "proj/src/m00"), ("R", "proj/docs")]
rng = random.Random(2026)
sessions = cmp_ = 0
for i in range(25):
    seed = rng.randint(0, 10**6)
    r2 = random.Random(seed)
    fz = [([("rand", r2.randint(0, 3))], r2.choice(TARGETS)) for _ in range(14)]
    comp = r2.choice([None, r2.randint(2, 14)])
    tail = r2.choice([0, 2, 5])
    for pol in L.POLICIES:
        if comp is not None and pol not in ("none", "chain", "carry"):
            continue
        r = L.run_session(pol, fz, comp, tail, mods=3, files=4, seed=seed)
        sessions += 1
        cmp_ += len(fz)
        check(not r["bad"], "fuzz seed=%d pol=%s comp=%s tail=%d bledne tury %s" % (seed, pol, comp, tail, r["bad"]))
print("fuzz: %d sesji, %d porownan listing==okno" % (sessions, cmp_))

# --- kolejnosc
out = L.order_test()
check(out[("long-iso", "-t")][0] == 0, "ls -t z long-iso: kolejnosc NIE do odtworzenia (w tym zestawie 0/40)")
check(out[("full-iso", "-t")][0] == 40, "ls -t z full-iso do odtworzenia")
check(out[("long-iso", "-S")][0] == 40 and out[("full-iso", "-S")][0] == 40, "ls -S do odtworzenia (remisy po nazwie)")

print("%s: %d asercji, %d niepowodzen" % ("OK" if not N["fail"] else "FAIL", N["ok"], N["fail"]))
sys.exit(1 if N["fail"] else 0)
