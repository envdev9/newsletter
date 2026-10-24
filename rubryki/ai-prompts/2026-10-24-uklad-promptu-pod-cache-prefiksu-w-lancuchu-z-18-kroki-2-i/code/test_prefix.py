#!/usr/bin/env python3
"""Niezmienniki dla prefix.py + test negatywny (celowo zepsuty uklad musi zostac wykryty).
Uruchom: python3 -B test_prefix.py   (exit 0 = wszystko OK)"""
from __future__ import annotations

import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import prefix as p  # noqa: E402


def check_layout(ps: list[str], need_shared_2_3: int) -> list[str]:
    """Reguly 'dobrego ukladu': kroki 2 i 3 maja wspolny prefiks >= need, a rozjazd nastepuje
    dopiero w czesci zmiennej (ROLA), nie w zrodlach."""
    errs = []
    k = p.lcp(ps[1], ps[2])
    if k < need_shared_2_3:
        errs.append(f"wspolny prefiks krokow 2 i 3 = {k} < {need_shared_2_3}")
    rest = ps[1][k:k + 12]
    if not rest.startswith("planista"):
        errs.append(f"rozjazd nie na granicy ROLI, tylko w: {rest!r}")
    return errs


def main() -> int:
    _, _, outs = p.load_steps()
    fails: list[str] = []

    def ok(cond: bool, msg: str) -> None:
        if not cond:
            fails.append(msg)

    a, b, c = p.layout_a(), p.layout_b(), p.layout_c()
    # budowa
    ok(all(isinstance(x, str) and x for x in a + b + c), "puste prompty")
    ok("{{" not in "".join(a + b + c), "nie wypelniony placeholder {{...}}")
    # B: wspolny prefiks wszystkich trzech = reguly + caly modul
    pre = p.tpl("rules.txt") + p.fill(p.tpl("src_all.txt"), symbol_index=p.index_text(),
                                      sources=p.sources(p.FILES_ALL))
    ok(all(x.startswith(pre) for x in b), "B: prompt nie zaczyna sie od wspolnego prefiksu")
    # A: brak wspolnego prefiksu (poza 'ROLA: ')
    ok(p.lcp(a[1], a[2]) <= 6, f"A: lcp(2,3) = {p.lcp(a[1], a[2])} > 6")
    # C: kroki 2 i 3 dziela reguly + zrodla (>= ich dlugosc), krok 1 dzieli tylko reguly
    shared = p.tpl("rules.txt") + p.fill(p.tpl("src_suspects.txt"), sources=p.sources(["Billing/Money.cs"]))
    ok(c[1].startswith(shared) and c[2].startswith(shared), "C: kroki 2,3 nie zaczynaja sie od reguly+zrodel")
    ok(p.lcp(c[0], c[1]) < len(shared), "C: krok 1 nie powinien dzielic zrodel z krokiem 2")
    ok(not check_layout(c, len(shared)), f"C: check_layout: {check_layout(c, len(shared))}")
    # model kosztu
    for ps in (a, b, c):
        ok(abs(p.sim(ps, outs, 1.0, 1.0, 0) - sum(len(x) / p.K for x in ps) - sum(len(o) / p.K for o in outs)) < 1e-6,
           "sim(r=1,g=1) != suma dlugosci")
        ok(p.sim(ps, outs, 0.1, 1.0, 0) <= p.sim(ps, outs, 1.0, 1.0, 0) + 1e-9, "cache (g=1) nie moze byc drozszy")
    ok(p.sim(c, outs, 0.1, 1.25, 1024) == p.sim(c, outs, 1.0, 1.0, 0), "prefiks < m tok. nie moze dawac efektu")
    big_a, big_c = p.layout_a(100), p.layout_c(100)
    ok(p.sim(big_c, outs, 0.1, 1.25, 1024) < p.sim(big_a, outs, 1.0, 1.0, 0), "C x100 z cache nie jest tanszy od A")
    # kolejnosc rundy naprawczej
    rep = p.fill(p.tpl("repair.txt"), step="2", errors="- e", previous="x", attempt="1", max_attempts="2")
    ok(p.lcp(c[1], c[1] + "\n\n" + rep) == len(c[1]), "naprawa po prompcie nie zachowuje prefiksu")
    ok(p.lcp(c[1], rep + "\n\n" + c[1]) == 0, "naprawa przed promptem powinna zerowac prefiks")

    # ---- test negatywny: zepsute uklady MUSZA zostac wykryte przez check_layout
    need = len(shared)
    for name, bad in (("naglowek Krok n na poczatku", p.layout_c(header="Krok {n}: ")),
                      ("JSON przed zrodlami", p.layout_c(json_first=True)),
                      ("uklad A", a)):
        errs = check_layout(bad, need)
        ok(bool(errs), f"NEGATYWNY: '{name}' nie zostal wykryty jako zepsuty")
        print(f"  negatywny '{name}': wykryty ({len(errs)} naruszen)" if errs else f"  negatywny '{name}': NIEWYKRYTY")

    if fails:
        for f in fails:
            print("FAIL:", f)
        return 1
    print("OK: niezmienniki spelnione, 3/3 zepsute uklady wykryte")
    return 0


if __name__ == "__main__":
    sys.exit(main())
