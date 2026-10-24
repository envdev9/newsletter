#!/usr/bin/env python3
"""Testy ctxsearch.py (stdlib, bez frameworka). Uruchom: python3 -B test_ctxsearch.py"""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import ctxsearch as C  # noqa: E402

FAILS = []
COUNT = 0


def check(cond, msg):
    global COUNT
    COUNT += 1
    if not cond:
        FAILS.append(msg)
        print("FAIL:", msg)


tools = C.build_catalog()
R = C.Retrievers(tools)
by = {t["name"]: t for t in tools}

# --- katalog
check(len(tools) == 264, f"katalog 264 narzedzi, jest {len(tools)}")
check(len({t["server"] for t in tools}) == 8, "8 serwerow")
check(len(by) == 264, "nazwy unikalne")
check(C.check_targets(tools, C.DEV, C.TEST, C.FRESH, [(q, w) for q, _, w in C.AMBIG]) == [],
      "wszystkie cele zapytan istnieja w katalogu")
check(sum(C.full_cost(t) for t in tools) == 26380, "pelne definicje = 26380 tok. (jak w #14)")

# --- zestawy rozlaczne i bez duplikatow
sets = {"dev": C.DEV, "test": C.TEST, "fresh": C.FRESH}
qs = {k: {q.lower() for q, _ in v} for k, v in sets.items()}
check(not (qs["dev"] & qs["test"]), "dev i test rozlaczne")
check(not (qs["test"] & qs["fresh"]), "test i fresh rozlaczne")
check(not (qs["dev"] & qs["fresh"]), "dev i fresh rozlaczne")
check(all(len(v) == len(sets[k]) for k, v in qs.items()), "brak duplikatow zapytan w zestawach")

# --- tokenizacja / slownik
check(C.tokens("Pods LOGS") == ["pods", "pod", "logs", "log"], "stemming liczby mnogiej")
check("restart" in C.lookup_forms("restarting"), "lookup_forms: -ing")
check("merge" in C.lookup_forms("merged"), "lookup_forms: -ed -> bez ostatniej litery (merge)")
check("index" not in C.lookup_forms("indexes"), "znane ograniczenie: -es nie jest obslugiwane (stad PEEK_EXTRA)")
check(C.expand_query("silence the pager").startswith("silence the pager "), "expand_query dopisuje na koncu")
check("acknowledge" in C.expand_query("silence the pager").split(), "expand_query: pager -> acknowledge")
check(C.expand_query("zzz qqq") == "zzz qqq", "zapytanie bez hasel nie zmienia sie")
check(C.expand_query("pager", {}) == "pager", "pusty slownik = brak ekspansji")

# --- ngramy
g = C.ngrams("ab")
check(set(g) == {" ab", "ab "}, "trigramy z paddingiem")
check(R.ng.scores("restarting")[0] >= 0.0, "ngram scores zwraca liczby")
v = R.ng.scores("rollout restart deployment")
top = tools[max(range(len(v)), key=lambda i: v[i])]["name"]
check(top == "kubernetes__rollout_restart", f"ngram: rollout restart -> rollout_restart, jest {top}")

# --- self-retrieval: opis narzedzia specjalnego jako zapytanie
specials = [t for t in tools if t["verb"] is None]
check(len(specials) == 18, f"18 narzedzi specjalnych, jest {len(specials)}")
hit = sum(1 for t in specials if R.rank("bm25", t["description"])[0] == t["name"])
check(hit == len(specials), f"bm25: wlasny opis -> samo narzedzie top-1 ({hit}/{len(specials)})")

# --- RRF
check(C.rrf([["a", "b", "c"]]) == ["a", "b", "c"], "rrf jednej listy zachowuje kolejnosc")
check(C.rrf([["a", "b"], ["b", "a"]]) == ["a", "b"], "rrf remis rozstrzygany alfabetycznie")
check(C.rrf([["a", "b"], ["b", "c"]])[0] == "b", "rrf: element w obu listach wygrywa")

# --- prior sesji
base = C._rank(tools, R.bm.scores("create comment"))
same = C._rank(tools, R.bm.scores("create comment"), ["github"], 0.0)
check(base == same, "boost 0 nie zmienia rankingu")
boosted = C._rank(tools, R.bm.scores("create comment"), ["github"], 0.25)
check(boosted[0] == "github__create_review_comment", "prior: sesja github -> review_comment na 1.")
check(base[0] == "jira__create_comment", "bez priora wygrywa jira (krotszy opis) - ukryte obciazenie")
check(C._rank(tools, R.bm.scores("create comment"), ["jira"], 0.25)[0] == "jira__create_comment",
      "prior: sesja jira -> jira na 1.")

# --- zachowanie retrieverow = pinned wartosci (regresja)
def r5(name, qset):
    _, r, _ = C.evaluate(R, name, qset)
    return r[5]


check(r5("bm25", C.DEV) == 10, "bm25 dev @5 = 10/18 (jak w #14: 10/18)")
check(r5("bm25", C.TEST) == 17, "bm25 test @5 = 17/30")
check(r5("bm25+syn", C.DEV) == 18, "syn dev @5 = 18/18 (dopasowane do obejrzanego zbioru)")
check(r5("bm25+syn", C.TEST) == 26, "syn test @5 = 26/30")
check(r5("bm25+syn", C.FRESH) == 13, "syn fresh @5 = 13/15")
check(r5("rrf(bm25,ngram)", C.FRESH) == 8, "rrf(bm25,ngram) fresh @5 = 8/15")

# slownik pusty == bm25
R0 = C.Retrievers(tools, {})
check(all(R0.rank("bm25+syn", q) == R0.rank("bm25", q) for q, _ in C.TEST), "pusty slownik: bm25+syn == bm25")

# --- koszt aliasow
plain = sum(C.full_cost(t) for t in tools)
ali = sum(C.full_cost(dict(t, description=C.aliased_doc(t))) for t in tools)
check(ali == 29750 and ali > plain, f"aliasy: 26380 -> 29750 tok., jest {ali}")

# --- overlap
allq = C.DEV + C.TEST + C.FRESH
w, wo = C.overlap_split(tools, allq)
check(len(w) == 40 and len(wo) == 23, f"overlap 40/23, jest {len(w)}/{len(wo)}")
check(C.evaluate(R, "bm25", wo)[1][5] == 4, "bm25 bez wspolnego slowa: 4/23 @5")
check(C.evaluate(R, "bm25+syn", wo)[1][5] == 19, "syn bez wspolnego slowa: 19/23 @5")

print(f"{'OK' if not FAILS else 'FAILED'}: {COUNT} asercji, {len(FAILS)} niepowodzen")
sys.exit(1 if FAILS else 0)
