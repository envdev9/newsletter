#!/usr/bin/env python3
"""Uklad promptow lancucha pod cache prefiksu: ile wspolnego prefiksu maja kolejne wywolania,
ile to kosztuje w modelu cache'a i co ten prefiks psuje. Python stdlib, bez modelu, bez sieci.

MIERZONE (deterministycznie): dlugosc wspolnego prefiksu (w znakach) miedzy promptami, ktore
skrypt naprawde zbudowal z szablonow z prompts/ i nagran z recordings/.
SZACOWANE: tokeny = znaki / K (K=4). To NIE jest tokenizer zadnego modelu.
ZALOZENIA (parametry, NIE zweryfikowane z cennikiem zadnego dostawcy):
  r = mnoznik ceny odczytu z cache'a, g = mnoznik ceny zapisu do cache'a,
  m = minimalna dlugosc prefiksu w tokenach, ponizej ktorej cache nie dziala.
Model cache'a: cache trafia tylko, gdy prompt zaczyna sie BAJT W BAJT tym samym tekstem co
wczesniejszy prompt; punkt zapisu stoi idealnie na granicy wspolnego prefiksu.
"""
from __future__ import annotations

import json
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
K = 4.0
FILES_ALL = ["Billing/Discounts.cs", "Billing/InvoiceCalculator.cs", "Billing/Money.cs"]


def read(rel: str) -> str:
    with open(os.path.join(HERE, rel), encoding="utf-8") as fh:
        return fh.read()


def fill(tpl: str, **kw: str) -> str:
    for k, v in kw.items():
        tpl = tpl.replace("{{" + k + "}}", v)
    return tpl


def tpl(name: str) -> str:
    return read(os.path.join("prompts", name))


def sources(files: list[str], scale: int = 1) -> str:
    """Tresc plikow; scale>1 = balast: ten sam tekst powielony (kopia i), zeby sprawdzic wiekszy kod."""
    parts = []
    for f in files:
        body = read(f).rstrip()
        for i in range(scale):
            tag = f if i == 0 else f"{f} (kopia {i})"
            parts.append(f"=== {tag} ===\n{body}\n")
    return "\n".join(parts)


def index_text() -> str:
    # indeks symboli wpisany jawnie (jak z regexow w #18) - tu liczy sie tekst, nie sposob budowy
    return ("Billing/Discounts.cs: Discounts, Discounts.IsEligible\n"
            "Billing/InvoiceCalculator.cs: InvoiceCalculator, InvoiceCalculator.LineTotal, "
            "InvoiceCalculator.Total, InvoiceLine\n"
            "Billing/Money.cs: Money, Money.Percent, Money.Round")


def dump(obj: dict) -> str:
    return json.dumps(obj, ensure_ascii=False, indent=1)


def load_steps() -> tuple[dict, dict, list[str]]:
    s1 = json.loads(read("recordings/step1.txt"))
    s2 = json.loads(read("recordings/step2.txt"))
    outs = [read(f"recordings/step{i}.txt") for i in (1, 2, 3)]
    return s1, s2, outs


# ------------------------------------------------------------------ uklady
def layout_a(scale: int = 1, s1: dict | None = None, s2: dict | None = None) -> list[str]:
    """#18: kazdy krok ma wlasny szablon od pierwszego znaku; zrodla tylko plikow z planu/triazu."""
    s1, s2_, _ = load_steps()
    s2 = s2 or s2_
    bug = read("bug_report.txt").strip()
    f2 = sorted({s["file"] for s in s1["suspects"]})
    f3 = sorted({c["file"] for c in s2["changes"]})
    return [fill(tpl("a1.txt"), bug_report=bug, symbol_index=index_text()),
            fill(tpl("a2.txt"), step1_json=dump(s1), sources=sources(f2, scale)),
            fill(tpl("a3.txt"), step2_json=dump(s2), sources=sources(f3, scale))]


def layout_b(scale: int = 1) -> list[str]:
    """Wspolny prefiks: reguly + indeks + CALY modul; rola, JSON i zgloszenie na koncu."""
    s1, s2, _ = load_steps()
    bug = read("bug_report.txt").strip()
    pre = tpl("rules.txt") + fill(tpl("src_all.txt"), symbol_index=index_text(), sources=sources(FILES_ALL, scale))
    return [pre + fill(tpl("s1.txt"), bug_report=bug, symbol_index="(w indeksie powyzej)"),
            pre + fill(tpl("s2.txt"), step1_json=dump(s1)),
            pre + fill(tpl("s3.txt"), step2_json=dump(s2))]


def layout_c(scale: int = 1, header: str = "", json_first: bool = False,
             step3_from_plan: bool = False, s1: dict | None = None, s2: dict | None = None) -> list[str]:
    """Reguly na poczatku; kroki 2 i 3 dziela blok zrodel PODEJRZANYCH Z TRIAZU (nie z planu);
    zmienne (rola, JSON, zgloszenie) na koncu. Parametry = celowe psucie (mutanty)."""
    s1_, s2_, _ = load_steps()
    s1, s2 = s1 or s1_, s2 or s2_
    bug = read("bug_report.txt").strip()
    f_susp = sorted({s["file"] for s in s1["suspects"]})
    f_plan = sorted({c["file"] for c in s2["changes"]})
    src2 = fill(tpl("src_suspects.txt"), sources=sources(f_susp, scale))
    src3 = fill(tpl("src_suspects.txt"), sources=sources(f_plan if step3_from_plan else f_susp, scale))
    rules = tpl("rules.txt")
    t1 = fill(tpl("s1.txt"), bug_report=bug, symbol_index=index_text())
    t2 = fill(tpl("s2.txt"), step1_json=dump(s1))
    t3 = fill(tpl("s3.txt"), step2_json=dump(s2))
    if json_first:
        calls = [rules + t1, rules + t2 + "\n" + src2, rules + t3 + "\n" + src3]
    else:
        calls = [rules + t1, rules + src2 + t2, rules + src3 + t3]
    return [f"{header.format(n=i + 1)}{c}" for i, c in enumerate(calls)]


# ------------------------------------------------------------------ pomiar
def lcp(a: str, b: str) -> int:
    n = min(len(a), len(b))
    i = 0
    while i < n and a[i] == b[i]:
        i += 1
    return i


def sim(prompts: list[str], outs: list[str], r: float, g: float, m: int, w: float = 1.0) -> float:
    """Koszt lancucha w 'tokenach wejsciowych': nieskeszowane wejscie=1, odczyt=r, zapis=g, wyjscie=w."""
    total = 0.0
    for i, p in enumerate(prompts):
        t = len(p) / K
        read_c = max([lcp(p, prompts[j]) for j in range(i)] or [0]) / K
        later = max([lcp(p, prompts[j]) for j in range(i + 1, len(prompts))] or [0]) / K
        if read_c < m:
            read_c = 0.0
        write_c = max(0.0, later - read_c) if later >= m else 0.0
        total += (t - read_c - write_c) + g * write_c + r * read_c
        total += w * len(outs[i]) / K
    return total


def section_prefix() -> None:
    print("== 1. wspolny prefiks kolejnych wywolan (znaki, bajt w bajt), skala kodu x1")
    print(f"{'uklad':<26}{'dl.1':>6}{'dl.2':>6}{'dl.3':>6}{'lcp(1,2)':>10}{'lcp(2,3)':>10}{'lcp(1,3)':>10}")
    for name, ps in (("A  (#18, szablon od zera)", layout_a()), ("B  (caly modul w prefiksie)", layout_b()),
                     ("C  (reguly + zrodla triazu)", layout_c())):
        print(f"{name:<26}{len(ps[0]):>6}{len(ps[1]):>6}{len(ps[2]):>6}"
              f"{lcp(ps[0], ps[1]):>10}{lcp(ps[1], ps[2]):>10}{lcp(ps[0], ps[2]):>10}")
    a = layout_a()
    c = layout_c()
    print(f"   A: kroki 2 i 3 rozjezdzaja sie na znaku {lcp(a[1], a[2])}: "
          f"{a[1][lcp(a[1], a[2]):][:28]!r} vs {a[2][lcp(a[1], a[2]):][:28]!r}")
    k = lcp(c[1], c[2])
    print(f"   C: kroki 2 i 3 rozjezdzaja sie na znaku {k} (z {len(c[1])}): "
          f"{c[1][k:][:28]!r} vs {c[2][k:][:28]!r}")


def section_cost_small(outs: list[str]) -> None:
    print("\n== 2. koszt lancucha na tym (malym) kodzie: r=0.1, g=1.25 (ZALOZENIA), jednostka = 1 token wejsciowy")
    print(f"{'uklad':<30}{'bez cache':>11}{'cache m=0':>11}{'cache m=1024':>14}")
    base = None
    for name, ps in (("A", layout_a()), ("B", layout_b()), ("C", layout_c())):
        nc = sim(ps, outs, 1.0, 1.0, 0)
        c0 = sim(ps, outs, 0.1, 1.25, 0)
        c1 = sim(ps, outs, 0.1, 1.25, 1024)
        base = base or nc
        print(f"{name:<30}{nc:>11.0f}{c0:>11.0f}{c1:>14.0f}")
    print("   m=0: gdyby cache dzialal dla dowolnie krotkiego prefiksu; m=1024: prefiksy ponizej 1024 tok. nie sa keszowane")


def section_scale(outs: list[str], r: float, g: float, m: int) -> None:
    print(f"\n== 3. rosnacy kod (balast = powielone zrodla), r={r}, g={g}, m={m}; koszt wzgledem A bez cache")
    print(f"{'skala':>6}{'zrodla all':>11}{'A':>9}{'B bez c.':>10}{'B cache':>9}{'C bez c.':>10}{'C cache':>9}"
          f"{'B/A':>7}{'C/A':>7}")
    for sc in (1, 5, 8, 10, 12, 20, 100, 400):
        a, b, c = layout_a(sc), layout_b(sc), layout_c(sc)
        ca = sim(a, outs, 1.0, 1.0, 0)
        cb0, cb = sim(b, outs, 1.0, 1.0, 0), sim(b, outs, r, g, m)
        cc0, cc = sim(c, outs, 1.0, 1.0, 0), sim(c, outs, r, g, m)
        print(f"{sc:>6}{len(sources(FILES_ALL, sc)):>11}{ca:>9.0f}{cb0:>10.0f}{cb:>9.0f}{cc0:>10.0f}{cc:>9.0f}"
              f"{cb / ca:>6.2f}x{cc / ca:>6.2f}x")


def section_sens(outs: list[str], sc: int, m: int) -> None:
    a, b, c = layout_a(sc), layout_b(sc), layout_c(sc)
    ca = sim(a, outs, 1.0, 1.0, 0)
    print(f"\n== 4. wrazliwosc na r i g (skala x{sc}, m={m}); komorka = koszt wzgledem A bez cache (B/A | C/A)")
    print(f"{'r':>6}" + "".join(f"{'g=' + str(g):>16}" for g in (1.0, 1.25, 2.0)))
    for r in (0.1, 0.25, 0.5, 1.0):
        row = f"{r:>6}"
        for g in (1.0, 1.25, 2.0):
            row += f"{sim(b, outs, r, g, m) / ca:>7.2f}|{sim(c, outs, r, g, m) / ca:<6.2f}  "
        print(row)


def section_breakers() -> None:
    print("\n== 5. co psuje prefiks (uklad C, skala x1): lcp(2,3) w znakach")
    base = layout_c()
    print(f"   {'baza (C)':<54}{lcp(base[1], base[2]):>6}")
    s1m = {"symptom": "x", "suspects": [{"symbol": "Money.Round", "file": "Billing/Money.cs"},
                                       {"symbol": "InvoiceCalculator.Total", "file": "Billing/InvoiceCalculator.cs"}],
           "unknowns": []}
    cases = [("naglowek 'Krok n:' na poczatku kazdego promptu", layout_c(header="Krok {n}: ")),
             ("JSON z poprzedniego kroku PRZED zrodlami", layout_c(json_first=True)),
             ("zrodla kroku 3 z PLANU (1 plik), zrodla kroku 2 z triazu (2 pliki)",
              layout_c(step3_from_plan=True, s1=s1m)),
             ("kontrola: te same 2 pliki z triazu w obu krokach", layout_c(s1=s1m))]
    for name, ps in cases:
        print(f"   {name:<54}{lcp(ps[1], ps[2]):>6}")
    # naprawa: kolejnosc [oryginalny prompt][odpowiedz+reguly naprawcze] vs odwrotnie
    ps = layout_c()
    rep = fill(tpl("repair.txt"), step="2", errors="- C11 plik poza zakresem", previous=read("recordings/step2.txt").strip(),
               attempt="1", max_attempts="2")
    good = ps[1] + "\n\n" + rep
    bad = rep + "\n\n" + ps[1]
    print(f"\n== 6. runda naprawcza kroku 2: prompt kroku = {len(ps[1])} znakow, tekst naprawczy = {len(rep)} znakow")
    print(f"   [prompt kroku][naprawa]: wspolny prefiks z oryginalnym promptem = {lcp(ps[1], good)} z {len(ps[1])}")
    print(f"   [naprawa][prompt kroku]: wspolny prefiks z oryginalnym promptem = {lcp(ps[1], bad)} z {len(ps[1])}")


def main() -> int:
    _, _, outs = load_steps()
    section_prefix()
    section_cost_small(outs)
    section_scale(outs, 0.1, 1.25, 1024)
    section_sens(outs, 20, 1024)
    section_breakers()
    return 0


if __name__ == "__main__":
    sys.exit(main())
