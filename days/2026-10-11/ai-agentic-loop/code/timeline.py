"""Zlozenie segmentow archiwum dziennika (journal.jsonl.archive-NNNNN) + zywy plik w JEDNA os zdarzen.

Po kompaktowaniu z archive=True mamy kilka plikow: kazdy zaczyna sie rekordem `snapshot`
(pochodna: stan po poprzednim segmencie), a dalej ma surowe zdarzenia. Os zdarzen = surowe zdarzenia
wszystkich segmentow w kolejnosci, BEZ rekordow `snapshot` (to widok zapisany do szybkiego wznowienia,
nie zdarzenie) i bez duplikatow.

Trzy kontrole, zamiast zaufania:
  1. ciaglosc: `snapshot.summary.total` musi rownac sie liczbie krokow zlozonych dotad (inaczej
     brakuje segmentu: TimelineGap),
  2. rownowaznosc: fold(os zdarzen) musi dac TEN SAM stan co fold(zywy plik) (podsumowanie, pending,
     last_end, vt, okno krokow),
  3. brak duplikatow: ten sam krok/koniec zapisany w dwoch segmentach liczy sie raz.
"""
from __future__ import annotations

import glob
import json
import os
import re
from dataclasses import dataclass
from typing import Optional

from agentloop import Journal, State, fold


class TimelineGap(Exception):
    """Brakuje segmentu archiwum (lub zdarzen) - os czasu nie jest kompletna."""


class TimelineMismatch(Exception):
    """Zlozona os nie daje stanu zywego dziennika - archiwum i zywy plik opowiadaja rozne historie."""


def event_key(rec: dict) -> tuple:
    """Tozsamosc zdarzenia, zeby segmenty o wspolnym fragmencie nie liczyly go dwa razy."""
    t = rec["t"]
    if t in ("intent", "result"):
        return (t, rec["step"])
    if t == "resolve":
        return (t, rec["step"], rec["outcome"])
    if t == "end":
        return (t, rec["status"], rec["reason"], rec.get("vt"))
    raise ValueError(f"nieznany rekord {t!r}")


def segments(journal_path: str) -> list[str]:
    """Pliki archiwum posortowane po numerze (liczba krokow w chwili kompaktowania) + zywy plik."""
    found = []
    for p in glob.glob(glob.escape(journal_path) + ".archive-*"):
        m = re.search(r"\.archive-(\d+)$", p)
        if m:
            found.append((int(m.group(1)), p))
    return [p for _n, p in sorted(found)] + [journal_path]


@dataclass
class Timeline:
    events: list[dict]
    segments: list[str]
    duplicates_dropped: int
    snapshots_seen: int


def merge(journal_path: str) -> Timeline:
    events: list[dict] = []
    seen: set[tuple] = set()
    dups = snaps = 0
    segs = [p for p in segments(journal_path) if os.path.exists(p)]
    for path in segs:
        for rec in Journal(path, repair=False).read():
            if rec["t"] == "snapshot":
                snaps += 1
                have = fold(events).summary.total
                if have != rec["summary"]["total"]:
                    raise TimelineGap(
                        f"{os.path.basename(path)}: snapshot oczekuje {rec['summary']['total']} krokow "
                        f"wczesniej, a w osi jest {have}")
                continue
            k = event_key(rec)
            if k in seen:
                dups += 1
                continue
            seen.add(k)
            events.append(rec)
    return Timeline(events, segs, dups, snaps)


def _comparable(s: State) -> dict:
    return {"summary": s.summary.to_dict(), "pending": s.pending, "last_end": s.last_end,
            "vt": s.vt, "approved": s.approved_retry,
            "window": [(x.n, x.action.tool, x.ok, x.out, x.attempts) for x in s.steps]}


def verify(journal_path: str) -> Timeline:
    """merge() + kontrola rownowaznosci z zywym plikiem. Zwraca os albo rzuca wyjatek."""
    tl = merge(journal_path)
    live = fold(Journal(journal_path, repair=False).read())
    full = fold(tl.events)
    a, b = _comparable(full), _comparable(live)
    keep = len(live.steps)
    a["window"] = a["window"][-keep:] if keep else []
    for k in a:
        if a[k] != b[k]:
            raise TimelineMismatch(f"pole '{k}': os={a[k]!r:.120} zywy={b[k]!r:.120}")
    return tl


def write_full(journal_path: str, out_path: str) -> int:
    """Zapisuje zlozona os jako zwykly dziennik (zdarzenia bez snapshotow). Zwraca liczbe rekordow."""
    tl = verify(journal_path)
    tmp = out_path + ".tmp"
    with open(tmp, "w", encoding="utf-8") as f:
        for r in tl.events:
            f.write(json.dumps(r, ensure_ascii=False) + "\n")
        f.flush()
        os.fsync(f.fileno())
    os.replace(tmp, out_path)
    return len(tl.events)


def explain_step(tl: Timeline, step: int) -> Optional[dict]:
    """Odpowiedz na pytanie audytowe 'co sie stalo z krokiem N': intent + result + resolve."""
    out = {"intent": None, "result": None, "resolve": None, "th": None}
    for r in tl.events:
        if r.get("step") == step and r["t"] in out:
            out[r["t"]] = r
    out["th"] = (out["result"] or {}).get("th")
    return out if out["intent"] else None
