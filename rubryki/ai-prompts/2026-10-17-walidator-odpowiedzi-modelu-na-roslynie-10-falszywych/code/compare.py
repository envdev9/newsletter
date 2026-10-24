#!/usr/bin/env python3
"""Regex vs Roslyn: indeks symboli na tych samych korpusach + werdykty C06/C07 na twierdzeniach.

Wymaga zbudowanego SymbolIndex (patrz README). Zadnego modelu - prawda (expected_*.txt, claims.txt)
jest pisana recznie. Exit 0 zawsze, gdy skrypt sie wykonal; liczby sa wynikiem, nie asercja.
"""
import os
import subprocess
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
from regex_index import build_index  # noqa: E402

DLL = os.path.join(HERE, "SymbolIndex", "bin", "Release", "net10.0", "SymbolIndex.dll")

CORPORA = [
    # (nazwa, katalog-rodzic, podkatalog, plik prawdy)
    ("Billing", HERE, "Billing", "expected_billing.txt"),
    ("hard", os.path.join(HERE, "corpus"), "hard", "expected_hard.txt"),
]


def roslyn_index(parent: str, sub: str) -> dict[str, dict]:
    r = subprocess.run(["dotnet", DLL, "index", os.path.join(parent, sub)], capture_output=True, text=True, check=True)
    out = {}
    for line in r.stdout.splitlines():
        name, kind, access, files, sigs = line.split("\t")
        out[name] = {"kind": kind, "access": access, "files": set(files.split(";")), "sigs": set(s for s in sigs.split(";") if s)}
    return out


def read_expected(path: str) -> dict[str, set[str]]:
    out = {}
    for line in open(path, encoding="utf-8"):
        line = line.strip()
        if line and not line.startswith("#"):
            name, files = line.split("|")
            out[name] = set(files.split(";"))
    return out


def lenient(name: str) -> str:
    return ".".join(name.split(".")[-2:])


def report(label: str, found: set[str], truth: set[str]) -> None:
    tp, miss, ph = found & truth, truth - found, found - truth
    print(f"  {label:<8} trafione {len(tp):>2}/{len(truth)}  pominiete {len(miss):>2}  widma (nie istnieja) {len(ph):>2}")
    if miss:
        print(f"           pominiete: {', '.join(sorted(miss))}")
    if ph:
        print(f"           widma:     {', '.join(sorted(ph))}")


def main() -> int:
    tot = {"regex": [0, 0, 0], "roslyn": [0, 0, 0]}   # tp, miss, phantom
    rx_all, ro_all = {}, {}
    for name, parent, sub, exp in CORPORA:
        truth = read_expected(os.path.join(HERE, exp))
        rx = build_index(parent, sub)
        ro = roslyn_index(parent, sub)
        rx_all.update(rx)
        ro_all.update(ro)
        t = set(truth)
        print(f"== korpus {name}: {len(t)} symboli w prawdzie, regex zwrocil {len(rx)}, Roslyn {len(ro)}")
        report("regex", set(rx), t)
        report("Roslyn", set(ro), t)
        # lenient: porownanie po dwoch ostatnich czlonach (Typ.Skladowa) - ile bledu to samo nazewnictwo zagniezdzen
        lt = {lenient(x) for x in t}
        print(f"  regex (porownanie luzne, 2 ostatnie czlony): trafione {len({lenient(x) for x in rx} & lt)}/{len(lt)}")
        # pliki: czy symbol wskazuje CALY zestaw plikow z prawdy (partial)
        rx_file_bad = [s for s in truth if s in rx and {rx[s]} != truth[s]]
        ro_file_bad = [s for s in truth if s in ro and ro[s]["files"] != truth[s]]
        print(f"  zgodnosc plikow dla znalezionych: regex bledne {rx_file_bad or 0}, Roslyn bledne {ro_file_bad or 0}")
        for who, found in (("regex", set(rx)), ("roslyn", set(ro))):
            tot[who][0] += len(found & t)
            tot[who][1] += len(t - found)
            tot[who][2] += len(found - t)
        print()
    print("RAZEM (oba korpusy):")
    for who in ("regex", "roslyn"):
        tp, miss, ph = tot[who]
        print(f"  {who:<7} trafione {tp}, pominiete {miss}, widma {ph}")

    print("\n== werdykty C06/C07 na twierdzeniach (OK = walidator przepuszcza, ODRZUC = odrzuca)")
    print(f"{'twierdzenie':<34} {'prawda':<6} {'regex':<8} {'Roslyn':<8} notatka")
    rows = []
    for line in open(os.path.join(HERE, "claims.txt"), encoding="utf-8"):
        line = line.strip()
        if not line or line.startswith("#"):
            continue
        sym, file, truth, note = line.split("|", 3)
        name, _, sig = sym.partition("(")
        sig = sig.rstrip(")")
        # regex: nazwa w indeksie i plik sie zgadza (C06 + C07; sygnatur regex nie zna)
        rx_ok = name in rx_all and rx_all[name] == file
        ent = ro_all.get(name)
        ro_ok = ent is not None and file in ent["files"] and (not sig or sig in ent["sigs"])
        rows.append((sym, file, truth, rx_ok, ro_ok, note))
        print(f"{sym:<34} {truth:<6} {'OK' if rx_ok else 'ODRZUC':<8} {'OK' if ro_ok else 'ODRZUC':<8} {note}")
    for who, idx in (("regex", 3), ("Roslyn", 4)):
        fg = sum(1 for r in rows if r[2] == "fake" and r[idx])          # falszywe zielone
        fr = sum(1 for r in rows if r[2] == "real" and not r[idx])      # falszywe czerwone
        ok = sum(1 for r in rows if (r[2] == "real") == r[idx])
        print(f"{who}: poprawne decyzje {ok}/{len(rows)}, falszywe zielone (zmyslony symbol przeszedl) {fg}, "
              f"falszywe czerwone (prawdziwy symbol odrzucony) {fr}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
