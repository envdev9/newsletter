#!/usr/bin/env python3
"""ctxdedup.py - powtorzone odczyty plikow w kontekscie: dedupikacja PRZY ZAPISIE vs RETROAKTYWNA.

Pytanie: agent czyta ten sam plik wiele razy (po edycji, po testach, "dla pewnosci"). Kazdy odczyt
to pelna kopia w kontekscie. Co z tym zrobic - i ile kosztuje kazda odpowiedz, gdy uwzglednimy
prompt cache (zmiana historii niszczy prefiks)?

Sesja jest SKRYPTOWANA, ale operuje na PRAWDZIWYCH plikach (fixture/), prawdziwych edycjach i
prawdziwym uruchomieniu testow (subprocess). Zaden model nie jest uruchamiany: to nie jest pomiar
zachowania modelu, tylko pomiar tego, co trafia do kontekstu przy danej polityce.

Polityki (tylko ksztalt tego, co zwraca narzedzie / co zostaje w historii):
  none     - kazdy odczyt = pelna tresc, historia nietknieta (baseline)
  retro    - po nowym odczycie/edycji pliku stare odczyty tego pliku sa ZASTEPOWANE stubem
             (mutacja historii); stare wyniki testow tez
  append   - historia nigdy nie jest mutowana; narzedzie odczytu zwraca: stub "bez zmian od tury N",
             albo unified diff wzgledem ostatniej wersji widzianej w kontekscie, albo pelny plik
             (gdy diff nie oplaca sie)
  append+  - jak append, ale wyniki testow identyczne z poprzednimi tez jako stub

Uzycie:  python3 -B ctxdedup.py run | trace | verify | sweep | cache | show <polityka>
"""
import difflib
import hashlib
import os
import re
import shutil
import subprocess
import sys
import tempfile

HERE = os.path.dirname(os.path.abspath(__file__))
FIXTURE = os.path.join(HERE, "fixture")
BASE_TOKENS = 8000          # zalozenie: staly prefiks (system + narzedzia + CLAUDE.md), jak w #15
CACHE_READ, CACHE_WRITE = 0.10, 1.25   # mnozniki Z PAMIECI autora - niezweryfikowane


def tok(text):
    """Tokeny = bajty/4 (jak w calej rubryce)."""
    return (len(text.encode("utf-8")) + 3) // 4


# ----------------------------------------------------------------------------- diff
def make_diff(old, new, context=2):
    a = old.splitlines(keepends=True)
    b = new.splitlines(keepends=True)
    return "".join(difflib.unified_diff(a, b, "a", "b", n=context, lineterm="\n"))


_HUNK = re.compile(r"^@@ -(\d+)(?:,(\d+))? \+(\d+)(?:,(\d+))? @@")


def apply_diff(old, diff):
    """Stosuje unified diff z make_diff do `old`. Zglasza ValueError przy niezgodnosci kontekstu."""
    src = old.splitlines(keepends=True)
    out, pos = [], 0
    lines = diff.splitlines(keepends=True)
    i = 0
    while i < len(lines):
        m = _HUNK.match(lines[i])
        if not m:
            i += 1
            continue
        start = int(m.group(1))
        count = 1 if m.group(2) is None else int(m.group(2))
        start = start if count == 0 else start - 1
        if start < pos:
            raise ValueError("hunki nachodza na siebie")
        out.extend(src[pos:start])
        pos = start
        i += 1
        while i < len(lines) and not lines[i].startswith("@@"):
            ln = lines[i]
            tag, body = ln[:1], ln[1:]
            if tag == " ":
                if pos >= len(src) or src[pos] != body:
                    raise ValueError("kontekst nie pasuje")
                out.append(body)
                pos += 1
            elif tag == "-":
                if pos >= len(src) or src[pos] != body:
                    raise ValueError("usuwana linia nie pasuje")
                pos += 1
            elif tag == "+":
                out.append(body)
            elif ln.startswith("\\"):
                pass
            i += 1
    out.extend(src[pos:])
    return "".join(out)


# ----------------------------------------------------------------------------- sesja
# (rodzaj, sciezka, argumenty) - skrypt zadania "zmien k w RRF, zobacz testy, posprzataj".
SCRIPT = [
    ("read", "ctxsearch.py", None),
    ("read", "test_ctxsearch.py", None),
    ("run", "test_ctxsearch.py", None),
    ("read", "ctxsearch.py", None),                       # powtorka: "dla pewnosci"
    ("edit", "ctxsearch.py", ("def rrf(rank_lists, k=60):", "def rrf(rank_lists, k=20):")),
    ("run", "test_ctxsearch.py", None),
    ("read", "ctxsearch.py", None),                       # po edycji
    ("edit", "ctxsearch.py", ("def main(argv):", "def main(argv):\n    # uwaga: k w rrf eksperymentalnie 20")),
    ("read", "test_ctxsearch.py", None),
    ("edit", "test_ctxsearch.py", ("rrf jednej listy zachowuje kolejnosc", "rrf jednej listy zachowuje kolejnosc (k domyslne)")),
    ("run", "test_ctxsearch.py", None),
    ("read", "ctxsearch.py", None),
    ("read", "test_ctxsearch.py", None),
    ("run", "test_ctxsearch.py", None),                   # ten sam wynik co poprzedni
    ("edit", "ctxsearch.py", ("def rrf(rank_lists, k=20):", "def rrf(rank_lists, k=60):")),
    ("read", "ctxsearch.py", None),
    ("run", "test_ctxsearch.py", None),
]


def build_session(script=None, fixture=FIXTURE):
    """Wykonuje SCRIPT naprawde (edycje na kopii w tmp, testy przez subprocess) i zwraca liste krokow
    z PRAWDZIWYMI wynikami - niezaleznymi od polityki."""
    script = SCRIPT if script is None else script
    work = tempfile.mkdtemp(prefix="ctxdedup_")
    try:
        for name in ("ctxsearch.py", "test_ctxsearch.py"):
            shutil.copy(os.path.join(fixture, name), os.path.join(work, name))
        steps = []
        for kind, path, arg in script:
            full = os.path.join(work, path)
            if kind == "read":
                with open(full, encoding="utf-8") as f:
                    content = f.read()
                steps.append({"kind": "read", "path": path, "call": "Read(%s)" % path, "content": content})
            elif kind == "edit":
                old, new = arg
                with open(full, encoding="utf-8") as f:
                    content = f.read()
                if content.count(old) != 1:
                    raise RuntimeError("edycja: wzorzec musi wystapic dokladnie raz: %r (%d)" % (old, content.count(old)))
                with open(full, "w", encoding="utf-8") as f:
                    f.write(content.replace(old, new))
                steps.append({"kind": "edit", "path": path, "call": "Edit(%s, %r -> %r)" % (path, old, new),
                              "result": "The file %s has been updated." % path})
            elif kind == "run":
                p = subprocess.run([sys.executable, "-B", path], cwd=work, capture_output=True, text=True, timeout=300)
                out = (p.stdout + p.stderr).rstrip("\n") + "\n[exit %d]" % p.returncode
                steps.append({"kind": "run", "path": path, "call": "Bash(python3 -B %s)" % path, "result": out})
            else:
                raise ValueError(kind)
        # stan koncowy dysku
        final = {}
        for name in ("ctxsearch.py", "test_ctxsearch.py"):
            with open(os.path.join(work, name), encoding="utf-8") as f:
                final[name] = f.read()
        return steps, final
    finally:
        shutil.rmtree(work, ignore_errors=True)


# ----------------------------------------------------------------------------- polityki
def _stub_same(n):
    return "[plik bez zmian od odczytu w turze %d - tresc jak wyzej]" % n


def _stub_super(path):
    return "[tresc %s zastapiona: nowsza wersja nizej]" % path


def _stub_run(n):
    return "[wynik identyczny z uruchomieniem w turze %d]" % n


def simulate(steps, policy):
    """Zwraca liste migawek kontekstu: dla kazdej tury lista eventow (str), sumy tokenow zbudowane
    z prefiksu BASE. Kazdy event = {'turn','kind','path','text','full'(tresc pliku jesli odczyt)}."""
    events = []        # historia (mutowalna tylko przy retro)
    snaps = []
    last_seen = {}     # path -> (turn, content widziana w kontekscie)
    last_run = None    # (turn, text)
    for t, s in enumerate(steps, 1):
        call = {"turn": t, "kind": "call", "path": s["path"], "text": s["call"]}
        if s["kind"] == "read":
            content = s["content"]
            text, meta = content, "full"
            if policy.startswith("append"):
                seen = last_seen.get(s["path"])
                if seen is not None and seen[1] == content:
                    text, meta = _stub_same(seen[0]), "same"
                elif seen is not None:
                    d = make_diff(seen[1], content)
                    if tok(d) < 0.5 * tok(content):
                        text, meta = d, "diff"
            if policy == "retro":
                for e in events:
                    if e["kind"] == "read" and e["path"] == s["path"] and e["text"] != _stub_super(s["path"]):
                        e["text"], e["meta"] = _stub_super(s["path"]), "stub"
            res = {"turn": t, "kind": "read", "path": s["path"], "text": text, "meta": meta, "content": content}
            last_seen[s["path"]] = (t, content)
        elif s["kind"] == "edit":
            res = {"turn": t, "kind": "edit", "path": s["path"], "text": s["result"], "meta": "full"}
            if policy == "retro":
                for e in events:
                    if e["kind"] == "read" and e["path"] == s["path"] and e["text"] != _stub_super(s["path"]):
                        e["text"], e["meta"] = _stub_super(s["path"]), "stub"
        else:
            text, meta = s["result"], "full"
            if policy == "append+" and last_run and last_run[1] == s["result"]:
                text, meta = _stub_run(last_run[0]), "same"
            if policy == "retro":
                for e in events:
                    if e["kind"] == "run" and e["meta"] != "stub":
                        e["text"], e["meta"] = "[starszy wynik testow zastapiony nowszym]", "stub"
            res = {"turn": t, "kind": "run", "path": s["path"], "text": text, "meta": meta}
            last_run = (t, s["result"])
        events.append(call)
        events.append(res)
        snaps.append([(e["text"], tok(e["text"])) for e in events])
    return snaps, events


def cost_of(snaps, base=BASE_TOKENS, cache_read=CACHE_READ, cache_write=CACHE_WRITE):
    """token-tury (rozmiar kontekstu x tury) i koszt wazony cache. Model: w turze i model dostaje
    caly kontekst C_i; wspolny prefiks z C_{i-1} (liczony po eventach, rowna tresc) jest odczytem z cache,
    reszta zapisem. Pierwsza tura: baza jest 'ciepla' (czytana z cache), reszta zapis."""
    token_turns, weighted, rewritten = 0, 0.0, 0
    prev = []
    for snap in snaps:
        total = base + sum(n for _, n in snap)
        common = 0
        for (a, na), (b, nb) in zip(snap, prev):
            if a != b:
                break
            common += na
        reused = base + common
        token_turns += total
        weighted += cache_read * reused + cache_write * (total - reused)
        rewritten += total - reused
        prev = snap
    return {"token_turns": token_turns, "weighted": weighted, "rewritten": rewritten,
            "final_ctx": base + sum(n for _, n in snaps[-1])}


# ----------------------------------------------------------------------------- weryfikacja
def reconstruct(events, path):
    """Odtwarza OSTATNIA wersje `path` wylacznie z tekstu widocznego w kontekscie (pelny odczyt + diffy)."""
    cur = None
    for e in events:
        if e["kind"] != "read" or e["path"] != path:
            continue
        if e["meta"] == "full":
            cur = e["text"]
        elif e["meta"] == "diff":
            if cur is None:
                return None
            cur = apply_diff(cur, e["text"])
        elif e["meta"] == "same":
            if cur is None:
                return None
        elif e["meta"] == "stub":
            continue          # retro: stare zastapione, nowsze dalej
    return cur


def verify_policy(steps, policy):
    """Dla kazdego odczytu: czy tresc odtworzona z kontekstu == tresc, ktora dysk mial w tej turze."""
    # kontekst w turze t = symulacja tylko krokow 1..t (retro mutuje historie, wiec nie wolno
    # ucinac gotowej, koncowej historii - pozniejsze stuby nie istnialy jeszcze w turze t)
    bad = 0
    total = 0
    for t, s in enumerate(steps, 1):
        if s["kind"] != "read":
            continue
        _, prefix = simulate(steps[:t], policy)
        got = reconstruct(prefix, s["path"])
        total += 1
        if got != s["content"]:
            bad += 1
    return total, bad


def stale_tokens(events, final):
    """Tokeny pelnych kopii plikow w kontekscie, ktore sa rozne od stanu koncowego dysku."""
    n = 0
    versions = {}
    for e in events:
        if e["kind"] == "read" and e["meta"] == "full":
            versions.setdefault(e["path"], set()).add(hashlib.sha1(e["text"].encode()).hexdigest())
            if e["text"] != final[e["path"]]:
                n += tok(e["text"])
    return n, {p: len(v) for p, v in versions.items()}


# ----------------------------------------------------------------------------- polecenia
POLICIES = ["none", "retro", "append", "append+"]


def cmd_run(steps, final):
    print("sesja: %d krokow (%d odczytow, %d edycji, %d uruchomien testow), baza %d tok." % (
        len(steps), sum(s["kind"] == "read" for s in steps), sum(s["kind"] == "edit" for s in steps),
        sum(s["kind"] == "run" for s in steps), BASE_TOKENS))
    for name in sorted(final):
        print("  %-20s %6d tok. (%d bajtow)" % (name, tok(final[name]), len(final[name].encode())))
    print()
    print("| polityka | kontekst koncowy | token-tury | vs none | zapis do cache (tok.) | koszt wazony | vs none | odtworzenie odczytow | stare pelne kopie (tok.) |")
    print("|---|---|---|---|---|---|---|---|---|")
    base = None
    for p in POLICIES:
        snaps, events = simulate(steps, p)
        c = cost_of(snaps)
        if base is None:
            base = c
        tot, bad = verify_policy(steps, p)
        st, _ = stale_tokens(events, final)
        print("| %s | %d | %d | %.2fx | %d | %.0f | %.2fx | %d/%d | %d |" % (
            p, c["final_ctx"], c["token_turns"], base["token_turns"] / c["token_turns"], c["rewritten"],
            c["weighted"], base["weighted"] / c["weighted"], tot - bad, tot, st))


def cmd_trace(steps, final):
    print("| tura | krok | none | retro | append | append+ |")
    print("|---|---|---|---|---|---|")
    for t, s in enumerate(steps, 1):
        row = []
        for p in POLICIES:
            # rozmiar wyniku W MOMENCIE zwrocenia (retro zastapi go stubem dopiero pozniej)
            res = simulate(steps[:t], p)[1][-1]
            row.append("%d (%s)" % (tok(res["text"]), res["meta"]))
        print("| %d | %s %s | %s |" % (t, s["kind"], s["path"], " | ".join(row)))


def cmd_verify(steps, final):
    ok = True
    for p in POLICIES:
        tot, bad = verify_policy(steps, p)
        _, events = simulate(steps, p)
        rec = {n: reconstruct(events, n) == final[n] for n in final}
        print("%-8s odczyty odtwarzalne z kontekstu: %d/%d; stan koncowy plikow: %s" % (p, tot - bad, tot, rec))
        ok = ok and bad == 0 and all(rec.values())
    return 0 if ok else 1


def cmd_sweep(steps, final):
    """Jak kosztuje polityka przy rosnacej liczbie 'dla pewnosci' powtorzonych odczytow bez zmian."""
    print("| dodatkowych powtorzen | token-tury none | retro/none | append/none | koszt wazony none | retro/none | append/none |")
    print("|---|---|---|---|---|---|---|")
    for extra in (0, 5, 10, 20):
        script = list(SCRIPT)
        for _ in range(extra):
            script.append(("read", "ctxsearch.py", None))
        st, _ = build_session(script)
        r = {p: cost_of(simulate(st, p)[0]) for p in ("none", "retro", "append")}
        print("| %d | %d | %.2f | %.2f | %.0f | %.2f | %.2f |" % (
            extra, r["none"]["token_turns"],
            r["retro"]["token_turns"] / r["none"]["token_turns"],
            r["append"]["token_turns"] / r["none"]["token_turns"], r["none"]["weighted"],
            r["retro"]["weighted"] / r["none"]["weighted"], r["append"]["weighted"] / r["none"]["weighted"]))


def cmd_cache(steps, final):
    """Przy jakim mnozniku odczytu z cache 'retro' (mutacja historii) przestaje sie oplacac?"""
    print("| mnoznik odczytu z cache | zapis | none | retro | append | najtanszy |")
    print("|---|---|---|---|---|---|")
    snaps = {p: simulate(steps, p)[0] for p in ("none", "retro", "append")}
    for r in (1.0, 0.75, 0.5, 0.25, 0.1, 0.05):
        w = 1.0 if r == 1.0 else 1.25
        c = {p: cost_of(snaps[p], cache_read=r, cache_write=w)["weighted"] for p in snaps}
        best = min(c, key=c.get)
        print("| %.2f | %.2f | %.0f | %.0f | %.0f | %s |" % (r, w, c["none"], c["retro"], c["append"], best))


def cmd_show(steps, final, policy):
    _, events = simulate(steps, policy)
    for e in events:
        if e["kind"] == "call":
            print("T%02d > %s" % (e["turn"], e["text"]))
        else:
            first = e["text"].splitlines()[0] if e["text"] else ""
            print("T%02d < [%s] %d tok.  %s" % (e["turn"], e["meta"], tok(e["text"]), first[:90]))


def main(argv):
    if len(argv) < 2 or argv[1] not in ("run", "trace", "verify", "sweep", "cache", "show"):
        print(__doc__)
        return 2
    steps, final = build_session()
    if argv[1] == "run":
        cmd_run(steps, final)
    elif argv[1] == "trace":
        cmd_trace(steps, final)
    elif argv[1] == "verify":
        return cmd_verify(steps, final)
    elif argv[1] == "sweep":
        cmd_sweep(steps, final)
    elif argv[1] == "cache":
        cmd_cache(steps, final)
    elif argv[1] == "show":
        cmd_show(steps, final, argv[2] if len(argv) > 2 else "append")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
