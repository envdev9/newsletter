#!/usr/bin/env python3
"""drift_test.py - czy walidator, kompilator i wykonywalne przyklady lapia ROZJAZD dokumentacji?

Dla kazdego z 11 "dryfow" kopiuje Retry/, Retry.Demo/ i docs-good/ do katalogu w /tmp,
wprowadza jedna zmiane (w kodzie albo w dokumencie) i uruchamia trzy detektory:
  1. docs_check.py check          (walidator z tego wydania)
  2. dotnet build                 (liczba NOWYCH ostrzezen kompilatora CS*, XML-doc wlaczony)
  3. dotnet run --project Retry.Demo (przyklady z README/ADR wykonywane na kodzie)
Repo nie jest modyfikowane. Uzycie:  python3 -B drift_test.py [--no-dotnet]
"""
from __future__ import annotations

import argparse
import re
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

HERE = Path(__file__).resolve().parent
CHECK = HERE / "docs_check.py"

# (id, opis, plik wzgledny, stary fragment, nowy fragment, oczekiwana regula walidatora albo None)
DRIFTS = [
    ("D01", "dodany parametr bez <param>", "Retry/Backoff.cs",
     "public static TimeSpan Delay(int attempt, TimeSpan baseDelay)",
     "public static TimeSpan Delay(int attempt, TimeSpan baseDelay, double jitter = 0)", "XD01"),
    ("D02", "kod rzuca nowy wyjatek, doc nie", "Retry/Backoff.cs",
     "        if (baseDelay <= TimeSpan.Zero)",
     "        if (attempt == 99) throw new InvalidOperationException();\n        if (baseDelay <= TimeSpan.Zero)", "XD03"),
    ("D03", "MaxAttempts 6 -> 8", "Retry/Backoff.cs",
     "public const int MaxAttempts = 6;", "public const int MaxAttempts = 8;", "MD05"),
    ("D04", "zmiana nazwy metody IsTransient", "Retry/Backoff.cs",
     "IsTransient(int httpStatus)", "ShouldRetry(int httpStatus)", "MD02"),
    ("D05", "zmiana nazwy typu wyjatku", "Retry/RetryExhaustedException.cs",
     "RetryExhaustedException", "RetriesExhaustedException", "MD01"),
    ("D06", "MaxDelay 30 s -> 60 s", "Retry/Backoff.cs",
     "TimeSpan.FromSeconds(30)", "TimeSpan.FromSeconds(60)", "MD05"),
    ("D07", "usuniete <returns>", "Retry/Backoff.cs",
     "    /// <returns><c>true</c>, gdy błąd uznajemy za przejściowy.</returns>\n", "", "XD05"),
    ("D08", "status ADR spoza slownika", "docs-good/ADR-0001-exponential-backoff.md",
     "## Status\n\nPrzyjęty", "## Status\n\nWymyślony", "AD02"),
    ("D09", "README wskazuje nieistniejacy plik", "docs-good/README.md",
     "`Retry/Backoff.cs`", "`Retry/Throttle.cs`", "MD03"),
    ("D10", "IsTransient: 500-599 -> 502-504 (tekst doc nie zmieniony)", "Retry/Backoff.cs",
     "(>= 500 and <= 599)", "(>= 502 and <= 504)", None),
    ("D11", "Delay: 2^(attempt-1) -> 2^attempt (zachowanie)", "Retry/Backoff.cs",
     "Math.Pow(2, attempt - 1)", "Math.Pow(2, attempt)", None),
]


def run(cmd: list[str]) -> tuple[int, str]:
    p = subprocess.run(cmd, capture_output=True, text=True)
    return p.returncode, p.stdout + p.stderr


def prepare(tmp: Path) -> None:
    for d in ("Retry", "Retry.Demo", "docs-good"):
        shutil.copytree(HERE / d, tmp / d, ignore=shutil.ignore_patterns("bin", "obj"))


def validator(tmp: Path) -> list[str]:
    rc, out = run([sys.executable, "-B", str(CHECK), "check", "--root", str(tmp), "--src", "Retry", "--docs", str(tmp / "docs-good")])
    return sorted(set(re.findall(r"^\[(\w+)\]", out, re.M))) if rc == 1 else (["OK"] if rc == 0 else ["BLAD"])


def compiler(tmp: Path) -> str:
    rc, out = run(["dotnet", "build", str(tmp / "Retry.Demo" / "Retry.Demo.csproj"), "-nologo"])
    if rc != 0:
        return "BLAD-KOMPILACJI"
    warns = sorted(set(re.findall(r"warning (CS\d+)", out)))
    return ",".join(warns) if warns else "0 ostrzezen"


def demo(tmp: Path, compiled: str) -> str:
    if compiled == "BLAD-KOMPILACJI":
        return "n/d"
    rc, out = run(["dotnet", "run", "--no-build", "--project", str(tmp / "Retry.Demo" / "Retry.Demo.csproj")])
    failed = re.findall(r"^FAIL (.+)$", out, re.M)
    return "OK" if rc == 0 else f"FAIL x{len(failed)}"


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--no-dotnet", action="store_true", help="tylko walidator (bez kompilatora i Retry.Demo)")
    a = ap.parse_args()

    rows = []
    base = Path(tempfile.mkdtemp(prefix="drift-", dir="/tmp"))
    try:
        # linia bazowa
        t0 = base / "base"
        t0.mkdir()
        prepare(t0)
        c0 = "-" if a.no_dotnet else compiler(t0)
        rows.append(("D00", "bez zmian (baseline)", None, validator(t0), c0,
                     "-" if a.no_dotnet else demo(t0, c0)))
        for did, desc, rel, old, new, expect in DRIFTS:
            t = base / did
            t.mkdir()
            prepare(t)
            f = t / rel
            text = f.read_text(encoding="utf-8")
            if old not in text:
                print(f"{did}: brak fragmentu do podmiany w {rel}", file=sys.stderr)
                return 2
            if rel == "Retry/RetryExhaustedException.cs":
                # zmiana nazwy typu musi byc spojna w calym kodzie, inaczej nie kompiluje
                for cs in (t / "Retry").glob("*.cs"):
                    cs.write_text(cs.read_text(encoding="utf-8").replace(old, new), encoding="utf-8")
                demo_cs = t / "Retry.Demo" / "Program.cs"
                demo_cs.write_text(demo_cs.read_text(encoding="utf-8").replace(old, new), encoding="utf-8")
            else:
                f.write_text(text.replace(old, new, 1), encoding="utf-8")
            c = "-" if a.no_dotnet else compiler(t)
            rows.append((did, desc, expect, validator(t), c,
                         "-" if a.no_dotnet else demo(t, c)))
    finally:
        shutil.rmtree(base, ignore_errors=True)

    print(f"{'id':4} {'walidator':16} {'kompilator':18} {'Retry.Demo':10} opis")
    ok = True
    caught_v = caught_c = caught_d = 0
    for did, desc, expect, v, c, d in rows:
        print(f"{did:4} {','.join(v):16} {c:18} {d:10} {desc}")
        if did == "D00":
            ok &= v == ["OK"]
            continue
        det_v = v != ["OK"]
        det_c = c not in ("0 ostrzezen", "-")
        det_d = d not in ("OK", "-", "n/d")
        caught_v += det_v
        caught_c += det_c
        caught_d += det_d
        if expect and expect not in v:
            ok = False
            print(f"   ^ oczekiwano {expect}")
    n = len(DRIFTS)
    print(f"\nwalidator: {caught_v}/{n}  kompilator (nowe ostrzezenia lub blad): {caught_c}/{n}  Retry.Demo: {caught_d}/{n}")
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())
