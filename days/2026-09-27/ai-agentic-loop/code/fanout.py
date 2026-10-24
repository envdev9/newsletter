#!/usr/bin/env python3
"""Fan-out / fan-in: rownolegle 'subagenty' (procesy) + scalanie wynikow.

Fan-out: kazda rola = osobny proces (odpowiednik osobnego okna kontekstu).
Fan-in (merge):
  1. dedupe po (file, line, category) - dwie role widza to samo -> jedno znalezisko, obie w 'roles',
     severity = najwyzsza z zaglaszajacych,
  2. sort: severity malejaco, potem plik/linia,
  3. limit --top N (rodzic nie ma dostac 3000 tokenow prozy),
  4. awaria workera NIE jest cicha: raport mowi 'PARTIAL', exit code = 1.
Exit: 0 = brak znalezisk high i brak awarii; 1 = sa high LUB ktorys worker padl; 2 = zle uzycie.
"""
import argparse
import json
import subprocess
import sys
import time
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

SEV = {"high": 3, "medium": 2, "low": 1}
HERE = Path(__file__).resolve().parent


def run_role(role: str, files, delay: float):
    t0 = time.monotonic()
    p = subprocess.run([sys.executable, str(HERE / "reviewer.py"), "--role", role,
                        "--delay", str(delay), *files], capture_output=True, text=True)
    findings = []
    if p.returncode == 0:
        findings = [json.loads(l) for l in p.stdout.splitlines() if l.strip()]
    return {"role": role, "rc": p.returncode, "err": p.stderr.strip(),
            "findings": findings, "secs": time.monotonic() - t0}


def merge(results):
    merged = {}
    for r in results:
        for f in r["findings"]:
            key = (f["file"], f["line"], f["category"])
            m = merged.setdefault(key, {**f, "roles": []})
            m["roles"].append(f["role"])
            if SEV[f["severity"]] > SEV[m["severity"]]:
                m["severity"] = f["severity"]
    out = list(merged.values())
    out.sort(key=lambda m: (-SEV[m["severity"]], m["file"], m["line"]))
    return out


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--roles", default="security,concurrency,perf,style")
    ap.add_argument("--delay", type=float, default=0.5)
    ap.add_argument("--sequential", action="store_true")
    ap.add_argument("--top", type=int, default=10)
    ap.add_argument("files", nargs="+")
    a = ap.parse_args()
    roles = a.roles.split(",")

    t0 = time.monotonic()
    if a.sequential:
        results = [run_role(r, a.files, a.delay) for r in roles]
    else:
        with ThreadPoolExecutor(max_workers=len(roles)) as ex:
            results = list(ex.map(lambda r: run_role(r, a.files, a.delay), roles))
    wall = time.monotonic() - t0

    failed = [r for r in results if r["rc"] != 0]
    merged = merge(results)
    raw = sum(len(r["findings"]) for r in results)
    print(f"tryb: {'sekwencyjnie' if a.sequential else 'rownolegle'}; wall={wall:.2f}s; "
          f"suma czasow workerow={sum(r['secs'] for r in results):.2f}s")
    print(f"surowo: {raw} znalezisk -> po scaleniu: {len(merged)}")
    for m in merged[: a.top]:
        print(f"{m['file']}:{m['line']} - {m['severity']} - {m['category']} - {m['msg']} "
              f"[{'+'.join(m['roles'])}]")
    if len(merged) > a.top:
        print(f"... i {len(merged) - a.top} nizszych (ucieto do --top {a.top})")
    for r in failed:
        print(f"WORKER PADL: {r['role']} (rc={r['rc']}) {r['err']}")
    if failed:
        print(f"PARTIAL: raport niekompletny - {len(failed)} z {len(roles)} workerow padlo")
    return 1 if failed or any(m["severity"] == "high" for m in merged) else 0


if __name__ == "__main__":
    sys.exit(main())
