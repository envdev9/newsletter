#!/usr/bin/env python3
"""Stop / SubagentStop: nie pozwol skonczyc, dopoki testy sa czerwone.

Uzycie: stop_gate.py <katalog_z_testami>   (uruchamia: python3 -m unittest discover -s <katalog>)

Kontrakt (JSON, exit 0):
  {"decision": "block", "reason": "..."}  -> agent NIE konczy, `reason` wraca do niego
  brak decision                           -> agent konczy normalnie
Bezpiecznik przed petla nieskonczona: jesli stdin ma `stop_hook_active: true`, agent juz raz
zostal zawrocony przez Stop-hook w tej turze - wtedy przepuszczamy.
"""
import json
import subprocess
import sys


def main() -> int:
    if len(sys.argv) != 2:
        sys.stderr.write("uzycie: stop_gate.py <katalog_z_testami>\n")
        return 1
    try:
        event = json.load(sys.stdin)
    except json.JSONDecodeError:
        event = {}
    if event.get("stop_hook_active"):
        print("stop_gate: stop_hook_active=true - przepuszczam (bezpiecznik przed petla)")
        return 0
    proc = subprocess.run(
        [sys.executable, "-m", "unittest", "discover", "-s", sys.argv[1]],
        capture_output=True, text=True,
    )
    if proc.returncode == 0:
        return 0
    tail = "\n".join(proc.stderr.strip().splitlines()[-12:])
    who = event.get("hook_event_name", "Stop")
    print(json.dumps({
        "decision": "block",
        "reason": f"[{who}] Testy sa czerwone - nie konczysz. Napraw i uruchom ponownie:\n{tail}",
    }, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    sys.exit(main())
