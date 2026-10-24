#!/usr/bin/env python3
"""Zewnetrzna petla z weryfikacja: worker -> weryfikacja -> (feedback) -> worker ... max N razy.

Kluczowa zasada: o sukcesie decyduje EXIT CODE weryfikatora (testy), nie deklaracja workera.
Worker dostaje poprzednia porazke w pliku wskazanym przez env FEEDBACK_FILE i katalog projektu
jako ostatni argument. Projekt jest kopiowany do katalogu tymczasowego - oryginal nietkniety.

Uzycie:
  python3 verify_loop.py --project loop-demo/project --max-iter 3 \
      --worker "python3 loop-demo/scripted_worker.py" --verify "python3 -m unittest -q"
Podmiana workera na prawdziwego agenta: patrz README (komenda `claude -p`, NIEZWERYFIKOWANA).
Exit: 0 = zielone, 1 = wyczerpano limit iteracji, 2 = zle uzycie.
"""
import argparse
import os
import shlex
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path


def run(cmd: str, cwd: Path, env=None, extra=()):
    return subprocess.run(shlex.split(cmd) + list(extra), cwd=cwd, env=env,
                          capture_output=True, text=True)


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--project", required=True)
    ap.add_argument("--worker", required=True)
    ap.add_argument("--verify", required=True)
    ap.add_argument("--max-iter", type=int, default=3)
    a = ap.parse_args()

    src = Path(a.project).resolve()
    worker = a.worker.split(" ")
    worker[-1] = str(Path(worker[-1]).resolve())  # sciezka skryptu workera bezwzgledna
    worker_cmd = " ".join(worker)

    with tempfile.TemporaryDirectory(prefix="loop-") as tmp:
        work = Path(tmp) / "project"
        shutil.copytree(src, work, ignore=shutil.ignore_patterns("__pycache__"))
        fb = Path(tmp) / "feedback.txt"
        env = {**os.environ, "FEEDBACK_FILE": str(fb)}
        for i in range(1, a.max_iter + 1):
            print(f"=== iteracja {i}/{a.max_iter}")
            w = run(worker_cmd, work, env, [str(work)])
            print("  " + (w.stdout.strip() or "(worker bez outputu)").replace("\n", "\n  "))
            v = run(a.verify, work)
            tail = "\n".join((v.stdout + v.stderr).strip().splitlines()[-12:])
            print(f"  weryfikacja: exit={v.returncode}")
            if v.returncode == 0:
                print(f"SUKCES po {i} iteracji(ach)")
                return 0
            fb.write_text(tail, encoding="utf-8")
            print("  feedback dla nastepnej iteracji:\n    " + tail.replace("\n", "\n    "))
        print(f"PORAZKA: limit {a.max_iter} iteracji wyczerpany, testy dalej czerwone")
        return 1


if __name__ == "__main__":
    sys.exit(main())
