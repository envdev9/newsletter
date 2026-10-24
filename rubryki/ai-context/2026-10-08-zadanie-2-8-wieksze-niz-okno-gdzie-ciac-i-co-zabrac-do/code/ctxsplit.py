#!/usr/bin/env python3
"""ctxsplit - dzielenie dlugiego zadania na okna kontekstu: kiedy ciac i co przekazac (plik handoff).

Dane SYNTETYCZNE i deterministyczne (LCG, bez losowosci). Tokeny = liczby z modelu (nie tokenizer);
w lincie handoffu bajty/4. ZADEN model ani API nie jest wywolywany: to MODEL KOSZTOW kontekstu,
nie pomiar zachowania Claude'a. Zalozenia modelu sa wypisane w ARTICLE.md.

Uzycie:
  python3 -B ctxsplit.py plan                   # zadanie: jednostki, zaleznosci, rozklad odleglosci
  python3 -B ctxsplit.py run [--T 90000]        # strategie ciecia x polityki handoffu
  python3 -B ctxsplit.py sweep                  # koszt w funkcji progu ciecia T
  python3 -B ctxsplit.py base                   # optymalne T w funkcji rozmiaru bazy (system+narzedzia+pamiec)
  python3 -B ctxsplit.py handoff [--after 12]   # renderuje przykladowy HANDOFF.md na stdout
  python3 -B ctxsplit.py lint PLIK [--cap 1500] [--root KATALOG]
"""
import math
import re
import sys
from dataclasses import dataclass, field

BASE_DEFAULT = 10_000      # system + narzedzia + pamiec (stala czesc kazdego okna)
WINDOW_DEFAULT = 200_000   # twardy limit okna (parametr, nie fakt o konkretnym modelu)
H0 = 400                   # staly narzut pliku handoff (naglowki, cel, nastepny krok)
REDERIVE = 0.4             # ile tokenow jednostki kosztuje odtworzenie jej decyzji od zera
CAP_ALL = 2000             # limit rozmiaru "handoffu append-only" (obcina najstarsze)
# Mnozniki ceny prompt cache - ZALOZENIE z pamieci autora (niezweryfikowane): odczyt z cache ~0.1x,
# zapis/nowy token ~1.25x ceny wejscia. Ignorujemy wygasanie cache (TTL) i cene tokenow wyjscia.
READ_MULT = 0.1
WRITE_MULT = 1.25

MODULES = ["Orders", "Billing", "Catalog", "Users", "Auth", "Shipping", "Returns", "Inventory",
           "Pricing", "Promotions", "Reports", "Audit", "Notifications", "Search", "Payments",
           "Tax", "Invoices", "Reviews", "Wishlist", "Cart", "Checkout", "Analytics", "Export", "Admin"]


# ------------------------------------------------------------------ zadanie syntetyczne
@dataclass
class Unit:
    idx: int
    name: str
    deltas: list            # tokeny dokladane do kontekstu w kolejnych turach
    fact_size: int          # tokenow, ktore zajmuje decyzja tej jednostki w handoffie
    deps: set = field(default_factory=set)

    @property
    def tokens(self):
        return sum(self.deltas)


def _lcg(seed):
    x = seed
    while True:
        x = (x * 1103515245 + 12345) % (2 ** 31)
        yield x >> 8


def build_units(n=24):
    """n jednostek pracy (np. migracja n modulow). Kazda ma 4-8 tur po 1500-5999 tok."""
    g = _lcg(42)
    units = []
    for j in range(n):
        turns = 4 + (j * 7) % 5
        deltas = [1500 + next(g) % 4500 for _ in range(turns)]
        deps = set()
        if j > 0:
            deps.add(0)                       # konwencje zapisane w jednostce 0 potrzebne wszystkim
        if j >= 2:
            deps.add(j - 1)                   # poprzednik
        far = (j * 13 + 5) % max(j - 1, 1)
        if j >= 3 and 0 < far < j - 1:
            deps.add(far)                     # zaleznosc daleka
        if j in (12, 17, 22):
            deps.add(5)                       # wspolny mapper typow z jednostki 5
        units.append(Unit(j, MODULES[j % len(MODULES)], deltas, 120 + (j * 53) % 180, deps))
    return units


def tok_text(s):
    return math.ceil(len(s.encode("utf-8")) / 4)


# ------------------------------------------------------------------ polityki handoffu
def pol_none(known, nxt, units):
    return set()


def pol_recent(known, nxt, units, n=3):
    return set(sorted(known)[-n:])


def pol_all(known, nxt, units):
    return set(known)


def pol_all_capped(known, nxt, units):
    out, used = set(), H0
    for i in sorted(known, reverse=True):
        if used + units[i].fact_size > CAP_ALL:
            break
        out.add(i)
        used += units[i].fact_size
    return out


def pol_live(known, nxt, units):
    """Fakty znane w tym oknie, ktorych potrzebuje jakakolwiek jednostka >= nxt (plan deklaruje zaleznosci)."""
    needed = set()
    for u in units[nxt:]:
        needed |= u.deps
    return {i for i in known if i in needed}


POLICIES = {"none": pol_none, "recent3": pol_recent, "all": pol_all,
            "all_capped": pol_all_capped, "live": pol_live}


def handoff_tokens(policy, facts, units):
    if policy == "none":
        return 0
    return H0 + sum(units[i].fact_size for i in facts)


# ------------------------------------------------------------------ symulacja
def simulate(units, trigger, policy, T, base=BASE_DEFAULT, W=WINDOW_DEFAULT, est=None):
    """trigger: never | mid | boundary | predictive.
    never      - tnij dopiero na twardym limicie W (jak czekanie na auto-kompakcje), w srodku jednostki
    mid        - tnij, gdy kolejna tura przekroczylaby T (w srodku jednostki)
    boundary   - tnij na granicy jednostek, gdy kontekst >= T
    predictive - tnij na granicy jednostek, gdy kontekst + szacunek nastepnej jednostki > T
    W (twardy limit) tnie w srodku jednostki zawsze. Cieta tura handoffu kosztuje caly biezacy kontekst.
    Zwraca slownik metryk."""
    if est is None:
        est = sum(u.tokens for u in units) / len(units)
    pol = POLICIES[policy]
    ctx, known = base, set()
    tt = windows = missing = rework = forced = overflow = 0
    max_ctx, handoff_total = ctx, 0
    inflight = 0
    w = 0.0          # koszt wazony cache: prefiks z poprzedniej tury x READ, nowe tokeny x WRITE
    cached = 0       # ile tokenow okna jest juz w cache (0 w swiezym oknie)

    def turn():
        nonlocal w, cached
        w += READ_MULT * cached + WRITE_MULT * (ctx - cached)
        cached = ctx

    def cut(nxt, carried_inflight):
        nonlocal ctx, known, tt, windows, rework, handoff_total, max_ctx, w, cached
        tt += ctx                                  # tura piszaca handoff widzi caly kontekst
        turn()
        windows += 1
        keep = pol(known, nxt, units)
        ht = handoff_tokens(policy, keep, units)
        handoff_total += ht
        w += WRITE_MULT * ht                       # tresc handoffu to nowe (zapisywane) tokeny
        cached = 0                                 # nowe okno = zimny prefiks
        known = set(keep)
        ctx = base + ht + carried_inflight        # praca w toku jest powtarzana od zera
        rework += carried_inflight
        max_ctx = max(max_ctx, ctx)

    def resolve(u):
        nonlocal ctx, missing, rework, max_ctx
        for i in sorted(u.deps - known):
            cost = int(REDERIVE * units[i].tokens)
            ctx += cost
            rework += cost
            missing += 1
            known.add(i)
        max_ctx = max(max_ctx, ctx)

    for u in units:
        inflight = 0
        if u.idx > 0:
            if trigger == "boundary" and ctx >= T:
                cut(u.idx, 0)
            elif trigger == "predictive" and ctx + est > T:
                cut(u.idx, 0)
        resolve(u)
        for d in u.deltas:
            limit = T if trigger == "mid" else W
            if ctx + d > limit and inflight > 0:
                if trigger != "mid":
                    forced += 1
                cut(u.idx, inflight)
                resolve(u)
            ctx += d
            inflight += d
            tt += ctx
            turn()
            max_ctx = max(max_ctx, ctx)
            if ctx > W:
                overflow += 1
        known.add(u.idx)
    return {"windows": windows + 1, "token_tury": tt, "wazony": round(w), "rework": rework, "missing": missing,
            "forced": forced, "overflow_tur": overflow, "max_ctx": max_ctx, "handoff_total": handoff_total}


def unlimited(units, base=BASE_DEFAULT):
    """Odniesienie: jedno okno bez limitu (nierealne, gdy suma przekracza okno)."""
    return simulate(units, "never", "none", 0, base, W=10 ** 12)


STRATEGIES = [
    ("never+recent3 (auto-kompakcja)", "never", "recent3"),
    ("mid+live", "mid", "live"),
    ("boundary+none", "boundary", "none"),
    ("boundary+recent3", "boundary", "recent3"),
    ("boundary+all", "boundary", "all"),
    ("boundary+all_capped", "boundary", "all_capped"),
    ("boundary+live", "boundary", "live"),
    ("predictive+live", "predictive", "live"),
]


# ------------------------------------------------------------------ handoff jako plik
SECTIONS = ["Cel", "Zrobione", "Decyzje obowiazujace", "Nastepny krok", "Pulapki", "Weryfikacja"]


def render_handoff(units, after, window_no, known=None):
    """HANDOFF.md po ukonczeniu jednostek 0..after-1; w 'Decyzjach' tylko fakty zywe (pol_live)."""
    if known is None:
        known = set(range(after))
    live = sorted(pol_live(known, after, units))
    nxt = units[after]
    lines = [f"# HANDOFF - okno {window_no} -> {window_no + 1}", "",
             "## Cel",
             f"Migracja {len(units)} modulow na nowy wzorzec obslugi bledow. Plan: PLAN.md (zaleznosci per modul).", "",
             "## Zrobione",
             f"- U00..U{after - 1:02d} ({after}/{len(units)}), testy zielone na koniec kazdej jednostki.", "",
             "## Decyzje obowiazujace"]
    for i in live:
        u = units[i]
        lines.append(f"- D{i:02d} {u.name}: wynik przeniesiony do wspolnej konwencji; szczegoly w pliku. "
                     f"-> docs/decisions/{i:02d}-{u.name.lower()}.md")
    lines += ["", "## Nastepny krok",
              f"- U{after:02d} {nxt.name}: zaleznosci {', '.join('D%02d' % d for d in sorted(nxt.deps)) or 'brak'}; "
              f"zacznij od odczytu docs/decisions/, nie od przegladu repo.", "",
              "## Pulapki",
              "- Nie rob refaktoru poza zakresem jednostki; nie ruszaj modulow z PLAN.md oznaczonych jako zamrozone.", "",
              "## Weryfikacja",
              "- `dotnet test --filter Category=Migrated` musi byc zielone przed zamknieciem jednostki.", ""]
    return "\n".join(lines)


def lint_handoff(text, cap=1500, root=None):
    """Zwraca liste bledow (pusta = OK). Reguly sa heurystyka dobrana pod format z render_handoff."""
    errs = []
    lines = text.splitlines()
    heads = [l[3:].strip() for l in lines if l.startswith("## ")]
    for s in SECTIONS:
        if s not in heads:
            errs.append(f"brak sekcji '{s}'")
    if heads and [h for h in heads if h in SECTIONS] != [s for s in SECTIONS if s in heads]:
        errs.append("sekcje w zlej kolejnosci")
    t = tok_text(text)
    if t > cap:
        errs.append(f"za duzy: {t} tok. > {cap}")
    for n, l in enumerate(lines, 1):
        if len(l) > 240:
            errs.append(f"linia {n}: {len(l)} znakow (wyglada na zrzut surowego tekstu)")
    in_fence, fence_len = False, 0
    for n, l in enumerate(lines, 1):
        if l.strip().startswith("```"):
            if in_fence and fence_len > 15:
                errs.append(f"linia {n}: blok kodu {fence_len} linii (handoff to wskazniki, nie logi)")
            in_fence, fence_len = not in_fence, 0
        elif in_fence:
            fence_len += 1

    def section(name):
        out, on = [], False
        for l in lines:
            if l.startswith("## "):
                on = l[3:].strip() == name
            elif on and l.strip():
                out.append(l)
        return out

    for l in section("Decyzje obowiazujace"):
        m = re.search(r"->\s*(\S+)\s*$", l)
        if not m:
            errs.append(f"decyzja bez wskaznika '-> plik': {l[:50]}")
        elif root is not None:
            import os
            if not os.path.exists(os.path.join(root, m.group(1))):
                errs.append(f"wskaznik do nieistniejacego pliku: {m.group(1)}")
    nk = [l for l in section("Nastepny krok") if l.lstrip().startswith("-")]
    if len(nk) != 1:
        errs.append(f"'Nastepny krok' ma {len(nk)} punktow, ma byc dokladnie 1")
    if not any("`" in l for l in section("Weryfikacja")):
        errs.append("'Weryfikacja' bez polecenia w backtickach")
    return errs


# ------------------------------------------------------------------ polecenia
def _arg(args, name, default, cast=int):
    return cast(args[args.index(name) + 1]) if name in args else default


def cmd_plan(_):
    us = build_units()
    tot = sum(u.tokens for u in us)
    print(f"jednostek: {len(us)}, suma tokenow pracy: {tot}, srednio {tot // len(us)} / jednostke "
          f"(min {min(u.tokens for u in us)}, max {max(u.tokens for u in us)})")
    print(f"okno {WINDOW_DEFAULT}, baza {BASE_DEFAULT}: praca bez ciec to {tot + BASE_DEFAULT} tok. = "
          f"{(tot + BASE_DEFAULT) / WINDOW_DEFAULT:.2f}x okna")
    dist = {}
    for u in us:
        for d in u.deps:
            dist[u.idx - d] = dist.get(u.idx - d, 0) + 1
    near = sum(v for k, v in dist.items() if k <= 1)
    far = sum(v for k, v in dist.items() if k > 3)
    allv = sum(dist.values())
    print(f"zaleznosci: {allv} (odleglosc <=1: {near}, >3: {far})")
    print("| odleglosc | liczba |")
    print("|---:|---:|")
    for k in sorted(dist):
        print(f"| {k} | {dist[k]} |")


def cmd_run(args):
    T = _arg(args, "--T", 90_000)
    us = build_units()
    ref = unlimited(us)
    print(f"T={T}, okno={WINDOW_DEFAULT}, baza={BASE_DEFAULT}; odniesienie (jedno okno bez limitu): "
          f"{ref['token_tury']} token-tur, koszt wazony {ref['wazony']}, max kontekst {ref['max_ctx']}")
    print("| strategia | okien | token-tury | koszt wazony cache | vs bez limitu (wazony) | rework tok | brakujace fakty | wymuszone ciecia | max kontekst | handoffy tok |")
    print("|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|")
    for name, trig, pol in STRATEGIES:
        r = simulate(us, trig, pol, T)
        print(f"| {name} | {r['windows']} | {r['token_tury']} | {r['wazony']} | {r['wazony'] / ref['wazony']:.2f}x | "
              f"{r['rework']} | {r['missing']} | {r['forced']} | {r['max_ctx']} | {r['handoff_total']} |")


def cmd_sweep(_):
    us = build_units()
    print("koszt w funkcji progu T (baza 10000, polityka live); komorka: okien / token-tury / koszt wazony cache / rework")
    print("najlepsze T wg kosztu WAZONEGO oznaczone *")
    Ts = list(range(30_000, 190_001, 20_000))
    results = {}
    for trig in ("mid", "boundary", "predictive"):
        results[trig] = [simulate(us, trig, "live", T) for T in Ts]
    print("| T | mid | boundary | predictive |")
    print("|---:|---|---|---|")
    best = {t: min(range(len(Ts)), key=lambda i: results[t][i]["wazony"]) for t in results}
    for i, T in enumerate(Ts):
        cells = []
        for trig in ("mid", "boundary", "predictive"):
            r = results[trig][i]
            cells.append(f"{r['windows']} / {r['token_tury']} / {r['wazony']} / {r['rework']}" + (" *" if best[trig] == i else ""))
        print(f"| {T} | " + " | ".join(cells) + " |")
    for trig in results:
        r = results[trig][best[trig]]
        print(f"najlepsze {trig}: T={Ts[best[trig]]}, {r['windows']} okien, koszt wazony {r['wazony']}")


def best_T(us, trig, base, pol="live", metric="wazony"):
    best = None
    for T in range(20_000, 190_001, 5_000):
        r = simulate(us, trig, pol, T, base)
        if best is None or r[metric] < best[1][metric]:
            best = (T, r)
    return best


def cmd_base(_):
    us = build_units()
    print("optymalne T (krok 5000, polityka live, ciecie predictive) w funkcji rozmiaru bazy: wg kosztu wazonego cache vs wg surowych token-tur")
    print("| baza | T (wazony) | okien | koszt wazony | jedno okno bez limitu (wazony) | T (surowe token-tury) | okien |")
    print("|---:|---:|---:|---:|---:|---:|---:|")
    for base in (5_000, 10_000, 30_000, 60_000):
        T, r = best_T(us, "predictive", base)
        T2, r2 = best_T(us, "predictive", base, metric="token_tury")
        print(f"| {base} | {T} | {r['windows']} | {r['wazony']} | {unlimited(us, base)['wazony']} | {T2} | {r2['windows']} |")


def cmd_handoff(args):
    after = _arg(args, "--after", 12)
    us = build_units()
    text = render_handoff(us, after, window_no=after // 6 + 1)
    sys.stdout.write(text)


def cmd_lint(args):
    if not args:
        print(__doc__)
        return 2
    cap = _arg(args, "--cap", 1500)
    root = args[args.index("--root") + 1] if "--root" in args else None
    text = open(args[0], encoding="utf-8").read()
    errs = lint_handoff(text, cap, root)
    print(f"{args[0]}: {tok_text(text)} tok. (bajty/4), limit {cap}")
    for e in errs:
        print("BLAD:", e)
    print("OK" if not errs else f"{len(errs)} bledow")
    return 1 if errs else 0


def main(argv):
    cmds = {"plan": cmd_plan, "run": cmd_run, "sweep": cmd_sweep, "base": cmd_base,
            "handoff": cmd_handoff, "lint": cmd_lint}
    if len(argv) < 2 or argv[1] not in cmds:
        print(__doc__)
        return 2
    return cmds[argv[1]](argv[2:]) or 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
