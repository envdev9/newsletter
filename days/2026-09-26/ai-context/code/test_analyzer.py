#!/usr/bin/env python3
"""Testy analizatora na ręcznie policzonym mini-transkrypcie (wyniki znane z góry)."""

import json
import os
import tempfile

from analyze_transcript import load_events, simulate


def write(records):
    fd, path = tempfile.mkstemp(suffix=".jsonl")
    with os.fdopen(fd, "w", encoding="utf-8") as f:
        for r in records:
            f.write(json.dumps(r) + "\n")
        f.write("to nie jest json\n")  # śmieć ma zostać pominięty
    return path


def asst(tid, name):
    return {"type": "assistant", "message": {"content": [{"type": "tool_use", "id": tid, "name": name, "input": {}}]}}


def res(tid, n):
    return {"type": "user", "message": {"content": [{"type": "tool_result", "tool_use_id": tid, "content": "x" * n}]}}


def main() -> None:
    path = write([asst("a", "Read"), res("a", 40000), asst("b", "Grep"), res("b", 400),
                  {"type": "system", "foo": 1}])
    try:
        events, _ = load_events(path)
        results = [(e[1], e[2]) for e in events if e[0] == "result"]
        assert results == [("Read", 40000), ("Grep", 400)], results
        assert sum(1 for e in events if e[0] == "assistant") == 2

        # baza 1000; tura 1 czyta 1000; potem +10000 (Read); tura 2 czyta ~11000+
        peak, total, comp = simulate(events, 1000)
        assert comp == 0
        assert peak > 11000 and total > 1000 + 11000, (peak, total)

        # delegacja: wynik 10000 tok. -> raport 150; Grep (100 tok.) zostaje
        peak_d, total_d, _ = simulate(events, 1000, delegate_over=3000, report_tokens=150)
        assert peak_d < 2000 and total_d < total / 3, (peak_d, total_d)

        # compact po przekroczeniu 5000 tok.: Read wywoła jedno zwinięcie do base+summary
        _, _, comp2 = simulate(events, 1000, compact_limit=5000, summary_tokens=500)
        assert comp2 == 1, comp2
    finally:
        os.remove(path)
    print("OK: 6/6 asercji przeszło")


if __name__ == "__main__":
    main()
