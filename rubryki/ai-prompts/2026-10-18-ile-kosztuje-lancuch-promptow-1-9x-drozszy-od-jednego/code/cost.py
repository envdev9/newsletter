#!/usr/bin/env python3
"""Model kosztu tokenowego lancucha z #18: ile kosztuje kontrakt, ile oszczedza fail-fast,
kiedy lancuch jest tanszy niz jeden prompt. Python stdlib, bez modelu, bez sieci, bez dotnet.

CO JEST MIERZONE (deterministycznie): dlugosc w znakach kazdego promptu, ktory skrypt
naprawde zbudowal (chain.build_prompt / chain.build_repair) i dlugosc nagran z fixtures/.
CO JEST SZACOWANE: tokeny = ceil(znaki / k), k w {3,4,5}. To NIE jest tokenizer zadnego modelu.
CO JEST ZALOZENIEM: waga tokena wyjsciowego wzgledem wejsciowego (w), odpowiedz naprawcza
o dlugosci poprzedniej odpowiedzi, prawdopodobienstwa sukcesu (tylko jako parametr, nie pomiar).
"""
from __future__ import annotations

import math
import os
import shutil
import sys

import chain

SCENARIOS = ["s0_good", "s1_fenced_json", "s2_halluc_symbol", "s3_scope_creep",
             "s4_test_tamper", "s5_bad_context", "s6_wrong_fix"]
K_DEFAULT = 4          # znakow na token (szacunek)
WEIGHTS = (1, 3, 5)    # cena tokena wyjsciowego / wejsciowego (zalozenie)
BILLING_FILES = ["Billing/Discounts.cs", "Billing/InvoiceCalculator.cs", "Billing/Money.cs"]


def tok(text: str, k: float = K_DEFAULT) -> int:
    return math.ceil(len(text) / k)


class Recorder:
    """Owija ReplayModel i zapamietuje (krok, prompt, odpowiedz) kazdego wywolania."""

    def __init__(self, scenario: str):
        self.inner = chain.ReplayModel(scenario)
        self.calls: list[tuple[int, str, str]] = []

    def __call__(self, step: int, prompt: str) -> str:
        out = self.inner(step, prompt)
        self.calls.append((step, prompt, out))
        return out


def stub_gate(diff, workdir):
    # koszt tokenowy nie zalezy od wyniku bramki; sam fakt jej osiagniecia wystarczy
    return False, "bramka (stub)"


def run(scenario: str, contracts: bool, bug: str, index: dict, wd: str):
    rec = Recorder(scenario)
    res = chain.run_chain(rec, contracts, bug, index, wd, gate=stub_gate)
    return rec, res


def cost(calls, k=K_DEFAULT, w=1.0, extra_in=0, extra_out=0):
    tin = sum(tok(p, k) for _, p, _ in calls) + extra_in
    tout = sum(tok(o, k) for _, _, o in calls) + extra_out
    return tin, tout, tin + w * tout


def repair_cost(rec, res, k=K_DEFAULT, w=1.0):
    """Koszt JEDNEJ rundy naprawczej po odrzuceniu: prompt naprawczy (+ oryginalny prompt kroku,
    bo API jest bezstanowe) i odpowiedz o dlugosci poprzedniej. Zalozenie, nie pomiar."""
    if res.accepted or res.stage in ("bramka", "-"):
        return None
    step, prompt, out = rec.calls[-1]
    rep = chain.build_repair(step, res.errors or ["(brak)"], out)
    tin = tok(rep, k) + tok(prompt, k)
    tout = tok(out, k)
    return tin, tout, tin + w * tout


def composition(bug, index, s1, s2):
    """Z czego sklada sie wejscie kazdego kroku (znaki): szablon / zgloszenie / indeks / poprzedni JSON / zrodla."""
    rows = []
    idx_txt = chain.index_text(index)
    p1 = chain.build_prompt(1, bug, index)
    tpl1 = chain.fill(chain.template("step1_triage.txt"), bug_report="", symbol_index="")
    rows.append(("krok 1", len(p1), len(tpl1), len(bug.strip()), len(idx_txt), 0, 0))
    p2 = chain.build_prompt(2, bug, index, step1=s1)
    files2 = sorted({s["file"] for s in s1["suspects"]})
    src2 = chain.read_sources(files2)
    j1 = len(chain.json.dumps(s1, ensure_ascii=False, indent=1))
    tpl2 = chain.fill(chain.template("step2_plan.txt"), step1_json="", sources="")
    rows.append(("krok 2", len(p2), len(tpl2), 0, 0, j1, len(src2)))
    p3 = chain.build_prompt(3, bug, index, step1=s1, step2=s2)
    files3 = sorted({c["file"] for c in s2["changes"]})
    src3 = chain.read_sources(files3)
    j2 = len(chain.json.dumps(s2, ensure_ascii=False, indent=1))
    tpl3 = chain.fill(chain.template("step3_patch.txt"), step2_json="", sources="")
    rows.append(("krok 3", len(p3), len(tpl3), 0, 0, j2, len(src3)))
    return rows, src2, src3


def main() -> int:
    index = chain.build_index()
    bug = open(os.path.join(chain.HERE, "bug_report.txt"), encoding="utf-8").read()
    wd = chain.make_workdir()
    try:
        data = {}
        for s in SCENARIOS:
            data[s] = (run(s, True, bug, index, wd), run(s, False, bug, index, wd))

        # ---------------------------------------------------------------- 1. sciezka szczesliwa
        rec0, res0 = data["s0_good"][0]
        print(f"== 1. sciezka szczesliwa (s0_good), k={K_DEFAULT} znaki/token, w=1 (tokeny wyjsciowe liczone jak wejsciowe)")
        print(f"{'krok':<8}{'znaki we':>10}{'znaki wy':>10}{'tok we':>9}{'tok wy':>9}")
        for step, p, o in rec0.calls:
            print(f"{step:<8}{len(p):>10}{len(o):>10}{tok(p):>9}{tok(o):>9}")
        tin, tout, _ = cost(rec0.calls)
        print(f"{'razem':<8}{sum(len(p) for _, p, _ in rec0.calls):>10}{sum(len(o) for _, _, o in rec0.calls):>10}{tin:>9}{tout:>9}")

        # ---------------------------------------------------------------- 2. z czego sklada sie wejscie
        import json
        s1 = json.loads(rec0.calls[0][2])
        s2 = json.loads(rec0.calls[1][2])
        rows, src2, src3 = composition(bug, index, s1, s2)
        print("\n== 2. z czego sklada sie wejscie (znaki)")
        print(f"{'krok':<8}{'razem':>7}{'szablon':>9}{'zgloszenie':>12}{'indeks':>8}{'poprz.JSON':>12}{'zrodla':>8}")
        for r in rows:
            print(f"{r[0]:<8}{r[1]:>7}{r[2]:>9}{r[3]:>12}{r[4]:>8}{r[5]:>12}{r[6]:>8}")
        total_in = sum(r[1] for r in rows)
        src_total = sum(r[6] for r in rows)
        same = src2 == src3
        print(f"zrodla w krokach 2 i 3 sa identyczne: {same}; zrodla = {src_total}/{total_in} znakow wejscia ({100*src_total/total_in:.0f}%), "
              f"z czego powtorzone w kroku 3: {len(src3)} znakow")

        # ---------------------------------------------------------------- 3. jeden prompt, ten sam material
        all_src = chain.read_sources(BILLING_FILES)
        mega_prompt = chain.template("mega_bad.txt").strip() + "\n\nZGLOSZENIE:\n" + bug.strip() + "\n\n" + all_src
        mega_out = rec0.calls[2][2]
        print("\n== 3. jeden prompt (mega_bad + zgloszenie + 3 pliki Billing) -> ten sam diff")
        print(f"wejscie {len(mega_prompt)} znakow ({tok(mega_prompt)} tok), wyjscie {len(mega_out)} znakow ({tok(mega_out)} tok)")
        print("  (dolna granica: realna odpowiedz modelu zwykle zawiera tez prose/uzasadnienie - nie liczone)")
        print(f"{'k':>3}{'w':>4}{'lancuch':>10}{'jeden':>9}{'stosunek':>10}")
        ratios = {}
        for k in (3, 4, 5):
            for w in WEIGHTS:
                c_chain = cost(rec0.calls, k, w)[2]
                c_mega = tok(mega_prompt, k) + w * tok(mega_out, k)
                ratios[(k, w)] = c_chain / c_mega
                print(f"{k:>3}{w:>4}{c_chain:>10.0f}{c_mega:>9.0f}{c_chain / c_mega:>9.2f}x")

        # ---------------------------------------------------------------- 4. fail-fast na 6 zlych scenariuszach
        print("\n== 4. tokeny wydane na kazdy scenariusz (k=4, w=1): kontrakty vs baseline (bez kontraktow)")
        print(f"{'scenariusz':<18}{'kontrakty':<18}{'tok':>6}  {'baseline':<18}{'tok':>6}  +naprawa(1 runda, kontrakty)")
        bad_c = bad_b = 0
        for s in SCENARIOS:
            (rc, resc), (rb, resb) = data[s]
            cc = cost(rc.calls)[2]
            cb = cost(rb.calls)[2]
            stage_c = "doszedl do bramki" if resc.stage in ("bramka", "-") else f"odrzucony: {resc.stage}"
            stage_b = "doszedl do bramki" if resb.stage in ("bramka", "-") else f"odrzucony: {resb.stage}"
            rp = repair_cost(rc, resc)
            rps = f"+{rp[2]:.0f}" if rp else "-"
            print(f"{s:<18}{stage_c:<18}{cc:>6.0f}  {stage_b:<18}{cb:>6.0f}  {rps}")
            if s != "s0_good":
                bad_c += cc
                bad_b += cb
        print(f"suma na 6 zlych/podejrzanych scenariuszach: kontrakty {bad_c:.0f} tok, baseline {bad_b:.0f} tok")

        # ---------------------------------------------------------------- 5. break-even
        print("\n== 5. kiedy lancuch jest tanszy od jednego promptu (oczekiwany koszt na zaakceptowany wynik)")
        print("   lancuch z naprawa lokalna kroku: koszt ~ C_lancuch / q  (q = szansa, ze krok przechodzi kontrakt)")
        print("   jeden prompt:                    koszt ~ C_jeden / Q    (Q = szansa, ze jedna odpowiedz jest dobra)")
        print("   lancuch tanszy <=> Q < q * C_jeden / C_lancuch.  q i Q to PARAMETRY, nie pomiar.")
        print(f"{'w':>3}{'stosunek':>10}" + "".join(f"{'q=' + str(q):>10}" for q in (0.95, 0.9, 0.8, 0.7)))
        for w in WEIGHTS:
            r = ratios[(K_DEFAULT, w)]
            print(f"{w:>3}{r:>9.2f}x" + "".join(f"{q / r:>10.2f}" for q in (0.95, 0.9, 0.8, 0.7)))
        print("   (komorka = prog Q: jesli jeden prompt trafia czesciej niz prog, jest tanszy niz lancuch)")

        # ---------------------------------------------------------------- 6. skalowanie rozmiaru kodu
        f = len(src2) / len(all_src)
        chain_fixed = total_in - src_total + sum(len(o) for _, _, o in rec0.calls)
        mega_fixed = len(mega_prompt) - len(all_src) + len(mega_out)
        print(f"\n== 6. ekstrapolacja: co jesli kod jest wiekszy (w=1, k=4). Zmierzony udzial plikow podejrzanych f = {f:.2f}")
        print("   model: lancuch = stale + 2 * f * S   (zrodla podejrzanych w kroku 2 i 3),  jeden = stale + S   (cale S)")
        print("   NIE modelowane: indeks symboli rosnie z repo (psuje przewage lancucha), a agent z narzedziami nie czyta calego repo.")
        print(f"{'S [znaki]':>11}{'lancuch tok':>13}{'jeden tok':>11}{'stosunek':>10}")
        for S in (len(all_src), 5_000, 20_000, 100_000, 1_000_000):
            c = math.ceil((chain_fixed + 2 * f * S) / K_DEFAULT)
            m = math.ceil((mega_fixed + S) / K_DEFAULT)
            print(f"{S:>11}{c:>13}{m:>11}{c / m:>9.2f}x")
        print(f"   granica dla S -> nieskonczonosc: 2f = {2 * f:.2f}x")
    finally:
        shutil.rmtree(wd, ignore_errors=True)
    return 0


if __name__ == "__main__":
    sys.exit(main())
