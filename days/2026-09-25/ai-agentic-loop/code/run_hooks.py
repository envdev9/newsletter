#!/usr/bin/env python3
"""SYMULATOR kompozycji hookow - NIE jest to prawdziwy harness Claude Code.

Robi to, co wg dokumentacji robi harness: dla jednego eventu odpala WSZYSTKIE pasujace
hooki rownolegle, kazdemu podaje ten sam JSON na stdin, po czym laczy wyniki.
Sluzy do pokazania skutkow (czas, kolejnosc, laczenie decyzji), nie do dowodzenia,
ze prawdziwy harness robi dokladnie tak. Zasady laczenia zaimplementowane tutaj:
  * exit 2 z dowolnego hooka            -> BLOK (stderr = powod)
  * exit 0 + JSON {"decision":"block"}  -> BLOK (reason = powod)
  * exit 0 + stdout (UserPromptSubmit)  -> kontekst; doklejany, gdy nikt nie blokuje
  * inny exit                           -> blad niekrytyczny, tylko raport
Wyniki wypisujemy w kolejnosci z konfiguracji (deterministycznie), choc hooki
skonczyly sie w dowolnej kolejnosci - w prawdziwym harnessie na kolejnosc NIE licz.

Uzycie: run_hooks.py <event> <plik_z_json_stdin> <komenda_hooka> [<komenda_hooka> ...]
"""
import json
import subprocess
import sys
import time
from concurrent.futures import ThreadPoolExecutor


def run_one(cmd: str, payload: str):
    t0 = time.perf_counter()
    p = subprocess.run(cmd, shell=True, input=payload, capture_output=True, text=True)
    return cmd, p.returncode, p.stdout.strip(), p.stderr.strip(), time.perf_counter() - t0


def main() -> int:
    event, payload_file, *cmds = sys.argv[1:]
    payload = open(payload_file, encoding="utf-8").read()
    t0 = time.perf_counter()
    with ThreadPoolExecutor(max_workers=len(cmds)) as pool:
        results = list(pool.map(lambda c: run_one(c, payload), cmds))
    wall = time.perf_counter() - t0

    blocks, contexts = [], []
    for cmd, code, out, err, dt in results:
        print(f"- {cmd}\n    exit={code} czas={dt:.2f}s")
        if out:
            print(f"    stdout: {out}")
        if err:
            print(f"    stderr: {err}")
        if code == 2:
            blocks.append(err)
        elif code == 0 and out:
            try:
                data = json.loads(out)
            except json.JSONDecodeError:
                data = None
            if isinstance(data, dict) and data.get("decision") == "block":
                blocks.append(data.get("reason", ""))
            elif event == "UserPromptSubmit" and data is None:
                contexts.append(out)
    sum_dt = sum(r[4] for r in results)
    print(f"\nCZAS scienny: {wall:.2f}s (suma czasow hookow: {sum_dt:.2f}s)")
    if blocks:
        print("WYNIK POLACZONY: BLOK")
        for b in blocks:
            print(f"  powod: {b}")
        return 2
    print("WYNIK POLACZONY: PRZEPUSZCZONE")
    for c in contexts:
        print(f"  kontekst do modelu: {c!r}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
