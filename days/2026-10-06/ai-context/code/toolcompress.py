#!/usr/bin/env python3
"""toolcompress.py - kompresja wynikow narzedzi z metryka "przezycia igiel" + pakowanie budzetu.

Python 3.10, tylko stdlib. WSZYSTKIE dane sa SYNTETYCZNE (generowane tu, ziarno stale).
Tokeny = bajty/4 (heurystyka). Metryka recall = ile "igiel" (faktow, ktore model MUSI zobaczyc)
przetrwalo w skompresowanym tekscie. To mierzy INFORMACJE w tekscie, a NIE zachowanie modelu.

Uzycie:
  python3 -B toolcompress.py demo          # tabela strategii na logu i JSON-ie
  python3 -B toolcompress.py pack          # pakowanie budzetu kontekstu (plecak) + kolejnosc
  python3 -B toolcompress.py filter < plik # smart_log z stdin (budzet --budget tok.)
"""
import argparse
import json
import random
import re
import sys
import tempfile
from pathlib import Path

TOK = lambda s: (len(s.encode("utf-8")) + 3) // 4  # bajty/4, w gore


# ---------------------------------------------------------------- dane syntetyczne
def make_build_log(n=2400, seed=7):
    """Syntetyczny log 'dotnet build + test': tysiace powtarzalnych linii, kilka igiel w srodku."""
    rnd = random.Random(seed)
    lines = []
    files = ["Orders", "Customers", "Invoices", "Shipping", "Catalog", "Pricing"]
    for i in range(n):
        f = rnd.choice(files)
        k = rnd.random()
        if k < 0.55:
            lines.append(f"2026-10-06T10:{i // 60 % 60:02d}:{i % 60:02d}.{rnd.randint(0,999):03d}Z info: "
                         f"{f}.Api[0] GET /{f.lower()}/{rnd.randint(1000,99999)} -> 200 in {rnd.randint(2,90)}ms")
        elif k < 0.85:
            lines.append(f"src/{f}/{f}Dto{rnd.randint(1,40)}.cs({rnd.randint(5,200)},{rnd.randint(3,30)}): "
                         f"warning CS8618: Non-nullable property 'Prop{rnd.randint(1,9)}' must contain a non-null value")
        else:
            lines.append(f"  Restored /home/build/{f}/obj/{f}.csproj (in {rnd.randint(10,900)} ms).")
    needles = {}
    # igly w srodku (40%, 55%, 70%) - tam, gdzie head/tail ich nie dosiegna
    plant = [
        (0.40, "src/Pricing/DiscountCalculator.cs(88,13): error CS0103: The name 'rounding' does not exist in the current context",
         "DiscountCalculator.cs(88,13): error CS0103"),
        (0.55, "  Failed Orders.Tests.OrderTotalTests.Total_Rounds_HalfUp [31 ms] Expected: 10.05m But was: 10.04m",
         "Total_Rounds_HalfUp"),
        # igla BEZ slow kluczowych 'error/fail' - test na zawodnosc heurystyki wzorcow
        (0.70, "2026-10-06T10:41:07.002Z info: Migrator[0] Migration 20261001_AddIndex skipped: checksum mismatch (expected 9f2c, found 77ab)",
         "20261001_AddIndex skipped"),
    ]
    for pos, text, needle in sorted(plant):
        lines.insert(int(len(lines) * pos), text)
        needles[needle] = text
    tail = "Build FAILED. 1 Error(s), 2140 Warning(s). Tests: 1 failed, 214 passed."
    lines.append(tail)
    needles["Build FAILED. 1 Error(s)"] = tail
    return "\n".join(lines), list(needles)


def make_orders_json(n=300, seed=11):
    """Syntetyczna odpowiedz API: 300 zamowien x 14 pol; 3 w statusie Failed (igly)."""
    rnd = random.Random(seed)
    rows = []
    for i in range(n):
        rows.append({
            "id": f"ord-{i:05d}", "status": "Paid", "total": round(rnd.uniform(5, 900), 2),
            "currency": "PLN", "customerId": f"c-{rnd.randint(1,500):04d}",
            "createdAt": f"2026-09-{rnd.randint(1,28):02d}T{rnd.randint(0,23):02d}:00:00Z",
            "updatedAt": f"2026-10-0{rnd.randint(1,5)}T08:00:00Z",
            "shippingAddress": {"street": "Ul. Przykladowa 1", "city": "Poznan", "zip": "60-001"},
            "lines": [{"sku": f"SKU-{rnd.randint(1,999)}", "qty": rnd.randint(1, 4)}],
            "notes": "", "channel": "web", "tags": ["a", "b"], "version": 3, "etag": f"W/\"{rnd.getrandbits(32):08x}\"",
        })
    needles = []
    for idx in (37, 151, 262):
        rows[idx]["status"] = "Failed"
        rows[idx]["notes"] = "payment gateway timeout"
        needles.append(rows[idx]["id"])
    return json.dumps({"items": rows, "total": n}, indent=2), needles


# ---------------------------------------------------------------- strategie: log
def s_head(text, budget):
    return text.encode()[: budget * 4].decode(errors="ignore")


def s_head_tail(text, budget):
    b = budget * 4
    raw = text.encode()
    if len(raw) <= b:
        return text
    h, t = raw[: b // 2].decode(errors="ignore"), raw[-(b // 2):].decode(errors="ignore")
    return h + "\n[... pominieto %d bajtow ...]\n" % (len(raw) - b) + t


_NORM = [(re.compile(r"\d{4}-\d\d-\d\dT[\d:.]+Z"), "<ts>"), (re.compile(r"\d+"), "<n>")]


def template(line):
    for rx, rep in _NORM:
        line = rx.sub(rep, line)
    return line.strip()


SEV = [(re.compile(r"\b(error|fatal|exception|FAILED|Failed)\b"), 100),
       (re.compile(r"\b(warn(ing)?)\b", re.I), 5)]


def severity(line):
    return max([w for rx, w in SEV if rx.search(line)] or [0])


def s_dedup(text, budget=None):
    """Zwija linie o tym samym szablonie (cyfry/znaczniki czasu -> <n>): zostaje 1. wystapienie + licznik."""
    lines = text.split("\n")
    count, first = {}, {}
    for i, l in enumerate(lines):
        t = template(l)
        count[t] = count.get(t, 0) + 1
        first.setdefault(t, i)
    out = []
    for t, i in sorted(first.items(), key=lambda kv: kv[1]):
        c = count[t]
        out.append(lines[i] + (f"   [x{c}]" if c > 1 else ""))
    return "\n".join(out)


def s_errors_only(text, budget=None):
    """Tylko linie o wzorcu bledu + ostatnia linia. Zawodzi, gdy fakt nie wyglada jak blad."""
    lines = text.split("\n")
    keep = [l for l in lines if severity(l) >= 100]
    return "\n".join(keep + [lines[-1]])


def s_smart(text, budget):
    """dedup + wybor linii po wyniku = waga_powaznosci + 1/liczebnosc szablonu, w oryginalnej kolejnosci,
    do wyczerpania budzetu; ostatnia linia (podsumowanie) zawsze."""
    lines = text.split("\n")
    count = {}
    for l in lines:
        count[template(l)] = count.get(template(l), 0) + 1
    seen, cand = set(), []
    for i, l in enumerate(lines[:-1]):
        t = template(l)
        if t in seen:
            continue
        seen.add(t)
        cand.append((severity(l) + 1.0 / count[t], i, l + (f"   [x{count[t]}]" if count[t] > 1 else "")))
    used = TOK(lines[-1]) + 20
    chosen = []
    for score, i, l in sorted(cand, key=lambda c: -c[0]):
        if used + TOK(l) > budget:
            continue
        used += TOK(l)
        chosen.append((i, l))
    body = [l for _, l in sorted(chosen)]
    dropped = len(cand) - len(chosen)
    return "\n".join(body + [f"[... {dropped} rzadziej istotnych szablonow pominieto ...]", lines[-1]])


def s_spill(text, budget=None):
    """Pelny wynik na dysk, do kontekstu: statystyka + wskaznik + podpowiedz grep."""
    f = Path(tempfile.gettempdir()) / "toolcompress_spill_demo.log"
    f.write_text(text)
    n = text.count("\n") + 1
    errs = sum(1 for l in text.split("\n") if severity(l) >= 100)
    return (f"Wynik: {n} linii, {len(text)} bajtow, linii o wzorcu bledu: {errs}.\n"
            f"Pelny log: {f}\nCzytaj selektywnie, np. grep -n -E 'error|Failed' {f}")


# ---------------------------------------------------------------- strategie: JSON
def j_head(text, budget):
    return text.encode()[: budget * 4].decode(errors="ignore")


def j_project(text, budget=None):
    d = json.loads(text)
    return json.dumps({"total": d["total"], "items": [
        {k: r[k] for k in ("id", "status", "total")} for r in d["items"]]}, separators=(",", ":"))


def j_filter_project(text, budget=None):
    d = json.loads(text)
    bad = [r for r in d["items"] if r["status"] != "Paid"]
    cnt = {}
    for r in d["items"]:
        cnt[r["status"]] = cnt.get(r["status"], 0) + 1
    return json.dumps({"total": d["total"], "by_status": cnt, "non_paid": [
        {k: r[k] for k in ("id", "status", "total", "notes")} for r in bad]}, separators=(",", ":"))


# ---------------------------------------------------------------- metryki
def recall(out, needles):
    return sum(1 for n in needles if n in out), len(needles)


def row(name, out, base_tok, needles):
    got, tot = recall(out, needles)
    t = TOK(out)
    return f"| {name:<22} | {t:>6} | {base_tok / max(t,1):>6.1f}x | {got}/{tot} |"


def demo(budget):
    log, ln = make_build_log()
    base = TOK(log)
    print(f"LOG (syntetyczny): {log.count(chr(10)) + 1} linii, ~{base} tok., igiel: {len(ln)}; budzet strategii: {budget} tok.")
    print("| strategia              |   ~tok | zysk   | igly |")
    print("|------------------------|-------:|-------:|------|")
    for name, fn in [("surowy (nic)", lambda t, b: t), ("head", s_head), ("head+tail", s_head_tail),
                     ("dedup", s_dedup), ("tylko bledy", s_errors_only),
                     ("smart (dedup+wynik)", s_smart), ("spill + wskaznik", s_spill)]:
        print(row(name, fn(log, budget), base, ln))
    print("\nWyjscie 'smart':")
    print(s_smart(log, budget))
    js, jn = make_orders_json()
    jb = TOK(js)
    print(f"\nJSON (syntetyczny): ~{jb} tok., igiel (id Failed): {len(jn)}")
    print("| strategia              |   ~tok | zysk   | igly | poprawny JSON |")
    print("|------------------------|-------:|-------:|------|---------------|")
    for name, fn in [("surowy (nic)", lambda t, b: t), ("head", j_head), ("projekcja pol", j_project),
                     ("filtr+projekcja+licznik", j_filter_project)]:
        out = fn(js, budget)
        try:
            json.loads(out)
            ok = "tak"
        except ValueError:
            ok = "NIE"
        print(row(name, out, jb, jn)[:-1] + f" {ok:<13} |")
    print("\nWyjscie 'filtr+projekcja+licznik':")
    print(j_filter_project(js))


# ---------------------------------------------------------------- budzet jako kod
def pack(items, budget):
    """Plecak zachlanny po gestosci wartosci (value/tokens); zwraca (wybrane, odrzucone)."""
    chosen, dropped, used = [], [], 0
    for it in sorted(items, key=lambda x: -x["value"] / x["tok"]):
        if used + it["tok"] <= budget:
            chosen.append(it)
            used += it["tok"]
        else:
            dropped.append(it)
    return chosen, dropped


def fifo(items, budget):
    chosen, dropped, used = [], [], 0
    for it in items:
        if used + it["tok"] <= budget:
            chosen.append(it)
            used += it["tok"]
        else:
            dropped.append(it)
    return chosen, dropped


def order_edges(chosen):
    """Kolejnosc 'brzegi': najwazniejsze na poczatek i na koniec, najmniej wazne w srodek.
    To hipoteza oparta na doniesieniach o 'lost in the middle' - NIE mierzona tutaj na modelu."""
    s = sorted(chosen, key=lambda x: -x["value"])
    front, back = [], []
    for i, it in enumerate(s):
        (front if i % 2 == 0 else back).append(it)
    return front + back[::-1]


# SYNTETYCZNE kandydaty do kontekstu zadania "napraw test Total_Rounds_HalfUp".
# Kolejnosc listy = kolejnosc NADEJSCIA (agent najpierw czyta wszystko jak leci) - dla FIFO.
# Wartosci (value) to moje subiektywne oceny, nie pomiar. Ograniczenie: plecak nie zna wykluczen
# (surowy log i log po smart_log to alternatywy, a plecak moglby wziac oba).
ITEMS = [
    {"name": "dokumentacja architektury (caly docs/)", "tok": 2500, "value": 10},
    {"name": "historia git blame calego pliku", "tok": 1200, "value": 12},
    {"name": "pelny log builda (surowy)", "tok": 1500, "value": 25},
    {"name": "tresc zadania + kryterium akceptacji", "tok": 180, "value": 100},
    {"name": "DiscountCalculator.cs (caly plik)", "tok": 1400, "value": 80},
    {"name": "stack trace padajacego testu", "tok": 350, "value": 90},
    {"name": "OrderTotalTests.cs (caly plik)", "tok": 1800, "value": 60},
    {"name": "log builda po smart_log", "tok": 400, "value": 22},
    {"name": "regula: kwoty to decimal, MidpointRounding", "tok": 40, "value": 70},
]


def do_pack(budget):
    for name, fn in [("FIFO (jak leci)", fifo), ("plecak (value/tok)", pack)]:
        ch, dr = fn(ITEMS, budget)
        used = sum(i["tok"] for i in ch)
        print(f"\n{name}: ~{used}/{budget} tok., suma wartosci = {sum(i['value'] for i in ch)}")
        for i in ch:
            print(f"   + {i['name']:<46} {i['tok']:>5} tok.  v={i['value']}")
        print("   odrzucone: " + "; ".join(i["name"] for i in dr))
    ch, _ = pack(ITEMS, budget)
    print("\nKolejnosc 'brzegi' dla wybranych (hipoteza, niemierzona):")
    for i in order_edges(ch):
        print(f"   {i['value']:>3}  {i['name']}")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("cmd", choices=["demo", "pack", "filter"])
    ap.add_argument("--budget", type=int, default=600)
    a = ap.parse_args()
    if a.cmd == "demo":
        demo(a.budget)
    elif a.cmd == "pack":
        do_pack(a.budget if "--budget" in sys.argv else 4000)
    else:
        print(s_smart(sys.stdin.read().rstrip("\n"), a.budget))


if __name__ == "__main__":
    main()
