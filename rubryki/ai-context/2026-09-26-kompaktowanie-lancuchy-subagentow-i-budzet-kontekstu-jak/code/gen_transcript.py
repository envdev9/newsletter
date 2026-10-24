#!/usr/bin/env python3
"""Generuje SYNTETYCZNY transkrypt sesji w formacie .jsonl przypominającym Claude Code.

Uwaga (uczciwie): to NIE jest prawdziwa sesja. Kształt rekordów (type user/assistant,
message.content[] z blokami text/tool_use/tool_result, message.usage z polami
input_tokens / cache_creation_input_tokens / cache_read_input_tokens / output_tokens)
jest zgodny z tym, co opisano w wydaniu #1 rubryki. Nie porównywano go z aktualną
wersją klienta - analizator jest tolerancyjny (pomija rekordy, których nie rozumie).

Deterministyczny (seed=7): to samo wejście -> ten sam plik -> powtarzalny output.

Użycie:
    python3 gen_transcript.py session.jsonl
"""

import json
import random
import sys

SEED = 7
BASE_TOKENS = 18_000  # system prompt + schematy narzędzi + CLAUDE.md (stała część startowa)

# (narzędzie, waga losowania, min/max znaków wyniku)
TOOLS = [
    ("Read", 30, (800, 60_000)),
    ("Grep", 20, (200, 6_000)),
    ("Bash", 25, (50, 90_000)),
    ("Edit", 15, (60, 300)),
    ("Task", 10, (600, 1_800)),  # subagent zwraca tylko raport
]


def filler(rng: random.Random, n: int) -> str:
    words = ["var", "return", "await", "public", "class", "Order", "Async", "using",
             "namespace", "Task", "string", "int", "foreach", "null", "if", "else"]
    out, size = [], 0
    while size < n:
        line = " ".join(rng.choice(words) for _ in range(rng.randint(4, 12)))
        out.append(line)
        size += len(line) + 1
    return "\n".join(out)[:n]


def usage_for(context_chars: int, out_chars: int, first: bool) -> dict:
    ctx = BASE_TOKENS + context_chars // 4
    if first:
        return {"input_tokens": 12, "cache_creation_input_tokens": ctx,
                "cache_read_input_tokens": 0, "output_tokens": out_chars // 4}
    # stabilny prefiks z cache'u, tylko przyrost jako świeże tokeny
    return {"input_tokens": 12, "cache_creation_input_tokens": 1_500,
            "cache_read_input_tokens": ctx - 1_500, "output_tokens": out_chars // 4}


def main() -> None:
    path = sys.argv[1] if len(sys.argv) > 1 else "session.jsonl"
    rng = random.Random(SEED)
    names = [t[0] for t in TOOLS]
    weights = [t[1] for t in TOOLS]
    ranges = {t[0]: t[2] for t in TOOLS}
    records = []
    context_chars = 0
    records.append({"type": "user", "message": {"role": "user", "content": "Napraw bug w OrderService i dodaj test."}})
    context_chars += 40
    for i in range(1, 61):
        name = rng.choices(names, weights)[0]
        tid = f"toolu_{i:03d}"
        say = f"Krok {i}: użyję {name}."
        tool_input = {"file_path": f"src/File{i}.cs"} if name in ("Read", "Edit") else {"command": f"krok {i}"}
        first = not any(r["type"] == "assistant" for r in records)
        u = usage_for(context_chars, len(say) + 60, first)
        records.append({"type": "assistant", "message": {"role": "assistant", "usage": u, "content": [
            {"type": "text", "text": say},
            {"type": "tool_use", "id": tid, "name": name, "input": tool_input}]}})
        context_chars += len(say) + 60
        lo, hi = ranges[name]
        # rozkład z ciężkim ogonem: większość wyników mała, kilka ogromnych
        size = int(lo + (hi - lo) * rng.random() ** 3)
        result = filler(rng, size)
        records.append({"type": "user", "message": {"role": "user", "content": [
            {"type": "tool_result", "tool_use_id": tid, "content": result}]}})
        context_chars += size
    with open(path, "w", encoding="utf-8") as f:
        for r in records:
            f.write(json.dumps(r, ensure_ascii=False) + "\n")
    print(f"Zapisano {len(records)} rekordów, {sum(len(json.dumps(r)) for r in records)} bajtów -> {path}")


if __name__ == "__main__":
    main()
