#!/usr/bin/env python3
"""Testy calosci: fan-out/merge, polityka uprawnien, bramka CI. Uruchom z katalogu code/."""
import json
import os
import subprocess
import sys
import time

os.chdir(os.path.dirname(os.path.abspath(__file__)))
PY = sys.executable
FILES = ["sample-src/OrderService.cs", "sample-src/Cache.cs"]
results = []


def check(name, cond, detail=""):
    results.append(cond)
    print(f"[{'OK ' if cond else 'BLAD'}] {name} {detail}")


def sh(*args):
    return subprocess.run([PY, *args], capture_output=True, text=True)


# --- fan-out / merge ---
par = sh("fanout.py", "--delay", "0.5", *FILES)
seq = sh("fanout.py", "--delay", "0.5", "--sequential", *FILES)
w = lambda o: float(o.stdout.split("wall=")[1].split("s")[0])
check("rownolegle szybciej niz sekwencyjnie", w(par) < w(seq) * 0.6,
      f"(par={w(par):.2f}s seq={w(seq):.2f}s)")
check("ten sam wynik po scaleniu (poza naglowkiem)",
      par.stdout.splitlines()[1:] == seq.stdout.splitlines()[1:])
check("dedupe: .Result widziane przez 2 role = 1 znalezisko z 'concurrency+perf'",
      "concurrency+perf" in par.stdout)
check("exit 1 gdy sa znaleziska high", par.returncode == 1)
top = sh("fanout.py", "--delay", "0", "--top", "2", *FILES)
check("--top ucina liste", "nizszych (ucieto do --top 2)" in top.stdout)
crash = sh("fanout.py", "--roles", "style,crash", "--delay", "0", "sample-src/Cache.cs")
check("awaria workera => PARTIAL i exit 1 (nawet bez znalezisk high)",
      "PARTIAL" in crash.stdout and crash.returncode == 1)
clean = sh("fanout.py", "--roles", "style", "--delay", "0", "sample-src/Cache.cs")
check("czysty plik + zdrowe workery => exit 0", clean.returncode == 0)

# --- polityka uprawnien ---
cfg = json.load(open("policy-headless.json"))
sys.path.insert(0, ".")
from permission_policy import decide  # noqa: E402

D = lambda mode, tool, arg="", **k: decide(mode, cfg["allow"], cfg["deny"], tool, arg, **k)[0]
check("deny wygrywa z bypassPermissions", D("bypassPermissions", "Bash", "rm -rf x") == "deny")
check("plan blokuje Edit", D("plan", "Edit", "a.cs") == "deny")
check("acceptEdits puszcza Edit", D("acceptEdits", "Edit", "a.cs") == "allow")
check("default interaktywnie pyta o Edit", D("default", "Edit", "a.cs", interactive=True) == "ask")
check("default headless odmawia Edit", D("default", "Edit", "a.cs") == "deny")
check("allow dla 'dotnet test*'", D("default", "Bash", "dotnet test") == "allow")

# --- bramka CI ---
GATE = ["ci_gate.py", "--project", "gate-project", "--timeout", "2"]
def gate(scn, verify="test_ok", extra=()):
    return sh(*GATE, "--agent", f"{PY} ../fake_claude.py {scn}",
              "--verify", f"{PY} -m unittest -q {verify}", *extra).returncode

check("ok + zielony weryfikator => 0", gate("ok") == 0)
check("ok + czerwony weryfikator => 14", gate("ok", "test_red") == 14)
check("is_error/exit!=0 => 11", gate("error") == 11)
check("zly JSON => 12", gate("badjson") == 12)
t = time.monotonic()
check("zawieszony agent => timeout 10", gate("hang") == 10 and time.monotonic() - t < 10)
check("za duzo tur => 13", gate("toomany", extra=["--max-turns", "10"]) == 13)

print(f"WYNIK: {sum(results)}/{len(results)}")
sys.exit(0 if all(results) else 1)
