#!/usr/bin/env python3
"""Testy lsdelta.py (stdlib, bez frameworka). Uruchom: python3 -B test_lsdelta.py"""
import os
import random
import shutil
import sys
import tempfile

import lsdelta as L

PASS, FAIL = 0, 0


def check(cond, msg):
    global PASS, FAIL
    if cond:
        PASS += 1
    else:
        FAIL += 1
        print("FAIL:", msg)


def main():
    # --- podstawy
    check(L.tok("abcd") == 1 and L.tok("abcde") == 2 and L.tok("") == 0, "tok = bajty/4")
    check(L.name_of("total 12") == L.TOTAL, "total")
    check(L.name_of("-rw-r--r-- 1 120 2026-10-01 10:00 Mod 000 notes.md") == "Mod 000 notes.md", "nazwa ze spacjami")
    check(L.name_of("-rw-r--r-- 1 5 2026-10-01 10:00 a.cs") == "a.cs", "nazwa prosta")

    # --- sesja bazowa: bezpieczne polityki odtwarzaja listing; evented nie
    res = L.summarize(150)
    for p in ("none", "same", "setdiff", "namekey", "state"):
        check(res[p]["ls_ok"] == res[p]["ls_n"], f"{p}: wszystkie listingi odtwarzalne z okna")
    check(res["evented"]["ls_ok"] < res["evented"]["ls_n"], "NEGATYWNY: evented MUSI zawiesc po zewnetrznym buildzie")
    check(res["none"]["tokens"] > res["same"]["tokens"] > res["setdiff"]["tokens"] >= res["namekey"]["tokens"] >= res["state"]["tokens"],
          "kolejnosc tokenow none > same > setdiff >= namekey >= state")
    check(res["same"]["token_turns"] <= res["none"]["token_turns"], "same nie drozszy")
    check(res["state"]["weighted"] < res["none"]["weighted"], "state tanszy wazony")
    check(res["none"]["stub"] == res["none"]["delta"] == 0, "none: tylko pelne wyniki")

    # --- demo: edycja o tym samym rozmiarze i mtime niewidoczna w ls -l
    ev, meta = L.play("none", 150)
    s = meta["edit_same"]
    check(s["hash_before"] != s["hash_after"], "edit_same zmienia tresc")
    b = [l for l in ev[13]["text"].split("\n") if l.endswith(" Mod007.cs")]
    a = [l for l in ev[15]["text"].split("\n") if l.endswith(" Mod007.cs")]
    check(len(a) == 1 and a == b, "ls -l nie widzi edycji o tym samym rozmiarze i mtime")

    # --- ewolucja skali: im wiekszy katalog, tym wiekszy zysk
    gains = []
    for n in (20, 150, 500):
        a1, _ = L.play("none", n)
        b1, _ = L.play("state", n)
        gains.append(L.costs(a1)["tokens"] / L.costs(b1)["tokens"])
    check(gains[0] < gains[1] < gains[2], f"zysk rosnie z rozmiarem katalogu: {gains}")

    # --- fuzz: losowe mutacje katalogu, losowe warianty ls, 4 bezpieczne polityki
    rng = random.Random(20261020)
    sessions, checks = 0, 0
    for seed in range(60):
        rng = random.Random(seed)
        root = tempfile.mkdtemp(prefix="lsdelta-fuzz-")
        try:
            d = "d"
            os.makedirs(os.path.join(root, d))
            existing = set()
            wins = {p: L.Window(p) for p in ("same", "setdiff", "namekey", "state")}
            counter = 0
            for step in range(40):
                act = rng.choice(["create", "create", "delete", "edit", "ls", "ls", "ls"])
                if act == "create":
                    counter += 1
                    nm = rng.choice(["f%d.txt", "plik %d.cs", "zazolc_%d.md", ".h%d"]) % counter
                    L.write(os.path.join(root, d, nm), "x" * rng.randint(0, 3000), L.T0 + 60 * rng.randint(0, 400))
                    existing.add(nm)
                elif act == "delete" and existing:
                    nm = rng.choice(sorted(existing))
                    os.remove(os.path.join(root, d, nm))
                    existing.discard(nm)
                elif act == "edit" and existing:
                    nm = rng.choice(sorted(existing))
                    L.write(os.path.join(root, d, nm), "y" * rng.randint(0, 3000), L.T0 + 60 * rng.randint(0, 400))
                else:
                    kind = rng.choice(["1A", "lA"])
                    truth = L.run_ls(kind, d, root)
                    for p, w in wins.items():
                        text = L.respond(p, w, kind, d, truth, step)
                        w.apply(kind, d, text, step)
                        got = w.answer(kind, d)
                        checks += 1
                        check(got == sorted(truth), f"fuzz seed={seed} step={step} polityka={p} kind={kind}")
            sessions += 1
        finally:
            shutil.rmtree(root, ignore_errors=True)
    print(f"fuzz: {sessions} sesji, {checks} porownan listing==okno")

    print(f"{'OK' if FAIL == 0 else 'FAIL'}: {PASS} asercji, {FAIL} niepowodzen")
    return 0 if FAIL == 0 else 1


if __name__ == "__main__":
    sys.exit(main())
