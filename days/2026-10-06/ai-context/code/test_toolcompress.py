#!/usr/bin/env python3
"""Testy toolcompress.py (Python 3.10, stdlib). Uruchom: python3 -B test_toolcompress.py"""
import json
import sys

import toolcompress as tc

fails = 0


def check(cond, msg):
    global fails
    print(("OK   " if cond else "FAIL ") + msg)
    fails += 0 if cond else 1


log, needles = tc.make_build_log()
base = tc.TOK(log)
B = 600
check(len(needles) == 4 and all(n in log for n in needles), "log syntetyczny zawiera wszystkie 4 igly")
check(tc.make_build_log() == (log, needles), "generator deterministyczny")
check(tc.recall(tc.s_head(log, B), needles)[0] == 0, "head gubi igly (leza w srodku/na koncu)")
ht = tc.s_head_tail(log, B)
check(tc.recall(ht, needles)[0] == 1, "head+tail zachowuje tylko podsumowanie z konca")
er = tc.s_errors_only(log)
check(tc.recall(er, needles)[0] == 3, "tylko-bledy: 3/4 - gubi igle bez slowa error/Failed")
dd = tc.s_dedup(log)
check(tc.recall(dd, needles)[0] == 4, "dedup zachowuje 4/4 (igly maja unikalne szablony)")
sm = tc.s_smart(log, B)
check(tc.recall(sm, needles)[0] == 4, "smart zachowuje 4/4")
check(tc.TOK(sm) <= B + 30, "smart miesci sie w budzecie (+narzut znacznika)")
check(base / tc.TOK(sm) > 5, "smart: zysk > 5x wzgledem surowego")
check(tc.template("2026-10-06T10:00:01.123Z GET /a/123 in 45ms") == "<ts> GET /a/<n> in <n>ms", "template normalizuje cyfry i czas")

js, jn = tc.make_orders_json()
try:
    json.loads(tc.j_head(js, B))
    broken = False
except ValueError:
    broken = True
check(broken, "head na JSON-ie daje niepoprawny JSON")
fp = tc.j_filter_project(js)
check(json.loads(fp)["by_status"] == {"Paid": 297, "Failed": 3}, "filtr+licznik: statystyka statusow zgodna z danymi")
check(tc.recall(fp, jn) == (3, 3), "filtr+projekcja: 3/3 igiel")
check(tc.TOK(js) / tc.TOK(fp) > 50, "filtr+projekcja: zysk > 50x")
check(tc.recall(tc.j_project(js), jn) == (3, 3), "sama projekcja tez 3/3, ale kosztuje wiecej")
check(tc.TOK(tc.j_project(js)) > 5 * tc.TOK(fp), "projekcja bez filtra > 5x droższa niz filtr+projekcja")

sp = tc.s_spill(log)
check(tc.TOK(sp) < 120 and "grep" in sp, "spill: maly wskaznik z podpowiedzia grep")

ch, dr = tc.pack(tc.ITEMS, 4000)
ch2, _ = tc.fifo(tc.ITEMS, 4000)
check(sum(i["tok"] for i in ch) <= 4000, "plecak respektuje budzet")
check(sum(i["value"] for i in ch) > sum(i["value"] for i in ch2), "plecak > FIFO pod wzgledem sumy wartosci")
o = tc.order_edges(ch)
check(o[0]["value"] == max(i["value"] for i in ch) and len(o) == len(ch), "kolejnosc brzegi: najwazniejszy pierwszy")
sorted_vals = sorted(i["value"] for i in ch)
check(o[len(o) // 2]["value"] <= sorted_vals[len(sorted_vals) // 2], "kolejnosc brzegi: srodek nie jest najwazniejszy")

print(f"\n{'OK' if not fails else 'BLAD'}: {fails} niepowodzen")
sys.exit(1 if fails else 0)
