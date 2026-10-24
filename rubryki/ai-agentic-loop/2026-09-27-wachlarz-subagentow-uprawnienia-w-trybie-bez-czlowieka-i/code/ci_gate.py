#!/usr/bin/env python3
"""Bramka CI wokol headless agenta: agent -> parsowanie JSON -> NIEZALEZNY weryfikator -> exit code.

Zasady (te same co w petli z #3, ale dla jednego wywolania w pipeline):
  * timeout na agenta (zawieszony agent nie moze zablokowac agenta buildowego),
  * output nie-JSON albo is_error=true albo za duzo tur -> awaria bramki,
  * NAWET gdy agent mowi 'ok', o zielonym decyduje weryfikator (exit code testow).
Exit: 0 zielone; 10 timeout; 11 agent zglosil blad / exit != 0; 12 zly JSON; 13 za duzo tur;
      14 weryfikator czerwony.
Uzycie: python3 ci_gate.py --agent "python3 fake_claude.py ok" --verify "python3 -m unittest -q" \
        --project loop-demo --max-turns 10 --timeout 5
"""
import argparse
import json
import shlex
import subprocess
import sys


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--agent", required=True)
    ap.add_argument("--verify", required=True)
    ap.add_argument("--project", default=".")
    ap.add_argument("--max-turns", type=int, default=10)
    ap.add_argument("--timeout", type=float, default=60)
    a = ap.parse_args()

    try:
        p = subprocess.run(shlex.split(a.agent), cwd=a.project, capture_output=True, text=True,
                           timeout=a.timeout)
    except subprocess.TimeoutExpired:
        print(f"GATE: timeout agenta po {a.timeout}s")
        return 10
    if p.returncode != 0:
        print(f"GATE: agent exit={p.returncode}")
        return 11
    try:
        out = json.loads(p.stdout)
    except json.JSONDecodeError:
        print("GATE: stdout agenta to nie JSON")
        return 12
    if out.get("is_error"):
        print("GATE: agent zglosil is_error=true")
        return 11
    if out.get("num_turns", 0) > a.max_turns:
        print(f"GATE: {out['num_turns']} tur > limit {a.max_turns}")
        return 13
    print(f"agent: {out.get('result')!r} (tur: {out.get('num_turns')})")
    v = subprocess.run(shlex.split(a.verify), cwd=a.project, capture_output=True, text=True)
    print(f"weryfikator exit={v.returncode}")
    if v.returncode != 0:
        print("GATE: agent twierdzi sukces, ale weryfikator jest czerwony")
        return 14
    print("GATE: zielone")
    return 0


if __name__ == "__main__":
    sys.exit(main())
