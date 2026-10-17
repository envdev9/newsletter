#!/usr/bin/env python3
"""Krok 3 lancucha: co lapie Roslyn w pamieci, czego nie lapia reguly formatu, a co dopiero testy.

6 wariantow poprawki Money.Round (kod ciala PISANY RECZNIE jako 'odpowiedz modelu'; sam diff generuje difflib).
Dla kazdego: (a) reguly formatu/zakresu w stylu C13-C17 z #18, (b) Roslyn `diag` na lokalnej kopii po
`git apply`, (c) wyrocznia: `dotnet build` + Billing.Check. Wszystko w kopii w /tmp (sprzatane na koncu).
"""
import difflib
import os
import re
import shutil
import subprocess
import sys
import tempfile
import time

HERE = os.path.dirname(os.path.abspath(__file__))
DLL = os.path.join(HERE, "SymbolIndex", "bin", "Release", "net10.0", "SymbolIndex.dll")
TARGET = "Billing/Money.cs"
OLD = "        Math.Round(amount, 2);"

VARIANTS = [
    ("p0_good", "poprawna: AwayFromZero", "        Math.Round(amount, 2, MidpointRounding.AwayFromZero);"),
    ("p1_bad_enum", "zmyslony czlon enum", "        Math.Round(amount, 2, MidpointRounding.AwayFromZeroes);"),
    ("p2_bad_method", "zmyslona metoda Math.RoundHalfUp", "        Math.RoundHalfUp(amount, 2);"),
    ("p3_bad_arg", "zly typ argumentu (int zamiast enum)", "        Math.Round(amount, 2, 1);"),
    ("p4_bad_type", "double zamiast decimal (CS0266)", "        Math.Round((double)amount, 2, MidpointRounding.AwayFromZero);"),
    ("p5_wrong_fix", "kompiluje sie, ale zle: ToPositiveInfinity", "        Math.Round(amount, 2, MidpointRounding.ToPositiveInfinity);"),
]


def make_diff(new_line: str) -> str:
    src = open(os.path.join(HERE, TARGET), encoding="utf-8").read()
    assert OLD in src
    dst = src.replace(OLD, new_line)
    d = difflib.unified_diff(src.splitlines(keepends=True), dst.splitlines(keepends=True),
                             fromfile=f"a/{TARGET}", tofile=f"b/{TARGET}", n=3)
    return "".join(d)


def format_rules(diff: str, wd: str) -> list[str]:
    """Podzbior regul C13-C17 z #18 (czysty diff, zakres, rozmiar, git apply --check)."""
    errs = []
    if "```" in diff or not diff.startswith("--- "):
        errs.append("C13")
    files = re.findall(r"^\+\+\+ b/(\S+)", diff, flags=re.M)
    for f in files:
        if f.startswith("Billing.Check/"):
            errs.append("C14")
        elif f != TARGET:
            errs.append("C15")
    n = sum(1 for l in diff.splitlines() if l.startswith(("+", "-")) and not l.startswith(("+++", "---")))
    if n > 10:
        errs.append("C17")
    p = os.path.join(wd, "_patch.diff")
    open(p, "w", encoding="utf-8", newline="\n").write(diff)
    r = subprocess.run(["git", "-C", wd, "apply", "--check", "_patch.diff"], capture_output=True, text=True)
    if r.returncode != 0:
        errs.append("C16")
    return errs


def run(cmd: list[str], **kw) -> tuple[subprocess.CompletedProcess, float]:
    t = time.perf_counter()
    r = subprocess.run(cmd, capture_output=True, text=True, **kw)
    return r, (time.perf_counter() - t) * 1000


def main() -> int:
    rows = []
    shown_repair = None
    for vid, desc, new_line in VARIANTS:
        wd = tempfile.mkdtemp(prefix="patchcheck-")
        try:
            for d in ("Billing", "Billing.Check"):
                shutil.copytree(os.path.join(HERE, d), os.path.join(wd, d), ignore=shutil.ignore_patterns("bin", "obj"))
            diff = make_diff(new_line)
            fmt = format_rules(diff, wd)
            subprocess.run(["git", "-C", wd, "apply", "_patch.diff"], check=True, capture_output=True)
            os.remove(os.path.join(wd, "_patch.diff"))

            r, ms_roslyn_wall = run(["dotnet", DLL, "diag", os.path.join(wd, "Billing")])
            lines = r.stdout.splitlines()
            ro_ids = sorted({l.split()[0] for l in lines if re.match(r"CS\d+ ", l)})
            ro_msgs = [l for l in lines if re.match(r"CS\d+ ", l)]
            ro_inproc = next((l.split("=")[1] for l in lines if l.startswith("# ms=")), "?")

            r, ms_build = run(["dotnet", "build", os.path.join(wd, "Billing.Check", "Billing.Check.csproj"), "-nologo", "-v", "q"])
            build_ids = sorted(set(re.findall(r"error (CS\d+)", r.stdout)))
            build_ok = r.returncode == 0
            gate = "-"
            if build_ok:
                g, _ = run(["dotnet", "run", "--no-build", "--project", os.path.join(wd, "Billing.Check", "Billing.Check.csproj")])
                gate = "zielone" if g.returncode == 0 else "CZERWONE: " + g.stdout.strip().splitlines()[-1]
            if shown_repair is None and ro_msgs:
                shown_repair = (vid, ro_msgs)
            rows.append((vid, desc, fmt, ro_ids, int(ms_roslyn_wall), ro_inproc, build_ids, build_ok, int(ms_build), gate))
        finally:
            shutil.rmtree(wd, ignore_errors=True)

    print(f"{'id':<14} {'reguly formatu':<15} {'Roslyn (diag)':<16} {'dotnet build':<16} {'Billing.Check':<22} opis")
    for vid, desc, fmt, ro_ids, _, _, b_ids, b_ok, _, gate in rows:
        print(f"{vid:<14} {('OK' if not fmt else ','.join(fmt)):<15} {('OK' if not ro_ids else ','.join(ro_ids)):<16} "
              f"{('OK' if b_ok else ','.join(b_ids)):<16} {gate:<22} {desc}")
    print()
    agree = sum(1 for r in rows if r[3] == r[6])
    print(f"zgodnosc zbioru kodow bledow Roslyn vs dotnet build: {agree}/{len(rows)}")
    print("czasy [ms] (1 przebieg, zimny start): "
          + "; ".join(f"{r[0]}: Roslyn proces {r[4]} (w procesie {r[5]}) / build {r[8]}" for r in rows))
    if shown_repair:
        print(f"\nprzyklad listy bledow dla promptu naprawczego ({shown_repair[0]}):")
        for m in shown_repair[1]:
            print("- " + m)
    return 0


if __name__ == "__main__":
    sys.exit(main())
