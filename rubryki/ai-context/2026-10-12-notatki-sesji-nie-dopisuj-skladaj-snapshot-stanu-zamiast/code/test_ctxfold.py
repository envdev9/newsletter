#!/usr/bin/env python3
"""Testy ctxfold.py (stdlib, bez frameworka). Uruchom: python3 -B test_ctxfold.py"""
import random
import sys

import ctxfold as cf

FAIL = []
N = [0]


def check(cond, msg):
    N[0] += 1
    if not cond:
        FAIL.append(msg)
        print("FAIL:", msg)


def E(t, op, key, val="", why=""):
    return dict(t=t, op=op, key=key, val=val, why=why)


# 1. reczne zdarzenia -> reczny stan
evs = [E(1, "set", "a", "x"), E(2, "set", "a", "y"), E(3, "add", "s", "p"), E(4, "add", "s", "q"),
       E(5, "rm", "s", "p"), E(6, "inc", "n", "1"), E(7, "inc", "n", "1"), E(8, "set", "tmp/1", "z"),
       E(9, "del", "tmp/1")]
st = cf.fold(evs)
check(st["scalars"] == {"a": "y"}, "set nadpisuje, del usuwa")
check(st["sets"]["s"] == {"q"}, "add/rm na zbiorze")
check(st["counters"] == {"n": 2}, "licznik sumuje")
check(cf.tokens("abcdefgh") == 2, "tokeny = bajty/4")

# 2. fold nie jest przemienny (kolejnosc ma znaczenie)
a = cf.fold([E(1, "set", "k", "1"), E(2, "set", "k", "2")])
b = cf.fold([E(2, "set", "k", "2"), E(1, "set", "k", "1")])
check(a["scalars"] != b["scalars"], "fold zalezy od kolejnosci")

# 3. generator deterministyczny, rozne ziarna daja rozny strumien
check(cf.gen_events(300, 19) == cf.gen_events(300, 19), "generator deterministyczny")
check(cf.gen_events(300, 19) != cf.gen_events(300, 20), "inne ziarno -> inny strumien")

ev = cf.gen_events(300, 19)
truth = cf.fold(ev)

# 4. render zdarzenia <-> parse (bez 'why', ktore parser porzuca)
parsed = cf.parse_log("\n".join(cf.render_event(e) for e in ev))
check(len(parsed) == len(ev), "parse_log: wszystkie zdarzenia")
check(all((p["t"], p["op"], p["key"], p["val"]) == (e["t"], e["op"], e["key"], e["val"])
          for p, e in zip(parsed, ev)), "round trip zdarzen")

# 5. round trip snapshotu (z why i bez)
for why in (False, True):
    txt = cf.text_fold(ev, 300, why=why)
    check(cf.norm(cf.parse_snapshot(txt)) == cf.norm(truth), f"round trip snapshotu why={why}")

# 6. ASOCJACYJNOSC: fold(parse(snapshot(a)) + b) == fold(a+b) dla losowych podzialow i ziaren
rnd = random.Random(2026)
ok_all = True
trials = 0
for seed in (1, 19, 42, 77):
    evs_s = cf.gen_events(300, seed)
    full = cf.norm(cf.fold(evs_s))
    for _ in range(50):
        i = rnd.randrange(1, 300)
        snap = cf.parse_snapshot(cf.render_snapshot(cf.fold(evs_s[:i]), i, i))
        inc = cf.norm(cf.fold(evs_s[i:], snap))
        trials += 1
        if inc != full:
            ok_all = False
check(ok_all, f"fold inkrementalny == pelny ({trials} podzialow)")

# 6b. wielokrotny fold co k zdarzen
base = cf.empty_state()
for i in range(0, 300, 10):
    base = cf.parse_snapshot(cf.render_snapshot(cf.fold(ev[i:i + 10], base), i + 10, i + 10))
check(cf.norm(base) == cf.norm(truth), "30 foldow po 10 zdarzen == pelny")

# 7. czytelnicy
all_txt = cf.text_append_all(ev, 300)
check(cf.score(cf.reader_correct(all_txt), truth)["correct"] == cf.score(truth, truth)["total"],
      "poprawny czytelnik na pelnym logu: 100%")
nv = cf.score(cf.reader_naive(all_txt), truth)
check(nv["correct"] < nv["total"] and nv["spurious"] > 0, "naiwny czytelnik na logu myli sie")
snap_txt = cf.text_fold(ev, 300)
nf = cf.score(cf.reader_naive(snap_txt), truth)
check(nf["correct"] == nf["total"] and nf["spurious"] == 0, "naiwny czytelnik na snapshocie: bez bledow")

# 8. fold_every: poprawny dla KAZDEGO t (ogon surowych zdarzen)
bad = [t for t in range(1, 301)
       if cf.norm(cf.reader_correct(cf.text_fold_every(ev, t, 25)))
       != cf.norm(cf.fold([e for e in ev if e["t"] <= t]))]
check(not bad, f"fold_every(25) poprawny dla t=1..300 (zle: {bad[:5]})")

# 9. ucinanie od najstarszych gubi fundament
cap_txt = cf.text_append_cap(ev, 300, 1500)
got = cf.reader_correct(cap_txt)
lost_keys = [k for k in truth["scalars"] if k not in got["scalars"]]
check(any(k.startswith("conv/") for k in lost_keys), "cap 1500 gubi co najmniej jedna konwencje")
check(cf.tokens(cap_txt) <= 1500 + 80, "cap respektuje limit (+ jedna linia)")

# 10. rozmiar: snapshot << log
check(cf.tokens(snap_txt) * 5 < cf.tokens(all_txt), "snapshot >5x mniejszy niz log")

# 11. verify
good = cf.parse_snapshot(snap_txt)
check(cf.verify(good, truth, ev) == [], "verify: prawdziwy snapshot OK")


def mutate(fn):
    s = cf.copy_state(good)
    fn(s)
    return cf.verify(s, truth, ev)


k0 = sorted(truth["scalars"])[0]
p = mutate(lambda s: s["scalars"].pop(k0))
check(any(x.startswith("BRAK:") for x in p), "verify: brak klucza")
# przestarzala wartosc: klucz z >=2 roznymi wartosciami w historii
multi = None
for k in truth["scalars"]:
    vals = {e["val"] for e in ev if e["op"] == "set" and e["key"] == k}
    if len(vals) > 1:
        multi = (k, sorted(vals - {truth["scalars"][k]})[0])
        break
check(multi is not None, "w strumieniu jest klucz nadpisany")
p = mutate(lambda s: s["scalars"].__setitem__(multi[0], multi[1]))
check(any(x.startswith("PRZESTARZALA") for x in p), "verify: przestarzala wartosc")
p = mutate(lambda s: s["scalars"].__setitem__(k0, "zmyslona wartosc"))
check(any(x.startswith("BLEDNA") for x in p), "verify: zmyslona wartosc")
p = mutate(lambda s: s["scalars"].__setitem__("decision/nieistniejacy", "x"))
check(any(x.startswith("NADMIAR") for x in p), "verify: nadmiarowy klucz")
p = mutate(lambda s: s["counters"].__setitem__("done", 999))
check(any(x.startswith("LICZNIK") for x in p), "verify: zly licznik")
p = mutate(lambda s: s["sets"].setdefault("todo", set()).add("cos zmyslonego"))
check(any(x.startswith("NADMIAR elementu") for x in p), "verify: nadmiarowy element zbioru")
sk = sorted(truth["sets"]["todo"])[0]
p = mutate(lambda s: s["sets"]["todo"].discard(sk))
check(any(x.startswith("BRAK elementu") for x in p), "verify: brak elementu zbioru")

# 12. kolejnosc: sortowanie po t naprawia przemieszane zdarzenia
sh = list(ev)
random.Random(7).shuffle(sh)
check(cf.norm(cf.fold(sorted(sh, key=lambda e: e["t"]))) == cf.norm(truth), "sortowanie po t")
check(cf.norm(cf.fold(sh)) != cf.norm(truth), "bez sortowania stan sie rozjezdza")

print(f"{'OK' if not FAIL else 'BLAD'}: {N[0]} asercji, {len(FAIL)} niepowodzen")
sys.exit(1 if FAIL else 0)
