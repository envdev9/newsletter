"""Demo #29: token w dzienniku WAL. Uruchom: python3 -B demo.py"""
from __future__ import annotations

import json
import os
import shutil
import tempfile

import scen
from wal import Journal, compact, fold


def show(title: str, r: dict) -> None:
    print(f"== {title}")
    print("  fold z tokenem  :", json.dumps(r["fenced"]))
    print("  fold naiwny     :", json.dumps(r["naive"]))
    print("  skutki na krok  :", r["effects_per_step"], "| duplikaty:", r["dup_steps"], "| brakujace:", r["missing_steps"])
    print("  kolejnosc skutkow:", [e.replace(" tok=", "/t").replace(" step=", ":") for e in r["effects"]])


def offline() -> None:
    print("== 5. offline: snapshot musi niesc high-water mark; stary fd po compact")
    for carry in (True, False):
        d = tempfile.mkdtemp(prefix="prasowka-fence-")
        try:
            j = Journal(os.path.join(d, "j.jsonl"))
            j.append({"op": "barrier", "tok": 1, "who": "A", "id": "A1b"})
            j.append({"op": "step", "step": 0, "tok": 1, "who": "A", "id": "A1s0"})
            j.append({"op": "barrier", "tok": 2, "who": "B", "id": "B2b"})
            j.append({"op": "step", "step": 1, "tok": 2, "who": "B", "id": "B2s1"})
            compact(j, carry_hw=carry)
            j.append({"op": "step", "step": 1, "tok": 1, "who": "A", "id": "A1s1-zombie"})   # zombie po compact
            st = fold(j.read()[0])
            print(f"  carry_hw={carry!s:5}: krok1 zapisal {st.steps[1]['who']}/t{st.steps[1]['tok']}, hw={st.hw}, odrzucone={st.dropped}")
        finally:
            shutil.rmtree(d, ignore_errors=True)
    d = tempfile.mkdtemp(prefix="prasowka-fence-")
    try:
        p = os.path.join(d, "j.jsonl")
        j = Journal(p)
        j.append({"op": "barrier", "tok": 2, "who": "B", "id": "B2b"})
        fd = os.open(p, os.O_WRONLY | os.O_APPEND)             # zombie trzyma deskryptor sprzed compact
        compact(j)
        os.write(fd, b'{"op":"step","step":9,"tok":1,"who":"A","id":"late"}\n')
        os.close(fd)
        print("  zapis przez stary fd po compact: rekordow w dzienniku =", len(j.read()[0]),
              "(1 = snapshot; zapis zombie trafil do osieroconego i-node'a)")
    finally:
        shutil.rmtree(d, ignore_errors=True)


def main() -> None:
    show("1. blind, A zamrozony PRZED krokiem 2 (SIGSTOP), B przejmuje, A wznowiony", scen.run("blind", "A pre:2"))
    show("2. intent, ta sama zamrozenie przed krokiem 2", scen.run("intent", "A pre:2"))
    show("3. intent, A zamrozony w OKNIE miedzy sprawdzeniem a skutkiem (pause 0.4 s), potem SIGCONT",
         scen.run("intent", "A checked:2", pause=0.4))
    show("4. intent, A zamrozony w oknie i zabity (SIGKILL)", scen.run("intent", "A checked:2", pause=0.4, kill=True))
    offline()


if __name__ == "__main__":
    main()
