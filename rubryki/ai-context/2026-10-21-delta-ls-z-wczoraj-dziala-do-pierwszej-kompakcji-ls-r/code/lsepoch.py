#!/usr/bin/env python3
"""lsepoch.py - `ls -R` w kontekscie: delta PER SEKCJA, projekcja poddrzewa i kompakcja okna (epoka vs ogon vs "carry").

Kontynuacja #27 (delta wyniku `ls`). Tamten skrypt zalatwil JEDEN katalog. Tu trzy nowe pytania:
  1. `ls -R` calego drzewa: jedna zmiana w jednym podkatalogu - czy placic za cale drzewo? (delta globalna vs per sekcja)
  2. `ls -lA proj/src/m03` po `ls -R proj`: model JUZ to wie - wynik mozna wyprowadzic z wiedzy o drzewie (projekcja)
  3. kompakcja okna: delta wskazuje na baze, ktorej juz nie ma (wiszacy stub, jak w #26) - jak to naprawic tanio?
     "chain" (leniwie: wyslij pelna sekcje przy nastepnym `ls`) vs "carry" (zaszyj stan drzewa w podsumowaniu).

Sesja jest SKRYPTOWANA, ale drzewo plikow jest PRAWDZIWE (/tmp), `ls` jest PRAWDZIWE (GNU coreutils; LC_ALL=C),
a "okno modelu" jest budowane WYLACZNIE z tekstu, ktory narzedzie zwrocilo (po kompakcji: z tego, co przezylo).
Zaden model nie jest uruchamiany. Tokeny = bajty/4. mtime ustawiany deterministycznie (os.utime) = T0 + 60*tura.

Polityki (wszystkie append-only: historia nie jest mutowana):
  none    - zawsze pelny wynik
  same    - stub, jesli identyczny z poprzednim wynikiem TEGO SAMEGO polecenia; inaczej pelny
  gdelta  - delta globalna (calosc albo nic): jesli delta >= pelny wynik -> pelny
  sdelta  - delta per sekcja katalogu: dla kazdej zmienionej sekcji tansze z (delta | cala sekcja)
  proj    - sdelta + jeden stan drzewa na wszystkie polecenia (ls -R, ls -lA <podkatalog>): projekcja
  chain   - proj + swiadomosc kompakcji: sekcja, ktorej lancuch (pelna + delty) nie przezyl, jest wysylana od nowa
  carry   - proj + podsumowanie kompakcji zawiera caly stan drzewa (kosztuje przy kazdej kompakcji)
Uzycie: python3 -B lsepoch.py run | show <polityka> | sweep | compsweep | order | verify
"""
import calendar
import os
import random
import re
import shutil
import subprocess
import sys
import tempfile

ENV = {"LC_ALL": "C", "TZ": "UTC", "PATH": os.environ.get("PATH", "")}
T0 = calendar.timegm((2026, 10, 1, 10, 0, 0))
POLICIES = ["none", "same", "gdelta", "sdelta", "proj", "chain", "carry"]
SUMMARY = 510            # stale podsumowanie kompakcji (jak w #26)
TOTAL = "\0total"
PERM = re.compile(r"^[-dlbcps][-rwxsStT]{9}[. +]?\s")


def tok(text):
    return (len(text.encode("utf-8", "surrogateescape")) + 3) // 4


# ----------------------------------------------------------------------------- prawdziwy ls + parsowanie
def run_ls(argv, cwd):
    r = subprocess.run(argv, cwd=cwd, env=ENV, capture_output=True, check=True)
    return r.stdout.decode("utf-8", "surrogateescape").rstrip("\n")


def ls_cmd(kind, path, cwd):
    flags = ["-R"] if kind == "R" else []
    return run_ls(["ls"] + flags + ["-lAog", "--time-style=long-iso", path], cwd)


def key_of(line):
    """Klucz wpisu: nazwa pliku (dla symlinku bez ' -> cel'); `total` to osobny klucz."""
    if line.startswith("total "):
        return TOTAL
    tail = line.split(None, 5)[5]
    return tail.split(" -> ", 1)[0] if line[0] == "l" else tail


def parse(text, default):
    """Tekst `ls` -> {katalog: {klucz: linia}}. Dla `ls -R` naglowki to `sciezka:`; dla zwyklego `ls` jest jeden katalog."""
    secs, cur = {}, default
    for ln in text.split("\n"):
        if ln == "":
            continue
        if not ln.startswith("total ") and not PERM.match(ln):
            if not ln.endswith(":"):
                raise ValueError("nie rozpoznano linii: %r" % ln)
            cur = ln[:-1]
            secs.setdefault(cur, {})
            continue
        secs.setdefault(cur, {})[key_of(ln)] = ln
    return secs


def under(d, path):
    return d == path or d.startswith(path + "/")


def prune(view):
    """Sekcja, ktorej rodzic jest znany, a nie ma na liscie wpisu-katalogu o tej nazwie, jest sierota -> usuwamy."""
    changed = True
    while changed:
        changed = False
        for d in list(view):
            if "/" not in d:
                continue
            parent, name = d.rsplit("/", 1)
            if parent in view:
                ent = view[parent].get(name)
                if ent is None or ent[0] != "d":
                    for x in [x for x in view if under(x, d)]:
                        del view[x]
                    changed = True


def render_section(d, sec, header):
    body = [sec[k] for k in sorted(sec, key=lambda k: (k != TOTAL, k))]
    return ([d + ":"] if header else []) + body


# ----------------------------------------------------------------------------- "to, co model widzi w oknie"
class Window:
    def __init__(self):
        self.views = {}      # klucz widoku -> {katalog: {klucz: linia}}
        self.turn = {}       # klucz widoku -> tura ostatniej aktualizacji

    def apply(self, vk, kind, path, text, turn):
        v = self.views.setdefault(vk, {})
        lines = text.split("\n")
        if lines[0].startswith("[ls ") and lines[0].endswith("]"):
            if "identyczny" in lines[0]:
                return
            cur = None
            for ln in lines[1:]:
                if ln.startswith("@"):
                    if ln.endswith(" ="):
                        cur = ln[1:-2]
                        v[cur] = {}
                    else:                  # delta bez bazy (wiszaca): model nie ma do czego jej zastosowac
                        cur = ln[1:] if ln[1:] in v else None
                elif cur is None:
                    continue
                elif ln[0] == "=":
                    v[cur][key_of(ln[1:])] = ln[1:]
                elif ln[0] in "+~":
                    v[cur][key_of(ln[1:])] = ln[1:]
                elif ln[0] == "-":
                    v[cur].pop(ln[1:], None)
        else:
            secs = parse(text, path)
            if kind == "R":
                for d in [d for d in v if under(d, path)]:
                    del v[d]
            v.update(secs)
        prune(v)
        self.turn[vk] = turn

    def snapshot(self, vk, view, turn):
        self.views[vk] = {d: dict(s) for d, s in view.items()}
        self.turn[vk] = turn

    def answer(self, vk, kind, path):
        v = self.views.get(vk, {})
        if kind == "R":
            return {d: dict(s) for d, s in v.items() if under(d, path)}
        return {path: dict(v[path])} if path in v else {}


# ----------------------------------------------------------------------------- narzedzie (strona, ktora decyduje, co wyslac)
class Tool:
    def __init__(self, policy):
        self.policy = policy
        self.proj = policy in ("proj", "chain", "carry")
        self.shadow = Window()          # to, co narzedzie UWAZA, ze okno wie
        self.chain = {}                 # (vk, katalog) -> tura ostatniej pelnej sekcji (poczatek lancucha)
        self.rep_existing = 0           # ile razy "cala sekcja" wygrala z delta dla sekcji JUZ znanej

    def vkey(self, kind, path):
        return "*" if self.proj else (kind, path)

    def emit(self, kind, path, truth, full, turn):
        """Zwraca (forma, tekst); forma in full|delta|stub."""
        pol, vk = self.policy, self.vkey(kind, path)
        if pol == "none":
            return "full", full
        base = self.shadow.views.get(vk, {})
        old_turn = self.shadow.turn.get(vk, 0)
        flag = "-R " if kind == "R" else ""
        title = "[ls %s%s: " % (flag, path)
        diff, replaced = [], []
        for d in sorted(truth):
            sec, b = truth[d], base.get(d)
            if b is None:
                rep = ["@%s =" % d] + ["=" + l for l in render_section(d, sec, False)]
                diff.append(rep)
                replaced.append(d)
                continue
            if b == sec:
                continue
            dl = ["@" + d]
            for k in sorted(sec):
                if b.get(k) != sec[k]:
                    dl.append(("~" if k in b else "+") + sec[k])
            for k in sorted(b):
                if k not in sec:
                    dl.append("-" + k)
            rep = ["@%s =" % d] + ["=" + l for l in render_section(d, sec, False)]
            if pol in ("sdelta", "proj", "chain", "carry") and tok("\n".join(rep)) < tok("\n".join(dl)):
                diff.append(rep)
                replaced.append(d)
                self.rep_existing += 1
            else:
                diff.append(dl)
        if not diff and base and all(d in base for d in truth):
            return "stub", title + "identyczny z tura %d]" % old_turn
        if pol == "same":
            return "full", full
        text = title + "delta wzgledem tury %d; sekcji: %d]\n" % (old_turn, len(diff)) + "\n".join("\n".join(x) for x in diff)
        if tok(text) >= tok(full):
            return "full", full
        return "delta", text

    def record(self, kind, path, form, text, truth, turn):
        vk = self.vkey(kind, path)
        self.shadow.apply(vk, kind, path, text, turn)
        if form == "full":
            for d in truth:
                self.chain[(vk, d)] = turn
        elif form == "delta":
            for ln in text.split("\n")[1:]:
                if ln.startswith("@") and ln.endswith(" ="):
                    self.chain[(vk, ln[1:-2])] = turn
        for d in truth:
            self.chain.setdefault((vk, d), turn)
        if form != "stub":
            self.shadow.turn[vk] = turn

    def on_compact(self, keep_from):
        """Co narzedzie robi po kompakcji okna (zachowaja sie tylko wyniki z tur >= keep_from)."""
        if self.policy == "chain":
            for (vk, d), start in list(self.chain.items()):
                if start < keep_from:
                    self.shadow.views.get(vk, {}).pop(d, None)
                    del self.chain[(vk, d)]


# ----------------------------------------------------------------------------- prawdziwy katalog
class Sandbox:
    def __init__(self, mods=12, files=10, seed=1):
        self.base = tempfile.mkdtemp(prefix="lsepoch-")
        self.rng = random.Random(seed)
        self.n = 0
        os.makedirs(self.p("proj"))
        for m in range(mods):
            for i in range(files):
                self.write("proj/src/m%02d/File%03d.cs" % (m, i), 100 + (i * 37 + m * 11) % 900)
        for i in range(20):
            self.write("proj/tests/Test%03d.cs" % i, 80 + i * 13)
        for i in range(6):
            self.write("proj/docs/doc%d.md" % i, 300 + i)
        self.write("proj/my notes/a b.md", 50)
        self.write("proj/README.md", 700)
        self.write("proj/proj.sln", 900)
        os.symlink("src/m00", self.p("proj/latest"))
        os.symlink("../README.md", self.p("proj/docs/cur"))
        self.stamp_all(0)

    def p(self, rel):
        return os.path.join(self.base, rel)

    def write(self, rel, size):
        os.makedirs(os.path.dirname(self.p(rel)), exist_ok=True)
        with open(self.p(rel), "wb") as f:
            f.write(b"x" * size)

    def stamp_all(self, turn):
        t = T0 + 60 * turn
        for dp, dn, fn in os.walk(self.p("proj")):
            for n in dn + fn:
                os.utime(os.path.join(dp, n), (t, t), follow_symlinks=False)
            os.utime(dp, (t, t), follow_symlinks=False)

    def files(self):
        out = []
        for dp, dn, fn in os.walk(self.p("proj")):
            for n in fn:
                if not os.path.islink(os.path.join(dp, n)):
                    out.append(os.path.relpath(os.path.join(dp, n), self.base))
        return sorted(out)

    def dirs(self):
        out = []
        for dp, dn, fn in os.walk(self.p("proj")):
            out.append(os.path.relpath(dp, self.base))
        return sorted(out)

    def apply(self, op, turn):
        """Wykonuje operacje; zwraca zbior dotknietych sciezek (do ustawienia mtime)."""
        kind, a = op[0], op[1:]
        touched = set()

        def add(rel, parent=True):
            touched.add(rel)
            if parent:
                touched.add(os.path.dirname(rel))
        if kind == "edit":
            self.write(a[0], a[1]); add(a[0], False)
        elif kind == "create":
            self.write(a[0], a[1]); add(a[0])
        elif kind == "delete":
            os.remove(self.p(a[0])); touched.add(os.path.dirname(a[0]))
        elif kind == "rename":
            os.rename(self.p(a[0]), self.p(a[1])); touched.add(os.path.dirname(a[0])); add(a[1])
        elif kind == "rmtree":
            shutil.rmtree(self.p(a[0])); touched.add(os.path.dirname(a[0]))
        elif kind == "relink":
            os.remove(self.p(a[0])); os.symlink(a[1], self.p(a[0])); add(a[0])
        elif kind == "bulk":         # "build" (proces zewnetrzny): a[1] podkatalogow po a[2] plikow
            for j in range(a[1]):
                for i in range(a[2]):
                    self.write("%s/p%02d/gen%03d.g.cs" % (a[0], j, i), 40 + i)
                    add("%s/p%02d/gen%03d.g.cs" % (a[0], j, i), False)
                touched.add("%s/p%02d" % (a[0], j))
            touched.add(a[0]); touched.add(os.path.dirname(a[0]))
        elif kind == "rand":
            for _ in range(a[0]):
                touched |= self.rand_op()
        return touched

    def rand_op(self):
        r, files, dirs = self.rng, self.files(), self.dirs()
        c = r.choice(["edit", "edit", "create", "create", "delete", "rename", "mkdir", "rmdir", "relink"])
        t = set()
        if c == "edit" and files:
            f = r.choice(files); self.write(f, r.randint(1, 900)); t.add(f)
        elif c == "create":
            d = r.choice(dirs); f = "%s/%s%d.txt" % (d, r.choice(["n", "a b ", "z"]), r.randint(0, 99))
            self.write(f, r.randint(1, 500)); t |= {f, d}
        elif c == "delete" and len(files) > 5:
            f = r.choice(files); os.remove(self.p(f)); t.add(os.path.dirname(f))
        elif c == "rename" and files:
            f = r.choice(files); g = os.path.join(os.path.dirname(f), "r%d.cs" % r.randint(0, 999))
            if not os.path.exists(self.p(g)):
                os.rename(self.p(f), self.p(g)); t |= {os.path.dirname(f), g}
        elif c == "mkdir":
            d = r.choice(dirs); nd = "%s/new%d" % (d, r.randint(0, 99))
            if not os.path.exists(self.p(nd)):
                self.write(nd + "/x.cs", 10); t |= {d, nd, nd + "/x.cs"}
        elif c == "rmdir":          # tylko katalogi "newN" (pozostale sa celami zapytan ls w fuzzie)
            cand = [x for x in dirs if os.path.basename(x).startswith("new")]
            if cand:
                d = r.choice(cand)
                shutil.rmtree(self.p(d)); t.add(os.path.dirname(d))
        elif c == "relink":
            l = "proj/latest"
            os.remove(self.p(l)); os.symlink(r.choice(["src/m00", "src/m01", "docs"]), self.p(l)); t.add(l)
        return t

    def do_turn(self, ops, turn):
        touched = set()
        for op in ops:
            touched |= self.apply(op, turn)
        t = T0 + 60 * turn
        for rel in touched:
            if rel and os.path.lexists(self.p(rel)):
                os.utime(self.p(rel), (t, t), follow_symlinks=False)

    def close(self):
        shutil.rmtree(self.base, ignore_errors=True)


# ----------------------------------------------------------------------------- sesja
def script():
    """18 tur: (operacje, wywolanie ls). R = ls -R, L = ls bez -R."""
    S = "proj/src/m03"
    return [
        ([], ("R", "proj")),                                                                     # 1 pelne drzewo
        ([("edit", S + "/File002.cs", 555)], ("R", "proj")),                                     # 2 edycja w jednym podkatalogu
        ([], ("R", "proj")),                                                                     # 3 bez zmian
        ([("create", "proj/tests/New%d.cs" % i, 90) for i in range(3)], ("L", "proj/tests")),    # 4 3 nowe pliki, podkatalog
        ([("edit", "proj/src/m05/File004.cs", 333)], ("R", "proj")),                             # 5
        ([("bulk", "proj/obj", 4, 15)], ("R", "proj")),                                          # 6 zewnetrzny build: 4 katalogi x 15 plikow
        ([], ("R", S)),                                                                          # 7 poddrzewo po -R calego
        ([("rename", "proj/src/m01/File001.cs", "proj/src/m01/Renamed.cs")], ("R", "proj")),     # 8
        ([("delete", "proj/docs/doc0.md"), ("delete", "proj/docs/doc1.md"),
          ("relink", "proj/latest", "src/m02")], ("L", "proj")),                                 # 9 -lA samego korzenia
        ([], ("R", "proj")),                                                                     # 10
        ([("edit", S + "/File005.cs", 444)], ("R", "proj/src")),                                 # 11
        ([("rmtree", "proj/obj")], ("R", "proj")),                                               # 12 clean
        ([("create", "proj/my notes/c d.md", 77)], ("R", "proj")),                               # 13 spacje w nazwach
        ([], ("R", "proj")),                                                                     # 14
        ([("edit", S + "/File001.cs", 222)], ("L", S)),                                          # 15
        ([], ("R", "proj")),                                                                     # 16
        ([("edit", "proj/src/m07/File003.cs", 111), ("edit", "proj/tests/Test001.cs", 121)], ("R", "proj")),  # 17
        ([], ("R", "proj")),                                                                     # 18
    ]


def run_session(policy, scr, comp=None, tail=0, mods=12, files=10, seed=1):
    """comp = numer tury, PRZED ktora nastepuje kompakcja; zachowane sa wyniki z tur >= comp - tail."""
    sb = Sandbox(mods, files, seed)
    tool, win = Tool(policy), Window()
    records, results, bad, forms, summary = [], [], [], {"stub": 0, "delta": 0, "full": 0}, 0
    carry_tok = 0
    T = len(scr)
    try:
        for turn, (ops, (kind, path)) in enumerate(scr, 1):
            sb.do_turn(ops, turn)
            if comp == turn:
                keep = turn - tail
                records = [r for r in records if r[0] >= keep]
                tool.on_compact(keep)
                win = Window()
                if policy == "carry":
                    view = {d: dict(s) for d, s in tool.shadow.views.get("*", {}).items()}
                    txt = "\n".join(l for d in sorted(view) for l in render_section(d, view[d], True))
                    carry_tok = tok(txt)
                    win.snapshot("*", view, keep - 1)
                for r in records:
                    win.apply(*r[1:5], r[0])
                results = [(t, n, kept) for (t, n, kept) in results]
                results = [(t, n, t >= keep) for (t, n, _) in results]
            full = ls_cmd(kind, path, sb.base)
            truth = parse(full, path)
            form, text = tool.emit(kind, path, truth, full, turn)
            tool.record(kind, path, form, text, truth, turn)
            vk = tool.vkey(kind, path)
            win.apply(vk, kind, path, text, turn)
            records.append((turn, vk, kind, path, text))
            forms[form] += 1
            results.append((turn, tok(text), True))
            if win.answer(vk, kind, path) != truth:
                bad.append(turn)
    finally:
        sb.close()
    total = sum(n for _, n, _ in results)
    tt = 0
    for t, n, kept in results:
        end = T if (kept or comp is None) else comp - 1
        tt += n * (end - t + 1)
    if comp is not None:
        total += SUMMARY + carry_tok
        tt += (SUMMARY + carry_tok) * (T - comp + 1)
    return {"tokens": total, "tt": tt, "bad": bad, "forms": forms, "carry": carry_tok, "rep": tool.rep_existing}


def table(rows, base):
    print("| polityka | tokeny | vs none | token-tury | vs none | stub/delta/full | bledne tury |")
    print("|---|---|---|---|---|---|---|")
    for pol, r in rows:
        f = r["forms"]
        print("| %s | %d | %.2fx | %d | %.2fx | %d/%d/%d | %s |" % (
            pol, r["tokens"], base["tokens"] / r["tokens"], r["tt"], base["tt"] / r["tt"],
            f["stub"], f["delta"], f["full"], ("[" + ",".join(map(str, r["bad"])) + "]") if r["bad"] else "-"))


def cmd_run(args):
    mods = int(args[args.index("--mods") + 1]) if "--mods" in args else 12
    scr = script()
    sb = Sandbox(mods)
    n = len(parse(ls_cmd("R", "proj", sb.base), "proj"))
    full = ls_cmd("R", "proj", sb.base)
    entries = sum(len(s) - 1 for s in parse(full, "proj").values())
    print("drzewo proj: %d katalogow, %d wpisow, pelny `ls -R` = %d tok.; sesja %d tur" % (n, entries, tok(full), len(scr)))
    sb.close()
    for title, comp, tail in [("bez kompakcji", None, 0), ("kompakcja przed tura 10, ogon 0", 10, 0),
                              ("kompakcja przed tura 10, ogon 4 (zostaja tury 6..9)", 10, 4)]:
        print("\n### " + title)
        rows = [(p, run_session(p, scr, comp, tail, mods)) for p in POLICIES]
        table(rows, rows[0][1])
        print("(cala sekcja wygrala z delta dla sekcji juz znanej: %d razy w sdelta, %d w proj)" % (
            dict(rows)["sdelta"]["rep"], dict(rows)["proj"]["rep"]))


def cmd_show(args):
    pol = args[0]
    comp = int(args[args.index("--comp") + 1]) if "--comp" in args else None
    tail = int(args[args.index("--tail") + 1]) if "--tail" in args else 0
    scr = script()
    sb = Sandbox()
    tool, win = Tool(pol), Window()
    print("tura | wywolanie | forma | tokeny | peln.")
    records = []
    for turn, (ops, (kind, path)) in enumerate(scr, 1):
        sb.do_turn(ops, turn)
        if comp == turn:
            keep = turn - tail
            records = [r for r in records if r[0] >= keep]
            tool.on_compact(keep)
            win = Window()
            if pol == "carry":
                win.snapshot("*", {d: dict(s) for d, s in tool.shadow.views.get("*", {}).items()}, keep - 1)
            for r in records:
                win.apply(*r[1:5], r[0])
            print("---- kompakcja, zostaja tury >= %d ----" % keep)
        full = ls_cmd(kind, path, sb.base)
        truth = parse(full, path)
        form, text = tool.emit(kind, path, truth, full, turn)
        tool.record(kind, path, form, text, truth, turn)
        vk = tool.vkey(kind, path)
        win.apply(vk, kind, path, text, turn)
        records.append((turn, vk, kind, path, text))
        ok = win.answer(vk, kind, path) == truth
        print("%2d | ls %s%s | %s | %d | %d | %s" % (turn, "-R " if kind == "R" else "", path, form, tok(text), tok(full),
                                                  "ok" if ok else "BLAD (okno != ls)"))
        if "--text" in args and form != "full":
            for ln in text.split("\n")[:14]:
                print("      > " + ln)
    sb.close()


def cmd_sweep(args):
    print("| katalogow src | pelny ls -R (tok.) | none: tokeny | proj: tokeny | zysk | gdelta zysk | sdelta zysk |")
    print("|---|---|---|---|---|---|---|")
    scr = script()
    for mods in (4, 12, 40, 120):
        sb = Sandbox(mods)
        full = tok(ls_cmd("R", "proj", sb.base))
        sb.close()
        r = {p: run_session(p, scr, None, 0, mods) for p in ("none", "gdelta", "sdelta", "proj")}
        print("| %d | %d | %d | %d | %.2fx | %.2fx | %.2fx |" % (
            mods, full, r["none"]["tokens"], r["proj"]["tokens"], r["none"]["tokens"] / r["proj"]["tokens"],
            r["none"]["tokens"] / r["gdelta"]["tokens"], r["none"]["tokens"] / r["sdelta"]["tokens"]))


def compsweep():
    """Kompakcja przed kazda tura 2..18 x ogony {0,3,6}: ile scenariuszy z bledem, ile blednych tur, koszt wzgledem none."""
    scr = script()
    tails = (0, 3, 6)
    res = {}
    for pol in POLICIES:
        sc = badsc = badt = 0
        for comp in range(2, len(scr) + 1):
            for tail in tails:
                r = run_session(pol, scr, comp, tail)
                sc += 1
                if r["bad"]:
                    badsc += 1
                    badt += len(r["bad"])
                res.setdefault(pol, []).append(r["tt"])
        res[pol] = (sc, badsc, badt, sum(res[pol]))
    return res


def cmd_compsweep(args):
    res = compsweep()
    base = res["none"][3]
    print("| polityka | scenariuszy | z bledem | bledne tury | suma token-tur | vs none |")
    print("|---|---|---|---|---|---|")
    for pol in POLICIES:
        sc, bs, bt, tt = res[pol]
        print("| %s | %d | %d | %d | %d | %.2fx |" % (pol, sc, bs, bt, tt, base / tt))
    if "--list" in args:
        pol = args[args.index("--list") + 1]
        for comp in range(2, len(script()) + 1):
            for tail in (0, 3, 6):
                r = run_session(pol, script(), comp, tail)
                if r["bad"]:
                    print("%s: kompakcja przed tura %d, ogon %d -> bledne tury %s" % (pol, comp, tail, r["bad"]))


# ----------------------------------------------------------------------------- kolejnosc: ls -t / -S
def order_test():
    """Czy kolejnosc `ls -t` / `-S` da sie odtworzyc z TEKSTU linii? long-iso (minuty) vs full-iso (ns)."""
    base = tempfile.mkdtemp(prefix="lsorder-")
    rng = random.Random(7)
    try:
        d = os.path.join(base, "d")
        os.makedirs(d)
        names = ["f%03d.cs" % i for i in range(152)]
        for n in names:
            with open(os.path.join(d, n), "wb") as f:
                f.write(b"x" * rng.randint(1, 40))
        out = {}
        for style in ("long-iso", "full-iso"):
            for mode in ("-t", "-S"):
                good = tot = 0
                lens = []
                for trial in range(40):
                    # mtime: sekundy + ns losowe w obrebie ~8 minut -> wiele plikow w tej samej minucie
                    for n in names:
                        t = T0 + rng.randint(0, 480)
                        ns = rng.randint(0, 999999999)
                        os.utime(os.path.join(d, n), ns=(t * 10**9 + ns, t * 10**9 + ns))
                    for n in names[:20]:      # zmiany rozmiaru, zeby -S mial remisy
                        with open(os.path.join(d, n), "wb") as f:
                            f.write(b"x" * rng.randint(1, 6))
                    txt = run_ls(["ls", "-lAog", mode, "--time-style=" + style, "d"], base)
                    lines = [l for l in txt.split("\n") if not l.startswith("total ")]
                    lens.append(tok("\n".join(lines)))
                    ncol = 5 if style == "long-iso" else 6      # kolumny przed nazwa
                    rows = []
                    for l in lines:
                        p = l.split(None, ncol)
                        size, date, tm = int(p[2]), p[3], p[4]
                        rows.append((size, date + " " + tm, p[ncol]))
                    if mode == "-t":
                        rec = sorted(rows, key=lambda r: (_neg(r[1]), r[2]))
                    else:
                        rec = sorted(rows, key=lambda r: (-r[0], r[2]))
                    tot += 1
                    good += [r[2] for r in rec] == [r[2] for r in rows]
                out[(style, mode)] = (good, tot, sum(lens) // len(lens))
        return out
    finally:
        shutil.rmtree(base, ignore_errors=True)


def _neg(s):
    """Klucz malejacy po napisie czasu (porownanie leksykograficzne == chronologiczne dla ISO)."""
    return tuple(-ord(c) for c in s) + (1,)


def cmd_order(args):
    out = order_test()
    print("| tryb | styl czasu | kolejnosc odtworzona z tekstu | sredni rozmiar listingu (tok.) |")
    print("|---|---|---|---|")
    for (style, mode), (g, t, n) in out.items():
        print("| ls %s | %s | %d/%d | %d |" % (mode, style, g, t, n))


def cmd_verify(args):
    scr = script()
    ok = True
    for pol in ("none", "same", "gdelta", "sdelta", "proj", "chain", "carry"):
        r = run_session(pol, scr)
        if r["bad"]:
            print("BLAD: %s bez kompakcji ma bledne tury %s" % (pol, r["bad"])); ok = False
    res = compsweep()
    for pol in ("none", "chain", "carry"):
        if res[pol][1]:
            print("BLAD: %s ma %d scenariuszy z bledem po kompakcji" % (pol, res[pol][1])); ok = False
    for pol in ("same", "gdelta", "sdelta", "proj"):
        if res[pol][1] == 0:
            print("BLAD: test negatywny - %s MUSI sie mylic po kompakcji, a sie nie myli" % pol); ok = False
    print("OK" if ok else "FAIL")
    return 0 if ok else 1


def main(argv):
    if not argv:
        print(__doc__)
        return 2
    c, rest = argv[0], argv[1:]
    if c == "run":
        cmd_run(rest)
    elif c == "show":
        cmd_show(rest)
    elif c == "sweep":
        cmd_sweep(rest)
    elif c == "compsweep":
        cmd_compsweep(rest)
    elif c == "order":
        cmd_order(rest)
    elif c == "verify":
        return cmd_verify(rest)
    else:
        print(__doc__)
        return 2
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
