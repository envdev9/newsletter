#!/usr/bin/env python3
"""Testy ctxsplit.py (stdlib, bez pytest). Uruchom: python3 -B test_ctxsplit.py"""
import os
import sys
import tempfile

import ctxsplit as c

fails = 0


def check(name, cond, detail=""):
    global fails
    if cond:
        print("OK  ", name)
    else:
        fails += 1
        print("FAIL", name, detail)


def tiny():
    u0 = c.Unit(0, "A", [100, 200], 50, set())
    u1 = c.Unit(1, "B", [300], 50, {0})
    return [u0, u1]


# 1. determinizm i rozmiar zadania
us = c.build_units()
check("24 jednostki", len(us) == 24)
check("suma tokenow pracy 543784", sum(u.tokens for u in us) == 543784, sum(u.tokens for u in us))
check("deterministyczne", [u.deltas for u in us] == [u.deltas for u in c.build_units()])
check("zadanie nie miesci sie w oknie", sum(u.tokens for u in us) + c.BASE_DEFAULT > c.WINDOW_DEFAULT)

# 2. recznie policzony scenariusz bez ciec: 1100 + 1300 + 1600 = 4000; wazony 1375 + 360 + 505 = 2240
r = c.simulate(tiny(), "never", "none", 0, base=1000, W=10 ** 9)
check("bez ciec: token-tury 4000", r["token_tury"] == 4000, r)
check("bez ciec: wazony 2240", r["wazony"] == 2240, r)
check("bez ciec: 1 okno, 0 brakujacych", r["windows"] == 1 and r["missing"] == 0, r)

# 3. ciecie na granicy z polityka live: fakt 0 przezywa, nic nie brakuje
r = c.simulate(tiny(), "boundary", "live", 1200, base=1000, W=10 ** 9)
check("boundary+live: 2 okna, token-tury 5450", r["windows"] == 2 and r["token_tury"] == 5450, r)
check("boundary+live: brak brakujacych faktow", r["missing"] == 0 and r["rework"] == 0, r)

# 4. ten sam scenariusz bez handoffu: taniej w surowych tokenach, ale fakt trzeba odtworzyc
r = c.simulate(tiny(), "boundary", "none", 1200, base=1000, W=10 ** 9)
check("boundary+none: brakuje 1 faktu, rework 120", r["missing"] == 1 and r["rework"] == 120, r)
check("boundary+none: token-tury 5120", r["token_tury"] == 5120, r)

# 5. ciecie w srodku jednostki powtarza prace w toku
r = c.simulate(tiny(), "mid", "live", 1250, base=1000, W=10 ** 9)
check("mid: powtorzona praca w toku > 0", r["rework"] > 0 and r["windows"] >= 2, r)

# 6. twardy limit W zawsze tnie w srodku jednostki i liczy ciecie wymuszone
r = c.simulate(us, "never", "recent3", 0)
check("never: tnie wymuszenie, nie przekracza okna", r["forced"] > 0 and r["overflow_tur"] == 0, r)
check("never+recent3: gubi fakty", r["missing"] > 0, r)

# 7. wlasnosci polityk na pelnym zadaniu
live = c.simulate(us, "boundary", "live", 90_000)
none = c.simulate(us, "boundary", "none", 90_000)
allp = c.simulate(us, "boundary", "all", 90_000)
check("live: 0 brakujacych, 0 rework, 0 wymuszonych", live["missing"] == 0 and live["rework"] == 0 and live["forced"] == 0, live)
check("none: brakujace fakty > 0", none["missing"] > 0 and none["rework"] > 0, none)
check("all: handoffy wieksze niz live", allp["handoff_total"] > live["handoff_total"], (allp["handoff_total"], live["handoff_total"]))
check("live tanszy (wazony) niz none", live["wazony"] < none["wazony"])
check("predictive nie jest gorszy od boundary przy T=90000", c.simulate(us, "predictive", "live", 90_000)["wazony"] <= live["wazony"])
check("dzielenie tanszej niz jedno okno bez limitu (wazony)", live["wazony"] < c.unlimited(us)["wazony"])

known = set(range(10))
check("recent3 = 3 ostatnie", c.pol_recent(known, 10, us) == {7, 8, 9})
check("live podzbior known", c.pol_live(known, 10, us) <= known)
check("all_capped miesci sie w limicie", c.handoff_tokens("all_capped", c.pol_all_capped(set(range(24)), 24, us), us) <= c.CAP_ALL)

# 8. handoff jako plik
h = c.render_handoff(us, 12, 2)
check("wyrenderowany handoff przechodzi lint", c.lint_handoff(h) == [], c.lint_handoff(h))
check("liczba decyzji == liczba faktow zywych",
      sum(1 for l in h.splitlines() if l.startswith("- D")) == len(c.pol_live(set(range(12)), 12, us)))
check("handoff miesci sie w 1500 tok.", c.tok_text(h) <= 1500, c.tok_text(h))

# 9. testy negatywne lintu
check("lint: brak sekcji", any("Pulapki" in e for e in c.lint_handoff(h.replace("## Pulapki", "## Inne"))))
check("lint: decyzja bez wskaznika", any("bez wskaznika" in e for e in c.lint_handoff(h.replace("-> docs/decisions/00-orders.md", ""))))
check("lint: za duzy", any("za duzy" in e for e in c.lint_handoff(h, cap=100)))
check("lint: dwa kroki", any("dokladnie 1" in e for e in c.lint_handoff(h.replace("## Pulapki", "- U13 drugi krok\n\n## Pulapki"))))
check("lint: dluga linia", any("znakow" in e for e in c.lint_handoff(h + "\n" + "x" * 300)))
check("lint: brak polecenia weryfikacji", any("Weryfikacja" in e for e in c.lint_handoff(h.replace("`", ""))))
fence = "\n```\n" + "\n".join("log" for _ in range(20)) + "\n```\n"
check("lint: dlugi blok kodu", any("blok kodu" in e for e in c.lint_handoff(h + fence)))
swapped = h.replace("## Cel", "## TMP").replace("## Zrobione", "## Cel").replace("## TMP", "## Zrobione")
check("lint: zla kolejnosc", any("kolejnosci" in e for e in c.lint_handoff(swapped)))

with tempfile.TemporaryDirectory() as d:
    errs = c.lint_handoff(h, root=d)
    check("lint --root: nieistniejace wskazniki wykryte", any("nieistniejacego" in e for e in errs))
    os.makedirs(os.path.join(d, "docs", "decisions"))
    for i in c.pol_live(set(range(12)), 12, us):
        open(os.path.join(d, "docs", "decisions", f"{i:02d}-{us[i].name.lower()}.md"), "w").close()
    check("lint --root: istniejace wskazniki OK", c.lint_handoff(h, root=d) == [], c.lint_handoff(h, root=d))

print(f"\n{'OK: 0 niepowodzen' if not fails else 'NIEPOWODZEN: %d' % fails}")
sys.exit(1 if fails else 0)
