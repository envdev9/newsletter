#!/usr/bin/env python3
"""lsdelta.py - powtorzone wyniki `ls` w kontekscie: stub / delta / stan katalogu / "ufam zdarzeniom".

Kontynuacja #21 (powtorzone odczyty plikow) i #26 (wiszacy stub po kompakcji). Tym razem: LISTINGI KATALOGOW.
Agent wola `ls` wielokrotnie (przed i po edycjach, po buildzie), a kazdy wynik to pelna kopia w kontekscie.

Sesja jest SKRYPTOWANA, ale operuje na PRAWDZIWYM katalogu w /tmp i PRAWDZIWYM `ls` (GNU coreutils; LC_ALL=C).
Zaden model nie jest uruchamiany: mierzymy, CO trafia do kontekstu i czy da sie z tego tekstu odtworzyc listing.

Polityki (wszystkie "append-only": historia nigdy nie jest mutowana, wiec prefiks cache zostaje):
  none     - zawsze pelny wynik (baseline)
  same     - identyczny z poprzednim wynikiem TEGO SAMEGO polecenia -> stub; inaczej pelny
  setdiff  - delta wzgledem poprzedniego wyniku tego samego polecenia, porownanie CALYCH LINII (zmiana pliku = -stara +nowa)
  namekey  - jak setdiff, ale klucz = nazwa pliku (zmiana atrybutow = jedna linia `~`)
  state    - jeden "stan katalogu" z KAZDEGO wariantu ls (`-1A` jest rzutem `-lA`): delta liczona wzgledem tego,
             co model juz wie, takze z innego wariantu polecenia
  evented  - jak state, ale NIE WYWOLUJE ls, jesli agent nie zrobil wlasnej operacji na plikach (ufa zdarzeniom);
             nie widzi zmian zrobionych przez zewnetrzny proces (build)

Uzycie:  python3 -B lsdelta.py run | show <polityka> | sweep | verify | demo
"""
import calendar
import hashlib
import os
import shutil
import subprocess
import sys
import tempfile

ENV = {"LC_ALL": "C", "TZ": "UTC", "PATH": os.environ.get("PATH", "")}
T0 = calendar.timegm((2026, 10, 1, 10, 0, 0))     # stala data modyfikacji plikow (deterministyczny `ls -l`)
CACHE_READ, CACHE_WRITE = 0.10, 1.25              # mnozniki Z PAMIECI autora (jak w #21) - niezweryfikowane
POLICIES = ["none", "same", "setdiff", "namekey", "state", "evented"]
TOTAL = "\0total"


def tok(text):
    """Tokeny = bajty/4 (jak w calej rubryce)."""
    return (len(text.encode("utf-8", "surrogateescape")) + 3) // 4


# ----------------------------------------------------------------------------- prawdziwy ls
def run_ls(kind, d, cwd):
    if kind == "1A":
        args = ["ls", "-1A", d]
    else:  # lA: bez wlasciciela i grupy (-o -g), data w stalym formacie
        args = ["ls", "-lAog", "--time-style=long-iso", d]
    r = subprocess.run(args, cwd=cwd, env=ENV, capture_output=True, check=True)
    text = r.stdout.decode("utf-8", "surrogateescape")
    return text.splitlines()


def name_of(line):
    """Nazwa pliku z linii `ls -lAog --time-style=long-iso` (perm links size date time name)."""
    if line.startswith("total "):
        return TOTAL
    return line.split(None, 5)[5]


# ----------------------------------------------------------------------------- "to, co model widzi w oknie"
class Window:
    """Stan wiedzy modelu o listingach, budowany WYLACZNIE z tekstu wynikow (parsowanie stubow/delt)."""

    def __init__(self, policy):
        self.policy = policy
        self.stateful = policy in ("state", "evented")
        self.by_name = policy in ("namekey", "state", "evented")
        self.views = {}      # (kind, d) -> {klucz: linia}                (tryby per-polecenie)
        self.state = {}      # d -> {nazwa: linia | None}                 (tryby state/evented)
        self.turn = {}       # klucz (kind,d) lub d -> tura ostatniej aktualizacji

    def key(self, line, kind):
        return name_of(line) if (self.by_name and kind == "lA") else line

    def apply(self, kind, d, text, turn):
        lines = text.split("\n") if text else []
        head = lines[0] if lines and lines[0].startswith("[ls ") and lines[0].endswith("]") else None
        slot = d if self.stateful else (kind, d)
        if head and ("identyczny" in head or "nie wykonano" in head):
            return
        if head:       # delta
            body = lines[1:]
            if self.stateful:
                st = self.state[d]
                for ln in body:
                    op, rest = ln[0], ln[1:]
                    if kind == "1A":
                        if op == "+":
                            st.setdefault(rest, None)
                        elif op == "-":
                            st.pop(rest, None)
                    else:
                        if op in "+~":
                            st[name_of(rest)] = rest
                        elif op == "-":
                            st.pop(rest, None)
            else:
                v = self.views[(kind, d)]
                for ln in body:
                    op, rest = ln[0], ln[1:]
                    if op in "+~":
                        v[self.key(rest, kind)] = rest
                    elif op == "-":
                        v.pop(rest if self.by_name else rest, None)
        else:          # pelny wynik
            if self.stateful:
                old = self.state.get(d, {})
                if kind == "1A":
                    self.state[d] = {n: old.get(n) for n in lines}
                else:
                    self.state[d] = {name_of(l): l for l in lines}
            else:
                self.views[(kind, d)] = {self.key(l, kind): l for l in lines}
        self.turn[slot] = turn

    def known(self, kind, d):
        return (d in self.state) if self.stateful else ((kind, d) in self.views)

    def answer(self, kind, d):
        """Listing odtworzony z okna (posortowany) albo None, gdy czegos brakuje."""
        if self.stateful:
            st = self.state.get(d)
            if st is None:
                return None
            if kind == "1A":
                return sorted(n for n in st if n != TOTAL)
            if any(v is None for v in st.values()):
                return None
            return sorted(st.values())
        v = self.views.get((kind, d))
        return None if v is None else sorted(v.values())


# ----------------------------------------------------------------------------- budowanie odpowiedzi narzedzia
def _delta_text(kind, d, flag, turn, adds, chgs, rems, same_name_keys):
    head = f"[ls {flag} {d}: delta wzgledem tury {turn}: +{len(adds)} ~{len(chgs)} -{len(rems)}; reszta jak w tej turze]"
    body = ["+" + a for a in adds] + ["~" + c for c in chgs] + ["-" + r for r in rems]
    return "\n".join([head] + body)


def respond(policy, win, kind, d, truth, turn):
    """Zwraca tekst wyniku narzedzia dla polecenia (kind,d), znajac prawdziwy wynik `truth` (lista linii)."""
    flag = "-1A" if kind == "1A" else "-lA"
    full = "\n".join(truth)
    if policy == "none" or not win.known(kind, d):
        return full
    last = win.turn.get(d if win.stateful else (kind, d), 0)
    stub = f"[ls {flag} {d}: identyczny z wynikiem z tury {last}]"
    if policy == "same":
        cur = sorted(truth)
        return stub if cur == win.answer(kind, d) else full
    if policy in ("setdiff", "namekey"):
        key = (lambda l: name_of(l)) if (policy == "namekey" and kind == "lA") else (lambda l: l)
        old = win.views[(kind, d)]
        new = {key(l): l for l in truth}
        adds = [new[k] for k in new if k not in old]
        chgs = [new[k] for k in new if k in old and old[k] != new[k]]
        rems = [k for k in old if k not in new]           # setdiff: k = cala linia; namekey: nazwa
    else:  # state / evented
        st = win.state[d]
        if kind == "1A":
            old_names = {n for n in st if n != TOTAL}
            adds = [n for n in truth if n not in old_names]
            chgs = []
            rems = [n for n in old_names if n not in set(truth)]
        else:
            new = {name_of(l): l for l in truth}
            adds = [new[n] for n in new if n not in st]
            chgs = [new[n] for n in new if n in st and st[n] != new[n]]
            rems = [n for n in st if n not in new]
    if not (adds or chgs or rems):
        return stub
    text = _delta_text(kind, d, flag, last, adds, chgs, rems, None)
    return text if tok(text) < tok(full) else full


def skipped_text(kind, d, win):
    flag = "-1A" if kind == "1A" else "-lA"
    return f"[ls {flag} {d}: bez zmian od tury {win.turn.get(d, 0)} (polecenia nie wykonano)]"


# ----------------------------------------------------------------------------- sesja (prawdziwy system plikow)
def make_content(i):
    return "// modul %d\n" % i + ("x = %d;\n" % i) * (3 + (i * 7) % 29)


def setup(root, n):
    src, tests = os.path.join(root, "src"), os.path.join(root, "tests")
    os.makedirs(src)
    os.makedirs(tests)
    names = ["Mod%03d.cs" % i for i in range(1, n + 1)] + ["Mod 000 notes.md", ".editorconfig"]
    for i, nm in enumerate(names):
        write(os.path.join(src, nm), make_content(i), T0)
    for i in range(1, 21):
        write(os.path.join(tests, "ModTests%02d.cs" % i), make_content(100 + i), T0)


def write(path, content, mtime):
    with open(path, "w", encoding="utf-8") as f:
        f.write(content)
    os.utime(path, (mtime, mtime))


def minute(i):
    return T0 + 60 * (10 + 3 * i)


def build_script(n):
    return [
        {"op": "ls", "kind": "1A", "dir": "src"},
        {"op": "ls", "kind": "lA", "dir": "src"},
        {"op": "ls", "kind": "lA", "dir": "tests"},
        {"op": "edit", "file": "src/Mod007.cs"},
        {"op": "ls", "kind": "lA", "dir": "src"},
        {"op": "create", "dir": "src", "names": ["Mod%03d.cs" % (n + k) for k in (1, 2, 3)]},
        {"op": "ls", "kind": "1A", "dir": "src"},
        {"op": "ls", "kind": "lA", "dir": "src"},
        {"op": "external", "dir": "src", "names": ["Mod.g.cs", "Mod.generated.cs"]},   # build: agent NIE wie co powstalo
        {"op": "ls", "kind": "1A", "dir": "src"},
        {"op": "delete", "dir": "src", "names": ["Mod010.cs", "Mod011.cs"]},
        {"op": "rename", "dir": "src", "old": "Mod020.cs", "new": "Mod020.old.cs"},
        {"op": "ls", "kind": "1A", "dir": "src"},
        {"op": "ls", "kind": "lA", "dir": "src"},
        {"op": "edit_same", "file": "src/Mod007.cs"},      # ten sam rozmiar i ta sama minuta mtime
        {"op": "ls", "kind": "lA", "dir": "src"},
        {"op": "ls", "kind": "lA", "dir": "tests"},
    ]


def do_fs(root, step, i):
    """Wykonuje operacje na plikach; zwraca (nazwy_zmienione?, atrybuty_zmienione?, znana_agentowi?)."""
    op = step["op"]
    if op == "edit":
        p = os.path.join(root, step["file"])
        with open(p, "a", encoding="utf-8") as f:
            f.write("// dopisana linia po edycji\n")
        os.utime(p, (minute(i), minute(i)))
        return False, True, True
    if op == "edit_same":
        p = os.path.join(root, step["file"])
        st = os.stat(p)
        with open(p, "r", encoding="utf-8") as f:
            data = f.read()
        before = hashlib.sha256(data.encode()).hexdigest()
        new = data.replace("dopisana", "zmienion", 1)
        assert len(new) == len(data)
        with open(p, "w", encoding="utf-8") as f:
            f.write(new)
        os.utime(p, (st.st_mtime, st.st_mtime))
        step["hash_before"] = before
        step["hash_after"] = hashlib.sha256(new.encode()).hexdigest()
        return False, True, True
    if op in ("create", "external"):
        for nm in step["names"]:
            write(os.path.join(root, step["dir"], nm), make_content(len(nm)), minute(i))
        return True, True, op == "create"
    if op == "delete":
        for nm in step["names"]:
            os.remove(os.path.join(root, step["dir"], nm))
        return True, True, True
    if op == "rename":
        os.rename(os.path.join(root, step["dir"], step["old"]), os.path.join(root, step["dir"], step["new"]))
        return True, True, True
    raise ValueError(op)


def play(policy, n=150, script=None):
    """Odgrywa sesje dla polityki. Zwraca liste zdarzen i podsumowanie."""
    root = tempfile.mkdtemp(prefix="lsdelta-")
    try:
        setup(root, n)
        script = [dict(s) for s in (script or build_script(n))]
        win = Window(policy)
        names_dirty, attr_dirty = {}, {}
        events = []
        for i, step in enumerate(script):
            if step["op"] != "ls":
                nd, ad, known = do_fs(root, step, i)
                d = step["dir"] if "dir" in step else os.path.dirname(step["file"])
                if known:
                    names_dirty[d] = names_dirty.get(d, False) or nd
                    attr_dirty[d] = attr_dirty.get(d, False) or ad
                events.append({"i": i, "kind": "fs", "text": f"[{step['op']} ok]", "tok": tok(f"[{step['op']} ok]"),
                               "form": "fs", "ok": None})
                continue
            kind, d = step["kind"], step["dir"]
            truth = run_ls(kind, d, root)                       # prawda: zawsze liczona, by moc ocenic
            skip = (policy == "evented" and win.answer(kind, d) is not None and
                    not names_dirty.get(d, False) and (kind == "1A" or not attr_dirty.get(d, False)))
            if skip:
                text = skipped_text(kind, d, win)
            else:
                text = respond(policy, win, kind, d, truth, i)
                if kind == "1A":
                    names_dirty[d] = False
                else:
                    names_dirty[d] = attr_dirty[d] = False
            win.apply(kind, d, text, i)
            got = win.answer(kind, d)
            want = sorted(truth) if kind == "lA" else sorted(truth)
            if text.startswith("[ls ") and "identyczny" in text:
                form = "stub"
            elif text.startswith("[ls ") and "nie wykonano" in text:
                form = "skip"
            elif text.startswith("[ls "):
                form = "delta"
            else:
                form = "full"
            events.append({"i": i, "kind": f"ls {kind} {d}", "text": text, "tok": tok(text), "form": form,
                           "ok": got == want, "full_tok": tok("\n".join(truth))})
        meta = {s.get("op"): s for s in script}
        return events, meta
    finally:
        shutil.rmtree(root, ignore_errors=True)


def costs(events):
    n = len(events)
    tt, w, total = 0, 0.0, 0
    for e in events:
        rem = n - e["i"]
        tt += e["tok"] * rem
        w += e["tok"] * (CACHE_WRITE + CACHE_READ * (rem - 1))
        total += e["tok"]
    return {"tokens": total, "token_turns": tt, "weighted": w}


def summarize(n=150):
    out = {}
    for p in POLICIES:
        ev, _ = play(p, n)
        ls = [e for e in ev if e["kind"] != "fs"]
        c = costs(ev)
        c.update({"ls_ok": sum(1 for e in ls if e["ok"]), "ls_n": len(ls),
                  "stub": sum(1 for e in ls if e["form"] == "stub"), "delta": sum(1 for e in ls if e["form"] == "delta"),
                  "full": sum(1 for e in ls if e["form"] == "full"), "skip": sum(1 for e in ls if e["form"] == "skip"),
                  "wrong": [e["i"] for e in ls if not e["ok"]]})
        out[p] = c
    return out


# ----------------------------------------------------------------------------- komendy
def cmd_run(n):
    res = summarize(n)
    base = res["none"]
    print(f"katalog src: {n + 2} wpisow, sesja {len(build_script(n))} tur; mnozniki cache {CACHE_READ}/{CACHE_WRITE} (zalozenie)")
    print("| polityka | tokeny | vs none | token-tury | vs none | koszt wazony | vs none | ls ok | stub/delta/full/skip | bledne tury |")
    print("|---|---|---|---|---|---|---|---|---|---|")
    for p in POLICIES:
        r = res[p]
        print(f"| {p} | {r['tokens']} | {base['tokens'] / r['tokens']:.2f}x | {r['token_turns']} | "
              f"{base['token_turns'] / r['token_turns']:.2f}x | {r['weighted']:.0f} | {base['weighted'] / r['weighted']:.2f}x | "
              f"{r['ls_ok']}/{r['ls_n']} | {r['stub']}/{r['delta']}/{r['full']}/{r['skip']} | {r['wrong'] or '-'} |")


def cmd_show(policy, n):
    ev, _ = play(policy, n)
    for e in ev:
        flag = "" if e["ok"] in (None, True) else "  <-- BLAD"
        first = e["text"].split("\n")
        extra = f" (+{len(first) - 1} linii)" if len(first) > 1 else ""
        print(f"T{e['i']:02d} {e['kind']:<14} {e['form']:<5} {e['tok']:>5} tok. {first[0][:96]}{extra}{flag}")


def cmd_sweep():
    print("| wpisow w src | none: tokeny | state: tokeny | zysk tokenow | none: koszt wazony | state: koszt wazony | zysk kosztu |")
    print("|---|---|---|---|---|---|---|")
    for n in (20, 150, 500, 2000):
        a, _ = play("none", n)
        b, _ = play("state", n)
        ca, cb = costs(a), costs(b)
        print(f"| {n + 2} | {ca['tokens']} | {cb['tokens']} | {ca['tokens'] / cb['tokens']:.2f}x | "
              f"{ca['weighted']:.0f} | {cb['weighted']:.0f} | {ca['weighted'] / cb['weighted']:.2f}x |")


def cmd_verify(n):
    res = summarize(n)
    bad = [p for p in POLICIES if p != "evented" and res[p]["ls_ok"] != res[p]["ls_n"]]
    ok = not bad and res["evented"]["ls_ok"] < res["evented"]["ls_n"]
    print("bezpieczne polityki bez bledow:", "tak" if not bad else f"NIE: {bad}")
    print("evented (ufa zdarzeniom) ma bledy:", "tak" if res["evented"]["ls_ok"] < res["evented"]["ls_n"] else "nie")
    print("OK" if ok else "FAIL")
    return 0 if ok else 1


def cmd_demo(n):
    """Edycja o tym samym rozmiarze i tej samej minucie mtime: `ls -l` jej NIE widzi."""
    ev, meta = play("none", n)
    s = meta["edit_same"]
    i = [k for k, e in enumerate(ev) if e["i"] == 14][0]       # indeks kroku edit_same
    before = [e for e in ev if e["i"] == 13][0]["text"].split("\n")
    after = [e for e in ev if e["i"] == 15][0]["text"].split("\n")
    line_b = [l for l in before if l.endswith(" Mod007.cs")][0]
    line_a = [l for l in after if l.endswith(" Mod007.cs")][0]
    print("linia Mod007.cs w `ls -lA` przed edycja :", line_b)
    print("linia Mod007.cs w `ls -lA` po edycji    :", line_a)
    print("linie identyczne:", line_a == line_b)
    print("sha256 tresci przed:", s["hash_before"][:16], " po:", s["hash_after"][:16], " rozne:", s["hash_before"] != s["hash_after"])


def main(argv):
    n = 150
    if "--n" in argv:
        k = argv.index("--n")
        n = int(argv[k + 1])
        argv = argv[:k] + argv[k + 2:]
    cmd = argv[0] if argv else "run"
    if cmd == "run":
        cmd_run(n)
    elif cmd == "show":
        cmd_show(argv[1], n)
    elif cmd == "sweep":
        cmd_sweep()
    elif cmd == "verify":
        return cmd_verify(n)
    elif cmd == "demo":
        cmd_demo(n)
    else:
        print(__doc__)
        return 2
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
