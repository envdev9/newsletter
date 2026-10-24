"""Dziennik WAL z tokenem ogrodzeniowym w KAZDYM rekordzie - wydanie #29.

Wydanie #25 ogrodzilo zasob (FencedLog sprawdza token przy zapisie). Tu pytanie: co, gdy zapisu
NIE da sie bramkowac (zwykly O_APPEND, magazyn bez warunkowego zapisu)? Wtedy token sprawdza CZYTELNIK:
fold() odrzuca rekord, ktorego token jest mniejszy niz najwyzszy widziany wczesniej w pliku.

Journal.append  - jeden os.write() na rekord (O_APPEND), plik otwierany przy kazdym zapisie.
fold(fence=...) - skladanie stanu; fence=False to wersja naiwna (ostatni zapis wygrywa).
compact         - snapshot (os.replace); carry_hw=False to CELOWO bledna wersja do testu.
Tylko stdlib, Linux, Python 3.10.
"""
from __future__ import annotations

import json
import os
from dataclasses import dataclass, field
from typing import Optional


def encode(rec: dict) -> bytes:
    return (json.dumps(rec, separators=(",", ":"), sort_keys=True) + "\n").encode()


class Journal:
    def __init__(self, path: str) -> None:
        self.path = path

    def append(self, rec: dict) -> None:
        fd = os.open(self.path, os.O_WRONLY | os.O_APPEND | os.O_CREAT, 0o644)
        try:
            os.write(fd, encode(rec))
        finally:
            os.close(fd)

    def read(self) -> tuple[list[dict], int]:
        """(rekordy, liczba_uszkodzonych_wierszy). Urwany ostatni wiersz (bez \\n) jest pomijany."""
        try:
            with open(self.path, "rb") as f:
                raw = f.read()
        except FileNotFoundError:
            return [], 0
        recs, bad = [], 0
        for i, line in enumerate(raw.split(b"\n")):
            if not line:
                continue
            try:
                recs.append(json.loads(line))
            except json.JSONDecodeError:
                bad += 1
        return recs, bad


@dataclass
class State:
    steps: dict = field(default_factory=dict)      # step -> {"who", "tok"}
    done_by: Optional[str] = None
    hw: int = 0                                     # najwyzszy token widziany (high-water mark)
    dropped: list = field(default_factory=list)     # id odrzuconych rekordow

    def summary(self) -> dict:
        return {
            "steps": {s: f'{v["who"]}/t{v["tok"]}' for s, v in sorted(self.steps.items())},
            "done_by": self.done_by,
            "hw": self.hw,
            "dropped": len(self.dropped),
        }


def fold(recs: list[dict], fence: bool = True) -> State:
    st = State()
    for r in recs:
        tok = r.get("tok", 0)
        if fence and tok < st.hw:
            st.dropped.append(r.get("id", "?"))
            continue
        st.hw = max(st.hw, tok)
        op = r["op"]
        if op == "snapshot":
            st.steps = {int(k): dict(v) for k, v in r["steps"].items()}
            st.done_by = r.get("done_by")
        elif op == "step":
            st.steps[r["step"]] = {"who": r["who"], "tok": tok}
        elif op == "done":
            st.done_by = r["who"]
        # "barrier" tylko podnosi hw
    return st


def compact(journal: Journal, carry_hw: bool = True) -> None:
    """Zastepuje dziennik jednym snapshotem. carry_hw=False gubi high-water mark (BLAD, do testu)."""
    recs, _ = journal.read()
    st = fold(recs)
    snap = {
        "op": "snapshot",
        "tok": st.hw if carry_hw else 0,
        "id": "snapshot",
        "steps": {str(s): v for s, v in st.steps.items()},
        "done_by": st.done_by,
    }
    tmp = f"{journal.path}.tmp.{os.getpid()}"
    with open(tmp, "wb") as f:
        f.write(encode(snap))
        f.flush()
        os.fsync(f.fileno())
    os.replace(tmp, journal.path)
