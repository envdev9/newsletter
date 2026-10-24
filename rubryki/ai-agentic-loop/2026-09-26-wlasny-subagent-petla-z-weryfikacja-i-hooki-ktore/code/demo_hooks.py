#!/usr/bin/env python3
"""Uruchamia hooki PreCompact/SessionStart z fixtur w tymczasowym katalogu i sprawdza skutki.
Placeholder __CWD__ w fixturach zastepowany jest katalogiem tymczasowym. Nic nie zapisuje w repo.
Uzycie: python3 demo_hooks.py    (exit 1, jesli ktorykolwiek przypadek sie nie zgadza)
"""
import os
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).parent
PY = sys.executable
PRE = ROOT / "hooks" / "precompact_snapshot.py"
SS = ROOT / "hooks" / "sessionstart_restore.py"
results = []


def run(script, fixture, cwd: Path, extra_env=None):
    payload = (ROOT / "fixtures" / fixture).read_text(encoding="utf-8").replace("__CWD__", str(cwd))
    env = {**os.environ, **(extra_env or {})}
    return subprocess.run([PY, str(script)], input=payload, capture_output=True, text=True, env=env)


def check(desc, cond, p, extra=""):
    results.append(cond)
    print(f"### {desc}\n    exit  : {p.returncode}\n    stdout: " +
          (p.stdout.strip().replace("\n", "\n            ") or "(pusto)"))
    if p.stderr.strip():
        print("    stderr: " + p.stderr.strip())
    if extra:
        print("    " + extra)
    print(f"    -> {'OK' if cond else 'BLAD'}\n")


def main() -> int:
    with tempfile.TemporaryDirectory(prefix="hooks-demo-") as t:
        cwd = Path(t) / "proj"
        cwd.mkdir()
        shutil.copy(ROOT / "sample-tasks" / "TASKS.md", cwd / "TASKS.md")
        snap = cwd / "claude-state" / "precompact-abc-123.md"

        p = run(PRE, "precompact-auto.json", cwd)
        check("PreCompact (auto): zapisuje snapshot pliku zadan", p.returncode == 0 and snap.is_file(), p,
              "plik snapshotu: " + snap.read_text(encoding="utf-8").splitlines()[0] if snap.is_file() else "")

        p = run(SS, "sessionstart-compact.json", cwd)
        check("SessionStart (compact): stdout = odtworzony stan zadan",
              p.returncode == 0 and "W TOKU" in p.stdout, p)

        p = run(SS, "sessionstart-compact.json", cwd, {"MAX_CHARS": "60"})
        check("SessionStart (compact) z MAX_CHARS=60: obciete", "[...obciete...]" in p.stdout, p)

        p = run(SS, "sessionstart-startup.json", cwd)
        check("SessionStart (startup): tylko data", "Dzisiejsza data" in p.stdout and "W TOKU" not in p.stdout, p)

        p = run(SS, "sessionstart-clear.json", cwd)
        check("SessionStart (clear): cisza", p.returncode == 0 and not p.stdout.strip(), p)

        empty = Path(t) / "empty"
        empty.mkdir()
        p = run(SS, "sessionstart-compact.json", empty)
        check("SessionStart (compact) bez snapshotu: komunikat awaryjny", "brak snapshotu" in p.stdout, p)

        p = run(PRE, "precompact-traversal.json", cwd)
        inside = cwd / "claude-state" / "precompact-evil.md"
        outside = [f for f in Path(t).rglob("*evil*") if cwd / "claude-state" not in f.parents]
        check("PreCompact: session_id '../../evil' nie wychodzi poza katalog snapshotow",
              p.returncode == 0 and inside.is_file() and not outside, p,
              f"zapisano: {inside.relative_to(t)}; poza katalogiem: {len(outside)} plikow")
    print(f"WYNIK: {sum(results)}/{len(results)} zgodnych")
    return 0 if all(results) else 1


if __name__ == "__main__":
    sys.exit(main())
