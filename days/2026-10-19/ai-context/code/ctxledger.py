#!/usr/bin/env python3
"""ctxledger.py - wiszacy stub po kompakcji: ksiega "co model widzi w oknie" dla odczytow i wynikow grep.

W #21 (ctxdedup.py) narzedzie odczytu pamietalo `last_seen` i przy ponownym odczycie zwracalo stub albo diff.
Zalozenie milczace: to, na co stub wskazuje, JEST w oknie. Kompakcja (/compact lub auto) to zalozenie lamie:
stub "bez zmian od tury 3" wskazuje na tresc, ktorej juz nie ma.

Ten skrypt:
  1. wykonuje PRAWDZIWA sesje (edycje na kopii fixture, testy przez subprocess, prawdziwy grep),
  2. wstawia w nia kompakcje (okno -> podsumowanie + ogon ostatnich `keep` zdarzen),
  3. porownuje polityki obslugi `last_seen`/ksiegi po kompakcji:
       none   - zawsze pelna tresc (baseline)
       ignore - ksiega nie wie o kompakcji (zachowanie z #21)            -> wiszace stuby
       epoch  - ksiega zerowana przy kazdej kompakcji (grubo)
       last   - wpis wazny, gdy zyje OSTATNIE zdarzenie, ktore dalo tresc  -> diff bez bazy
       chain  - wpis wazny, gdy zyja WSZYSTKIE zdarzenia lancucha (pelny odczyt + diffy)
     oraz warianty chain-bez-grep / chain-tylko-grep (ile daje sam odczyt, ile sam grep),
  4. dla kazdego odczytu i kazdego grep sprawdza MECHANICZNIE, czy wynik da sie odtworzyc wylacznie
     z zywych zdarzen okna: ok / dangling (brak bazy) / wrong (zla tresc).

Zaden model nie jest uruchamiany. Kompakcja jest MODELOWANA (podsumowanie = staly tekst syntetyczny,
ogon = ostatnie `keep` zdarzen) - to nie jest opis dzialania `claude`.

Uzycie:  python3 -B ctxledger.py run | show <polityka> [keep] | sweep | verify
"""
import functools
import os
import re
import shutil
import subprocess
import sys
import tempfile

import ctxdedup
from ctxdedup import tok, make_diff, apply_diff, cost_of

HERE = os.path.dirname(os.path.abspath(__file__))
FIXTURE = os.path.join(HERE, "fixture")

# Podsumowanie kompakcji: STALY tekst syntetyczny (zalozenie: nie niesie tresci plikow). Prawdziwe
# podsumowanie modelu bywa inne - nie wiem, ile i czego zawiera.
SUMMARY = "[podsumowanie kompakcji - SYNTETYCZNE] " + (
    "zadanie: zmiana k w rrf, testy zielone, pliki ctxsearch.py i test_ctxsearch.py. " * 25)

_diff = functools.lru_cache(maxsize=None)(make_diff)

# (rodzaj, argument1, argument2) - zadanie: "sprawdz uzycia rrf, zmien k, posprzataj". BEZ kompakcji.
SCRIPT = [
    ("grep", "def ", ("ctxsearch.py",)),                                   # 1
    ("grep", "rrf", ("ctxsearch.py", "test_ctxsearch.py")),                # 2
    ("read", "ctxsearch.py", None),                                        # 3
    ("grep", "def ", ("ctxsearch.py",)),                                   # 4  identyczny z 1
    ("grep", "^(def|class) ", ("ctxsearch.py",)),                          # 5  inny zbior, czesciowo wspolny
    ("edit", "ctxsearch.py", ("def rrf(rank_lists, k=60):", "def rrf(rank_lists, k=20):")),   # 6
    ("grep", "rrf", ("ctxsearch.py", "test_ctxsearch.py")),                # 7  po edycji (zmieniona 1 linia)
    ("run", "test_ctxsearch.py", None),                                    # 8
    ("edit", "ctxsearch.py", ("def tok(obj):", "# pomocnicza: szacunek tokenow\ndef tok(obj):")),  # 9  PRZESUWA numery linii
    ("grep", "rrf", ("ctxsearch.py", "test_ctxsearch.py")),                # 10 numery linii przesuniete
    ("read", "ctxsearch.py", None),                                        # 11
    ("read", "ctxsearch.py", None),                                        # 12 (tu domyslnie wpada kompakcja: przed krokiem 12)
    ("grep", "rrf", ("ctxsearch.py", "test_ctxsearch.py")),                # 13
    ("read", "test_ctxsearch.py", None),                                   # 14
    ("edit", "ctxsearch.py", ("def rrf(rank_lists, k=20):", "def rrf(rank_lists, k=60):")),   # 15
    ("read", "ctxsearch.py", None),                                        # 16
    ("grep", "rrf", ("ctxsearch.py", "test_ctxsearch.py")),                # 17
    ("run", "test_ctxsearch.py", None),                                    # 18
    ("read", "test_ctxsearch.py", None),                                   # 19
]
COMPACT_AT = 11      # kompakcja po 11 krokach (przed krokiem 12)
KEEP_SCENARIOS = (0, 6)

_GREP_LINE = re.compile(r"^(.*?):(\d+):(.*)$")


# ----------------------------------------------------------------------------- sesja (prawdziwa)
def build_session(script=None, fixture=FIXTURE):
    script = SCRIPT if script is None else script
    work = tempfile.mkdtemp(prefix="ctxledger_")
    try:
        for name in ("ctxsearch.py", "test_ctxsearch.py"):
            shutil.copy(os.path.join(fixture, name), os.path.join(work, name))
        steps = []
        for kind, a, b in script:
            if kind == "read":
                with open(os.path.join(work, a), encoding="utf-8") as f:
                    steps.append({"kind": "read", "path": a, "call": "Read(%s)" % a, "content": f.read()})
            elif kind == "edit":
                full = os.path.join(work, a)
                with open(full, encoding="utf-8") as f:
                    content = f.read()
                if content.count(b[0]) != 1:
                    raise RuntimeError("edycja: wzorzec musi wystapic dokladnie raz: %r" % (b[0],))
                with open(full, "w", encoding="utf-8") as f:
                    f.write(content.replace(b[0], b[1]))
                steps.append({"kind": "edit", "path": a, "call": "Edit(%s)" % a,
                              "result": "The file %s has been updated." % a})
            elif kind == "run":
                p = subprocess.run([sys.executable, "-B", a], cwd=work, capture_output=True, text=True, timeout=300)
                out = (p.stdout + p.stderr).rstrip("\n") + "\n[exit %d]" % p.returncode
                steps.append({"kind": "run", "path": a, "call": "Bash(python3 -B %s)" % a, "result": out})
            elif kind == "grep":
                cmd = ["grep", "--color=never", "-H", "-n", "-E", a] + list(b)
                p = subprocess.run(cmd, cwd=work, capture_output=True, text=True, timeout=60)
                lines = []
                for ln in p.stdout.splitlines():
                    m = _GREP_LINE.match(ln)
                    if not m:
                        raise RuntimeError("nieparsowalna linia grep: %r" % ln)
                    lines.append((m.group(1), int(m.group(2)), m.group(3)))
                steps.append({"kind": "grep", "pattern": a, "files": list(b),
                              "call": "Bash(grep -Hn -E %r %s)" % (a, " ".join(b)), "lines": lines})
            else:
                raise ValueError(kind)
        return steps
    finally:
        shutil.rmtree(work, ignore_errors=True)


# ----------------------------------------------------------------------------- polityki
class Policy:
    def __init__(self, name, reads, grep, mode):
        self.name, self.reads, self.grep, self.mode = name, reads, grep, mode


POLICIES = [
    Policy("none", False, False, "ignore"),
    Policy("ignore", True, True, "ignore"),
    Policy("epoch", True, True, "epoch"),
    Policy("last", True, True, "last"),
    Policy("chain", True, True, "chain"),
    Policy("chain-bez-grep", True, False, "chain"),
    Policy("chain-tylko-grep", False, True, "chain"),
]
POL = {p.name: p for p in POLICIES}


def fmt_grep(lines):
    return "\n".join("%s:%d:%s" % l for l in lines) if lines else "(brak dopasowan)"


def omit_header(omitted, total):
    per = {}
    for p, l in omitted:
        per.setdefault(p, []).append(str(l))
    body = "; ".join("%s: %s" % (p, ",".join(v)) for p, v in sorted(per.items()))
    return "[pominieto %d z %d linii - widoczne wyzej, numery: %s]" % (len(omitted), total, body)


def check_read(events, path, truth):
    """Odtwarza ostatnia wersje `path` z ZYWYCH zdarzen i porownuje z prawda."""
    cur, state = None, "dangling"      # state: co mamy PO ostatnim zdarzeniu; pelny odczyt czyści wcześniejsze braki
    for e in events:
        if e["kind"] != "read" or e["path"] != path:
            continue
        if e["meta"] == "full":
            cur, state = e["text"], "ok"
        elif e["meta"] == "diff":
            if cur is None:
                state = "dangling"
                continue
            try:
                cur, state = apply_diff(cur, e["text"]), "ok"
            except ValueError:
                cur, state = None, "wrong"
        elif e["meta"] == "same":
            if cur is None:
                state = "dangling"
    if state != "ok":
        return state
    return "ok" if cur == truth else "wrong"


def check_grep(events, ev, truth_lines):
    known = {}
    for e in events:
        if e is ev:
            break
        if e["kind"] == "grep":
            for p, l, t in e["shown"]:
                known[(p, l)] = t
    got = set((p, l, t) for p, l, t in ev["shown"])
    for p, l in ev["omitted"]:
        if (p, l) not in known:
            return "dangling"
        got.add((p, l, known[(p, l)]))
    return "ok" if got == set(truth_lines) else "wrong"


def simulate(steps, pol, keep=0, compact_at=COMPACT_AT):
    """Zwraca (snaps, events, stats). Kompakcja po `compact_at` krokach: okno = [podsumowanie] + ogon `keep` zdarzen."""
    events, snaps = [], []
    nid = [0]
    last_seen = {}      # path -> {eid, content, chain, turn}
    gl = {}             # (path, lineno) -> {text, eid}
    stats = {"read": {"ok": 0, "dangling": 0, "wrong": 0}, "grep": {"ok": 0, "dangling": 0, "wrong": 0},
             "omitted_lines": 0, "diff_reads": 0, "same_reads": 0}

    def new_id():
        nid[0] += 1
        return nid[0]

    def live_ids():
        return set(e["id"] for e in events)

    def valid(entry):
        if pol.mode in ("ignore", "epoch"):
            return True
        live = live_ids()
        if pol.mode == "last":
            return entry["eid"] in live
        return all(c in live for c in entry["chain"])

    turn = 0
    for idx, s in enumerate(steps):
        if idx == compact_at:
            tail = [e for e in events if e["kind"] != "summary"]
            tail = tail[len(tail) - keep:] if keep > 0 else []
            events = [{"id": new_id(), "turn": 0, "kind": "summary", "text": SUMMARY, "meta": "summary"}] + tail
            if pol.mode == "epoch":
                last_seen.clear()
                gl.clear()
        turn += 1
        call = {"id": new_id(), "turn": turn, "kind": "call", "text": s["call"], "meta": "call"}
        events.append(call)
        res = {"id": new_id(), "turn": turn, "kind": s["kind"], "path": s.get("path"), "meta": "full"}
        if s["kind"] == "read":
            content = s["content"]
            text, meta = content, "full"
            seen = last_seen.get(s["path"])
            if pol.reads and seen is not None and valid(seen):
                if seen["content"] == content:
                    text, meta = ctxdedup._stub_same(seen["turn"]), "same"
                else:
                    d = _diff(seen["content"], content)
                    if tok(d) < 0.5 * tok(content):
                        text, meta = d, "diff"
            res.update(text=text, meta=meta)
            if meta == "full":
                last_seen[s["path"]] = {"eid": res["id"], "content": content, "chain": [res["id"]], "turn": turn}
            elif meta == "diff":
                last_seen[s["path"]] = {"eid": res["id"], "content": content,
                                        "chain": seen["chain"] + [res["id"]], "turn": turn}
                stats["diff_reads"] += 1
            else:
                stats["same_reads"] += 1
            events.append(res)
            stats["read"][check_read(events, s["path"], content)] += 1
        elif s["kind"] == "grep":
            lines = s["lines"]
            omitted, shown = [], []
            for p, l, t in lines:
                g = gl.get((p, l))
                if pol.grep and g is not None and g["text"] == t and valid(g):
                    omitted.append((p, l))
                else:
                    shown.append((p, l, t))
            full_text = fmt_grep(lines)
            text = full_text
            if omitted:
                cand = omit_header(omitted, len(lines)) + ("\n" + fmt_grep(shown) if shown else "")
                if tok(cand) < tok(full_text):
                    text = cand
                else:
                    omitted, shown = [], list(lines)
            else:
                shown = list(lines)
            for p, l, t in shown:
                gl[(p, l)] = {"text": t, "eid": res["id"], "chain": [res["id"]]}
            res.update(text=text, shown=shown, omitted=omitted)
            stats["omitted_lines"] += len(omitted)
            events.append(res)
            stats["grep"][check_grep(events, res, lines)] += 1
        else:
            res.update(text=s["result"])
            events.append(res)
        snaps.append([(e["text"], tok(e["text"])) for e in events])
    return snaps, events, stats


def summarize(steps, pol, keep, compact_at=COMPACT_AT):
    snaps, events, st = simulate(steps, pol, keep, compact_at)
    c = cost_of(snaps)
    bad = st["read"]["dangling"] + st["read"]["wrong"] + st["grep"]["dangling"] + st["grep"]["wrong"]
    return c, st, bad


# ----------------------------------------------------------------------------- polecenia
def cmd_run(steps):
    print("sesja: %d krokow (%d odczytow, %d grep, %d edycji, %d testow); kompakcja przed krokiem %d; podsumowanie %d tok. (zalozenie)" % (
        len(steps), sum(s["kind"] == "read" for s in steps), sum(s["kind"] == "grep" for s in steps),
        sum(s["kind"] == "edit" for s in steps), sum(s["kind"] == "run" for s in steps), COMPACT_AT + 1, tok(SUMMARY)))
    for keep in KEEP_SCENARIOS:
        print()
        print("ogon po kompakcji: %d zdarzen" % keep)
        print("| polityka | token-tury | vs none | zapis do cache (tok.) | koszt wazony | vs none | odczyty ok/dangl/wrong | grep ok/dangl/wrong | diffy | stuby | pominiete linie grep |")
        print("|---|---|---|---|---|---|---|---|---|---|---|")
        base = None
        for pol in POLICIES:
            c, st, _ = summarize(steps, pol, keep)
            if base is None:
                base = c
            r, g = st["read"], st["grep"]
            print("| %s | %d | %.2fx | %d | %.0f | %.2fx | %d/%d/%d | %d/%d/%d | %d | %d | %d |" % (
                pol.name, c["token_turns"], base["token_turns"] / c["token_turns"], c["rewritten"], c["weighted"],
                base["weighted"] / c["weighted"], r["ok"], r["dangling"], r["wrong"], g["ok"], g["dangling"], g["wrong"],
                st["diff_reads"], st["same_reads"], st["omitted_lines"]))


def cmd_show(steps, name, keep):
    pol = POL[name]
    _, events, _ = simulate(steps, pol, keep)
    print("polityka %s, ogon %d zdarzen - ZYWE zdarzenia okna na koncu sesji:" % (name, keep))
    for e in events:
        first = e["text"].splitlines()[0] if e["text"] else ""
        print("T%02d [%s] %5d tok.  %s" % (e["turn"], e["meta"], tok(e["text"]), first[:100]))


def sweep_table(steps, positions, keeps):
    rows = []
    for pol in POLICIES:
        combos = fail_combos = bad_total = checks = 0
        ratios = []
        for pos in positions:
            for keep in keeps:
                c, st, bad = summarize(steps, pol, keep, pos)
                base, _, _ = summarize(steps, POL["none"], keep, pos)
                combos += 1
                fail_combos += 1 if bad else 0
                bad_total += bad
                checks += sum(st["read"].values()) + sum(st["grep"].values())
                ratios.append(c["weighted"] / base["weighted"])
        rows.append((pol.name, combos, fail_combos, bad_total, checks, sum(ratios) / len(ratios)))
    return rows


def cmd_sweep(steps):
    positions = list(range(1, len(steps)))
    keeps = (0, 2, 4, 6, 8, 12)
    print("kompakcja w KAZDYM miejscu sesji (po kroku 1..%d) x ogon %s zdarzen" % (len(steps) - 1, list(keeps)))
    print("| polityka | kombinacji | z bledem | bledne wyniki (suma) | sprawdzen | sredni koszt wazony / none |")
    print("|---|---|---|---|---|---|")
    for n, combos, fc, bad, checks, ratio in sweep_table(steps, positions, keeps):
        print("| %s | %d | %d | %d | %d | %.2f |" % (n, combos, fc, bad, checks, ratio))


def cmd_verify(steps):
    """Kod wyjscia 0 tylko jesli polityki bezpieczne (none, epoch, last*, chain*) nie maja bledow tam, gdzie
    maja miec zero - a `ignore` ma je miec (inaczej eksperyment nic nie pokazuje)."""
    positions = list(range(1, len(steps)))
    keeps = (0, 2, 4, 6, 8, 12)
    rows = {r[0]: r for r in sweep_table(steps, positions, keeps)}
    for n in ("none", "epoch", "chain", "chain-bez-grep", "chain-tylko-grep"):
        print("%-17s bledne wyniki: %d" % (n, rows[n][3]))
    print("%-17s bledne wyniki: %d (oczekiwane > 0)" % ("ignore", rows["ignore"][3]))
    print("%-17s bledne wyniki: %d (oczekiwane > 0)" % ("last", rows["last"][3]))
    ok = all(rows[n][3] == 0 for n in ("none", "epoch", "chain", "chain-bez-grep", "chain-tylko-grep"))
    ok = ok and rows["ignore"][3] > 0 and rows["last"][3] > 0
    print("OK" if ok else "BLAD")
    return 0 if ok else 1


def main(argv):
    if len(argv) < 2 or argv[1] not in ("run", "show", "sweep", "verify"):
        print(__doc__)
        return 2
    steps = build_session()
    if argv[1] == "run":
        cmd_run(steps)
    elif argv[1] == "show":
        cmd_show(steps, argv[2] if len(argv) > 2 else "chain", int(argv[3]) if len(argv) > 3 else 6)
    elif argv[1] == "sweep":
        cmd_sweep(steps)
    elif argv[1] == "verify":
        return cmd_verify(steps)
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
