#!/usr/bin/env python3
"""ctxfold - snapshot stanu zamiast dopisywania (fold) dla pliku handoff / notatek sesji.

Dane SYNTETYCZNE: deterministyczny strumien zdarzen (LCG), zadany regula w kodzie.
Tokeny = bajty/4. Zadnego modelu ani CLI nie uruchamiano.

Podkomendy:
  stats                 statystyki strumienia i prawdziwego stanu
  sizes [--k 25]        rozmiar tekstu dla polityk w kolejnych punktach czasu
  compare [--t 300]     rozmiar + dokladnosc dwoch typow czytelnika (poprawny/naiwny)
  snapshot [--t 300]    wyrenderowany snapshot (stdout)
  verify PLIK [--t 300] sprawdz snapshot (np. napisany przez model) z logiem zdarzen
  tail                  snapshot + ogon: srednia po t=10..300 (rozmiar, czytelnik naiwny)
  log [--key K]         surowy log zdarzen (opcjonalnie jeden klucz)
  order                 skutki braku sortowania zdarzen (zrownoleglone subagenty)
"""
import argparse
import random
import re
import sys

# ---------------------------------------------------------------- generator

class LCG:
    def __init__(self, seed):
        self.s = seed % 2147483647 or 1

    def next(self):
        self.s = (self.s * 48271) % 2147483647
        return self.s

    def rnd(self, n):
        return self.next() % n

    def pick(self, seq):
        return seq[self.rnd(len(seq))]

MODULES = ["orders", "billing", "shipping", "audit", "notifications", "catalog", "pricing",
           "inventory", "identity", "reports", "search", "payments"]
CONVS = ["errors", "logging", "naming", "async", "nullability", "tests"]
VERBS = ["uzyj", "zamien", "przenies", "wydziel", "zachowaj", "usun"]
OBJS = ["Result<T>", "ILogger<T>", "CancellationToken", "IOptions<T>", "rekordy", "DateTimeOffset",
        "Span<byte>", "ValueTask", "init-only", "wyjatek domenowy", "Polly retry", "outbox"]
WHYS = ["bo poprzednie podejscie lamalo kontrakt API", "zgodnie z konwencja z jednostki 0",
        "po awarii na srodowisku testowym", "wymog z przegladu bezpieczenstwa",
        "uproszcza testy jednostkowe", "mniej alokacji na goracej sciezce",
        "zespol platformy wymaga tego formatu", "unikamy zmiany schematu bazy"]


def gen_events(n=300, seed=19):
    """Strumien zdarzen: t=1..6 ustawia konwencje (fundament, rzadko rewidowany)."""
    g = LCG(seed)
    ev = []
    tmp_open = []
    todo = []
    tmp_id = 0

    def val():
        return f"{g.pick(VERBS)} {g.pick(OBJS)} w {g.pick(MODULES)}"

    def why():
        return f"{g.pick(WHYS)}; {g.pick(WHYS)}"

    for t in range(1, n + 1):
        if t <= len(CONVS):
            ev.append(dict(t=t, op="set", key="conv/" + CONVS[t - 1], val=val(), why=why()))
            continue
        r = g.rnd(100)
        if r < 4:
            ev.append(dict(t=t, op="set", key="conv/" + g.pick(CONVS), val=val(), why=why()))
        elif r < 38:
            # decyzje dotycza coraz szerszego zbioru modulow -> czesc nigdy nie rewidowana
            m = MODULES[g.rnd(min(len(MODULES), 2 + t // 25))]
            ev.append(dict(t=t, op="set", key="decision/" + m, val=val(), why=why()))
        elif r < 52:
            item = f"{g.pick(VERBS)} {g.pick(OBJS)}"
            todo.append(item)
            ev.append(dict(t=t, op="add", key="todo", val=item, why=""))
        elif r < 66 and todo:
            item = todo.pop(g.rnd(len(todo)))
            ev.append(dict(t=t, op="rm", key="todo", val=item, why=""))
        elif r < 78:
            ev.append(dict(t=t, op="inc", key="done", val="1", why=""))
        elif r < 86:
            ev.append(dict(t=t, op="add", key="pitfall", val=f"nie {g.pick(VERBS)} {g.pick(OBJS)} ({g.pick(WHYS)})", why=""))
        elif r < 94:
            tmp_id += 1
            k = f"tmp/{tmp_id}"
            tmp_open.append(k)
            ev.append(dict(t=t, op="set", key=k, val=f"sprawdzam {g.pick(OBJS)}", why=""))
        elif tmp_open:
            k = tmp_open.pop(g.rnd(len(tmp_open)))
            ev.append(dict(t=t, op="del", key=k, val="", why=""))
        else:
            ev.append(dict(t=t, op="inc", key="done", val="1", why=""))
    return ev

# ---------------------------------------------------------------- stan (fold)

def empty_state():
    return {"scalars": {}, "sets": {}, "counters": {}}


def apply_event(st, e):
    op, k, v = e["op"], e["key"], e["val"]
    if op == "set":
        st["scalars"][k] = v
    elif op == "del":
        st["scalars"].pop(k, None)
    elif op == "add":
        st["sets"].setdefault(k, set()).add(v)
    elif op == "rm":
        st["sets"].setdefault(k, set()).discard(v)
    elif op == "inc":
        st["counters"][k] = st["counters"].get(k, 0) + int(v)
    else:
        raise ValueError(op)
    return st


def fold(events, base=None):
    st = base if base is not None else empty_state()
    for e in events:
        apply_event(st, e)
    return st


def copy_state(st):
    return {"scalars": dict(st["scalars"]),
            "sets": {k: set(v) for k, v in st["sets"].items()},
            "counters": dict(st["counters"])}


def norm(st):
    """Postac porownywalna (puste zbiory = brak)."""
    return ({k: v for k, v in st["scalars"].items()},
            {k: sorted(v) for k, v in st["sets"].items() if v},
            {k: c for k, c in st["counters"].items()})


def items(st):
    out = set()
    for k, v in st["scalars"].items():
        out.add(("s", k, v))
    for k, vs in st["sets"].items():
        for v in vs:
            out.add(("m", k, v))
    for k, c in st["counters"].items():
        out.add(("c", k, str(c)))
    return out

# ---------------------------------------------------------------- render / parse

def render_event(e):
    if e["op"] == "set":
        s = f"[t{e['t']:04d}] SET {e['key']} = {e['val']}"
        return s + (f"  | dlaczego: {e['why']}" if e["why"] else "")
    if e["op"] == "del":
        return f"[t{e['t']:04d}] DEL {e['key']}"
    if e["op"] == "add":
        return f"[t{e['t']:04d}] ADD {e['key']} += {e['val']}"
    if e["op"] == "rm":
        return f"[t{e['t']:04d}] RM {e['key']} -= {e['val']}"
    return f"[t{e['t']:04d}] INC {e['key']} += {e['val']}"


EV_RE = re.compile(r"^\[t(\d+)\] (SET|DEL|ADD|RM|INC) (\S+)(?: (?:=|\+=|-=) (.*?))?(?:  \| dlaczego: .*)?$")


def parse_log(text):
    out = []
    for line in text.splitlines():
        m = EV_RE.match(line)
        if m:
            out.append(dict(t=int(m.group(1)), op=m.group(2).lower(), key=m.group(3), val=m.group(4) or "", why=""))
    return out


def live_whys(events):
    w = {}
    for e in events:
        if e["op"] == "set":
            w[e["key"]] = e["why"]
        elif e["op"] == "del":
            w.pop(e["key"], None)
    return w


def render_snapshot(st, t, n_events, whys=None):
    L = [f"# SNAPSHOT t={t} (zlozony z {n_events} zdarzen; pelna historia: docs/log/events.log)", "",
         "## Wartosci"]
    for k in sorted(st["scalars"]):
        w = (whys or {}).get(k)
        L.append(f"- {k} = {st['scalars'][k]}" + (f"  | dlaczego: {w}" if w else ""))
    L += ["", "## Zbiory"]
    for k in sorted(st["sets"]):
        if st["sets"][k]:
            L.append(f"- {k}: " + " | ".join(sorted(st["sets"][k])))
    L += ["", "## Liczniki"]
    for k in sorted(st["counters"]):
        L.append(f"- {k} = {st['counters'][k]}")
    return "\n".join(L) + "\n"


def parse_snapshot(text):
    st = empty_state()
    sec = None
    for line in text.splitlines():
        if line.startswith("## "):
            sec = line[3:].strip()
        elif line.startswith("- ") and sec == "Wartosci":
            k, _, v = line[2:].partition(" = ")
            st["scalars"][k] = v.split("  | dlaczego: ")[0]
        elif line.startswith("- ") and sec == "Zbiory":
            k, _, v = line[2:].partition(": ")
            st["sets"][k] = set(v.split(" | ")) if v else set()
        elif line.startswith("- ") and sec == "Liczniki":
            k, _, v = line[2:].partition(" = ")
            st["counters"][k] = int(v)
    return st


def tokens(s):
    return len(s.encode("utf-8")) // 4

# ---------------------------------------------------------------- polityki

def text_append_all(ev, t):
    return "\n".join(render_event(e) for e in ev if e["t"] <= t) + "\n"


def text_append_cap(ev, t, cap):
    lines = [render_event(e) for e in ev if e["t"] <= t]
    kept, size = [], 0
    for line in reversed(lines):          # ucinamy od NAJSTARSZYCH
        size += tokens(line + "\n") + 0
        if size > cap:
            break
        kept.append(line)
    return "\n".join(reversed(kept)) + "\n"


def text_fold(ev, t, why=False):
    sub = [e for e in ev if e["t"] <= t]
    return render_snapshot(fold(sub), t, len(sub), live_whys(sub) if why else None)


def text_fold_every(ev, t, k):
    """Snapshot do ostatniego wielokrotnosci k + surowy ogon zdarzen."""
    tc = (t // k) * k
    head = text_fold(ev, tc) if tc > 0 else ""
    tail = "\n".join(render_event(e) for e in ev if tc < e["t"] <= t)
    return head + ("\n## Ogon (zdarzenia po snapshocie)\n" + tail + "\n" if tail else "")


def read_text(text):
    """Rozbija tekst na wspolna liste 'wzmianek' w kolejnosci wystepowania.
    Zwraca (base_state_or_None, events). Snapshot = mention ze stanu; log = zdarzenia."""
    base = None
    if "## Wartosci" in text:
        snap = text.split("\n## Ogon", 1)[0]
        base = parse_snapshot(snap)
    return base, parse_log(text)


def reader_correct(text):
    base, ev = read_text(text)
    return fold(ev, copy_state(base) if base else None)


def reader_naive(text):
    """Naiwny czytelnik: zmienna = PIERWSZA wzmianka (od gory), zbiory = suma wszystkiego
    co kiedykolwiek dodano (ignoruje RM), DEL ignorowany, liczniki sumuja INC."""
    base, ev = read_text(text)
    st = copy_state(base) if base else empty_state()
    seen = set(st["scalars"])
    for e in ev:
        if e["op"] == "set":
            if e["key"] not in seen:
                st["scalars"][e["key"]] = e["val"]
                seen.add(e["key"])
        elif e["op"] == "add":
            st["sets"].setdefault(e["key"], set()).add(e["val"])
        elif e["op"] == "inc":
            st["counters"][e["key"]] = st["counters"].get(e["key"], 0) + int(e["val"])
    return st


def score(got, truth):
    gi, ti = items(got), items(truth)
    ok = len(gi & ti)
    return dict(total=len(ti), correct=ok, spurious=len(gi - ti))

# ---------------------------------------------------------------- weryfikacja

def verify(snap_state, truth, history):
    """Porownuje snapshot z prawda; zwraca liste problemow (puste = OK)."""
    probs = []
    old = {}
    for e in history:
        if e["op"] == "set":
            old.setdefault(e["key"], set()).add(e["val"])
    for k, v in truth["scalars"].items():
        if k not in snap_state["scalars"]:
            probs.append(f"BRAK: {k}")
        elif snap_state["scalars"][k] != v:
            tag = "PRZESTARZALA" if snap_state["scalars"][k] in old.get(k, ()) else "BLEDNA"
            probs.append(f"{tag} wartosc: {k}")
    for k in snap_state["scalars"]:
        if k not in truth["scalars"]:
            probs.append(f"NADMIAR (usuniete lub zmyslone): {k}")
    for k, vs in truth["sets"].items():
        for v in vs - snap_state["sets"].get(k, set()):
            probs.append(f"BRAK elementu: {k} += {v}")
    for k, vs in snap_state["sets"].items():
        for v in vs - truth["sets"].get(k, set()):
            probs.append(f"NADMIAR elementu: {k} += {v}")
    for k, c in truth["counters"].items():
        if snap_state["counters"].get(k) != c:
            probs.append(f"LICZNIK {k}: jest {snap_state['counters'].get(k)}, ma byc {c}")
    return probs

# ---------------------------------------------------------------- CLI

def table(rows):
    w = len(rows[0])
    out = ["| " + " | ".join(rows[0]) + " |",
           "|" + "|".join("---" for _ in range(w)) + "|"]
    for r in rows[1:]:
        out.append("| " + " | ".join(str(c) for c in r) + " |")
    return "\n".join(out)


def main(argv=None):
    ap = argparse.ArgumentParser()
    ap.add_argument("cmd", choices=["stats", "sizes", "compare", "snapshot", "verify", "order", "tail", "log"])
    ap.add_argument("--key")
    ap.add_argument("file", nargs="?")
    ap.add_argument("--t", type=int, default=300)
    ap.add_argument("--k", type=int, default=25)
    ap.add_argument("--why", action="store_true")
    ap.add_argument("--cap", type=int, default=1500)
    ap.add_argument("--seed", type=int, default=19)
    a = ap.parse_args(argv)
    ev = gen_events(300, a.seed)

    if a.cmd == "stats":
        st = fold(ev)
        ops = {}
        for e in ev:
            ops[e["op"]] = ops.get(e["op"], 0) + 1
        revised = {}
        for e in ev:
            if e["op"] == "set":
                revised[e["key"]] = revised.get(e["key"], 0) + 1
        over = sum(1 for c in revised.values() if c > 1)
        print(f"zdarzen: {len(ev)}, operacje: {dict(sorted(ops.items()))}")
        print(f"klucze zmiennych: {len(revised)}, nadpisanych >=2x: {over}, nadpisan lacznie: "
              f"{sum(c - 1 for c in revised.values())}")
        print(f"stan koncowy: {len(st['scalars'])} zmiennych, "
              f"{sum(len(v) for v in st['sets'].values())} elem. zbiorow, {len(st['counters'])} liczniki")
        print(f"log w calosci: {tokens(text_append_all(ev, a.t))} tok., "
              f"snapshot: {tokens(text_fold(ev, a.t))} tok.")
    elif a.cmd == "sizes":
        rows = [["t", "append_all tok", f"append_cap({a.cap}) tok", "fold tok", f"fold_every({a.k}) tok",
                 "stan: zm./elem./licz."]]
        for t in range(25, 301, 25):
            st = fold([e for e in ev if e["t"] <= t])
            rows.append([t, tokens(text_append_all(ev, t)), tokens(text_append_cap(ev, t, a.cap)),
                         tokens(text_fold(ev, t)), tokens(text_fold_every(ev, t, a.k)),
                         f"{len(st['scalars'])}/{sum(len(v) for v in st['sets'].values())}/{len(st['counters'])}"])
        print(table(rows))
    elif a.cmd == "compare":
        truth = fold([e for e in ev if e["t"] <= a.t])
        pol = [("append_all", text_append_all(ev, a.t)),
               (f"append_cap({a.cap})", text_append_cap(ev, a.t, a.cap)),
               ("append_cap(500)", text_append_cap(ev, a.t, 500)),
               ("fold", text_fold(ev, a.t)),
               ("fold+dlaczego", text_fold(ev, a.t, why=True)),
               (f"fold_every({a.k})", text_fold_every(ev, a.t, a.k))]
        rows = [["polityka", "tok.", "prawda: elem.", "czyt. poprawny: ok", "spurious",
                 "czyt. naiwny: ok", "spurious"]]
        for name, text in pol:
            c = score(reader_correct(text), truth)
            n = score(reader_naive(text), truth)
            rows.append([name, tokens(text), c["total"], f"{c['correct']} ({100 * c['correct'] // c['total']}%)",
                         c["spurious"], f"{n['correct']} ({100 * n['correct'] // n['total']}%)", n["spurious"]])
        print(f"t={a.t}")
        print(table(rows))
    elif a.cmd == "snapshot":
        sys.stdout.write(text_fold(ev, a.t, a.why))
    elif a.cmd == "verify":
        with open(a.file, encoding="utf-8") as f:
            snap = parse_snapshot(f.read())
        hist = [e for e in ev if e["t"] <= a.t]
        probs = verify(snap, fold(hist), hist)
        if probs:
            for p in probs:
                print("BLAD:", p)
            print(f"{len(probs)} problemow")
            return 1
        print("OK: snapshot zgodny z logiem")
    elif a.cmd == "log":
        for e in ev:
            if e["t"] <= a.t and (a.key is None or e["key"] == a.key):
                print(render_event(e))
    elif a.cmd == "tail":
        # srednia po wszystkich t=1..300: rozmiar i dokladnosc czytelnika naiwnego przy snapshot+ogon
        rows = [["polityka", "sr. tok.", "max tok.", "naiwny: sr. dokladnosc", "poprawny: sr. dokladnosc"]]
        for name, fn in [("fold (co zdarzenie)", lambda t: text_fold(ev, t))] + \
                [(f"fold_every({k})", (lambda kk: lambda t: text_fold_every(ev, t, kk))(k)) for k in (5, 10, 25, 50, 100)] + \
                [("append_all", lambda t: text_append_all(ev, t))]:
            toks, accn, accc = [], [], []
            for t in range(10, 301):
                truth = fold([e for e in ev if e["t"] <= t])
                txt = fn(t)
                toks.append(tokens(txt))
                tot = len(items(truth))
                accn.append(score(reader_naive(txt), truth)["correct"] / tot)
                accc.append(score(reader_correct(txt), truth)["correct"] / tot)
            rows.append([name, sum(toks) // len(toks), max(toks), f"{100 * sum(accn) / len(accn):.1f}%",
                         f"{100 * sum(accc) / len(accc):.1f}%"])
        print("t = 10..300")
        print(table(rows))
    elif a.cmd == "order":
        sub = list(ev)
        r = random.Random(7)
        r.shuffle(sub)
        truth = fold(ev)
        raw = fold(sub)
        srt = fold(sorted(sub, key=lambda e: e["t"]))
        d_raw = len(items(raw) ^ items(truth))
        d_srt = len(items(srt) ^ items(truth))
        print(f"zdarzenia przemieszane (seed 7): roznica wzgledem prawdy bez sortowania: {d_raw} elem., "
              f"po sortowaniu po t: {d_srt}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
