#!/usr/bin/env python3
"""ATRAPA 'claude -p --output-format json' - NIE jest to Claude ani jego prawdziwy format.

Nazwy pol (type, is_error, result, num_turns) sa Z PAMIECI i niezweryfikowane; sluza tylko do
przecwiczenia logiki bramki CI. Scenariusz z argv[1]: ok | error | badjson | hang | toomany
"""
import json
import sys
import time

scenario = sys.argv[1] if len(sys.argv) > 1 else "ok"
if scenario == "ok":
    print(json.dumps({"type": "result", "is_error": False, "num_turns": 4,
                      "result": "Naprawiono test_sub."}))
elif scenario == "toomany":
    print(json.dumps({"type": "result", "is_error": False, "num_turns": 40, "result": "..."}))
elif scenario == "error":
    print(json.dumps({"type": "result", "is_error": True, "num_turns": 2, "result": "limit"}))
    sys.exit(1)
elif scenario == "badjson":
    print("to nie jest json")
elif scenario == "hang":
    time.sleep(30)
