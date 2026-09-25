#!/usr/bin/env python3
"""Uruchamia kazdy hook z przykladowym JSON-em na stdin i pokazuje exit/stdout/stderr,
a potem sprawdza oczekiwania (exit code). Exit 1, jesli ktorekolwiek sie nie zgadza.
Uzycie: python3 demo_hooks.py
"""
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).parent
PY = sys.executable
H = ROOT / "hooks"
F = ROOT / "fixtures"

CASES = [
    # (opis, argv, fixture, oczekiwany exit)
    ("UserPromptSubmit: czysty prompt -> guard przepuszcza", [PY, H / "ups_secret_guard.py"], "prompt-clean.json", 0),
    ("UserPromptSubmit: haslo w prompcie -> guard blokuje", [PY, H / "ups_secret_guard.py"], "prompt-secret.json", 2),
    ("UserPromptSubmit: hook kontekstowy (stdout -> kontekst)", [PY, H / "ups_context.py"], "prompt-clean.json", 0),
    ("Stop: testy czerwone -> decision=block", [PY, H / "stop_gate.py", ROOT / "sample_broken"], "stop.json", 0),
    ("Stop: testy czerwone, ale stop_hook_active=true -> przepuszcza", [PY, H / "stop_gate.py", ROOT / "sample_broken"], "stop-active.json", 0),
    ("Stop: testy zielone -> cicho, przepuszcza", [PY, H / "stop_gate.py", ROOT / "sample_ok"], "stop.json", 0),
    ("SubagentStop: testy czerwone -> decision=block", [PY, H / "stop_gate.py", ROOT / "sample_broken"], "subagent-stop.json", 0),
]


def main() -> int:
    bad = 0
    for desc, argv, fixture, want in CASES:
        payload = (F / fixture).read_text(encoding="utf-8")
        p = subprocess.run([str(a) for a in argv], input=payload, capture_output=True, text=True)
        ok = p.returncode == want
        bad += not ok
        print(f"### {desc}\n    stdin : {payload.strip()}")
        print(f"    exit  : {p.returncode} (oczekiwano {want}) {'OK' if ok else 'BLAD'}")
        if p.stdout.strip():
            print("    stdout: " + p.stdout.strip().replace("\n", "\n            "))
        if p.stderr.strip():
            print("    stderr: " + p.stderr.strip().replace("\n", "\n            "))
        print()
    print(f"WYNIK: {len(CASES) - bad}/{len(CASES)} zgodnych")
    return 1 if bad else 0


if __name__ == "__main__":
    sys.exit(main())
