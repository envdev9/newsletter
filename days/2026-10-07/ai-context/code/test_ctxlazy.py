#!/usr/bin/env python3
"""Testy ctxlazy.py (stdlib). Uruchom: python3 -B test_ctxlazy.py"""
import sys

import ctxlazy as c

fails = 0


def check(name, cond, info=""):
    global fails
    if cond:
        print("OK  ", name)
    else:
        fails += 1
        print("FAIL", name, info)


tools = c.build_catalog()
names = [t["name"] for t in tools]
check("katalog deterministyczny", [t["name"] for t in c.build_catalog()] == names)
check("nazwy unikalne", len(set(names)) == len(names))
check("tok: 4 bajty = 1 tok.", c.tok("abcd") == 1 and c.tok("abcde") == 2)
check("nazwy tanie vs pelne definicje", sum(map(c.name_cost, tools)) * 10 < sum(map(c.full_cost, tools)))

idx = c.Bm25(tools)
check("BM25: dokladna nazwa na 1. miejscu", idx.search("pod logs tail", 3)[0] == "kubernetes__pod_logs")
check("BM25: brak trafien = pusta lista", idx.search("zzzzqqq", 5) == [])
check("BM25: k ogranicza wynik", len(idx.search("list", 4)) == 4)

eager = c.simulate(tools, "eager")
names_s = c.simulate(tools, "deferred_names")
blind = c.simulate(tools, "deferred_blind")
oracle = c.simulate(tools, "oracle")
check("eager: stale = suma pelnych definicji", eager["stale_tok"] == sum(map(c.full_cost, tools)))
check("kolejnosc kosztu: eager > names > blind > oracle",
      eager["token_tury"] > names_s["token_tury"] > blind["token_tury"] > oracle["token_tury"])
check("deferred_names: baza = nazwy + tool_search",
      names_s["stale_tok"] == sum(map(c.name_cost, tools)) + c.tok(c.SEARCH_TOOL))
check("wieksze k => wiecej zaladowanych", c.simulate(tools, "deferred_names", 12)["zaladowane"]
      > c.simulate(tools, "deferred_names", 2)["zaladowane"])
check("zaladowane nie przekracza katalogu", c.simulate(tools, "deferred_names", 50)["zaladowane"] <= len(tools))

# test negatywny: zadanie, ktorego zapytanie nie ma zadnego pokrycia leksykalnego, jest niezaliczone
bad = [("close the bug report", None, ["jira__transition_ticket"])]
check("negatyw: parafraza bez ponowienia = pudlo", c.simulate(tools, "deferred_names", 5, bad)["trafienia"] == 0)
# ten sam z ponowieniem zmienionym slownictwem
ok = [("close the bug report", "move ticket to Done status workflow", ["jira__transition_ticket"])]
check("ponowienie ze slownictwem narzedzia = trafienie", c.simulate(tools, "deferred_names", 5, ok)["trafienia"] == 1)

# tanszy start nie znaczy tanszy koniec: przy zaladowaniu calego katalogu leniwe jest drozsze
all_loaded = sum(map(c.name_cost, tools)) + c.tok(c.SEARCH_TOOL) + sum(map(c.full_cost, tools))
check("zaladowanie wszystkiego: leniwe drozsze od eager", all_loaded > eager["stale_tok"])

print(f"OK: {fails} niepowodzen" if fails == 0 else f"BLAD: {fails} niepowodzen")
sys.exit(1 if fails else 0)
