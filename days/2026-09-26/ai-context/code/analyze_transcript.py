#!/usr/bin/env python3
"""Analizator transkryptu sesji (.jsonl): kto pożera kontekst i co by było, gdyby...

Czyta WYŁĄCZNIE wskazany plik i drukuje statystyki agregatowe (nazwy narzędzi,
rozmiary). Nie drukuje treści rozmowy ani ścieżek.

Tokeny = bajty/4 (heurystyka, nie tokenizer Claude'a). Rekordy, których nie
rozumie, pomija. Trzy pytania:
  1. Rozkład per narzędzie (ile wywołań, ile bajtów, jaki udział).
  2. Najwięksi "pożeracze": rozmiar wyniku x liczba tur, które go dźwigały.
  3. What-if: (a) delegacja dużych wyników do subagenta (zostaje krótki raport),
     (b) automatyczny compact po przekroczeniu progu okna.

Użycie:
    python3 analyze_transcript.py session.jsonl [--base 18000] [--window 200000]
        [--top 5] [--delegate-over 3000] [--report-tokens 150]
        [--compact-at 0.8] [--summary-tokens 4000]
"""

import argparse
import json
from collections import defaultdict


def text_of(content) -> str:
    if isinstance(content, str):
        return content
    if isinstance(content, list):
        return "".join(b.get("text", "") for b in content if isinstance(b, dict))
    return ""


def load_events(path: str):
    """Zwraca listę zdarzeń (kind, tool, tokens) w kolejności; kind: 'user'|'assistant'|'result'."""
    events, tool_names, peak_usage = [], {}, 0
    with open(path, encoding="utf-8") as f:
        for raw in f:
            try:
                rec = json.loads(raw)
            except json.JSONDecodeError:
                continue
            msg = rec.get("message")
            if not isinstance(msg, dict):
                continue
            content = msg.get("content")
            if rec.get("type") == "assistant":
                usage = msg.get("usage") or {}
                ctx = sum(usage.get(k, 0) for k in
                          ("input_tokens", "cache_creation_input_tokens", "cache_read_input_tokens"))
                peak_usage = max(peak_usage, ctx)
                size = 0
                for b in content if isinstance(content, list) else []:
                    if b.get("type") == "tool_use":
                        tool_names[b.get("id")] = b.get("name", "?")
                    size += len(json.dumps(b, ensure_ascii=False).encode())
                events.append(("assistant", None, size, None))
            elif rec.get("type") == "user":
                blocks = content if isinstance(content, list) else None
                if blocks and any(b.get("type") == "tool_result" for b in blocks if isinstance(b, dict)):
                    for b in blocks:
                        if b.get("type") == "tool_result":
                            n = len(text_of(b.get("content")).encode())
                            events.append(("result", tool_names.get(b.get("tool_use_id"), "?"), n, None))
                else:
                    events.append(("user", None, len(text_of(content).encode()), None))
    return events, peak_usage


def simulate(events, base, delegate_over=None, report_tokens=150, compact_limit=None, summary_tokens=4000):
    """Zwraca (szczyt kontekstu, suma 'token-tur', liczba compactów)."""
    ctx, peak, total, compactions = base, base, 0, 0
    for kind, _tool, size, _ in events:
        tokens = size / 4
        if kind == "result" and delegate_over is not None and tokens > delegate_over:
            tokens = report_tokens
        if kind == "assistant":
            total += ctx  # ta tura czyta cały dotychczasowy kontekst
        ctx += tokens
        peak = max(peak, ctx)
        if compact_limit is not None and ctx > compact_limit:
            ctx = base + summary_tokens
            compactions += 1
    return peak, total, compactions


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("path")
    ap.add_argument("--base", type=int, default=18000, help="stała część startowa (system+narzędzia+CLAUDE.md), tokeny")
    ap.add_argument("--window", type=int, default=200000)
    ap.add_argument("--top", type=int, default=5)
    ap.add_argument("--delegate-over", type=int, default=3000)
    ap.add_argument("--report-tokens", type=int, default=150)
    ap.add_argument("--compact-at", type=float, default=0.8)
    ap.add_argument("--summary-tokens", type=int, default=4000)
    a = ap.parse_args()

    events, peak_usage = load_events(a.path)
    turns = sum(1 for e in events if e[0] == "assistant")

    per = defaultdict(lambda: [0, 0, 0])  # calls, bytes, max
    for kind, tool, size, _ in events:
        if kind == "result":
            p = per[tool]
            p[0] += 1
            p[1] += size
            p[2] = max(p[2], size)
    total_bytes = sum(v[1] for v in per.values()) or 1
    all_bytes = sum(e[2] for e in events) or 1

    print(f"Zdarzeń: {len(events)}, tur asystenta: {turns}, "
          f"wyniki narzędzi = {100 * total_bytes / all_bytes:.1f}% wszystkich bajtów")
    print()
    print("1) Rozkład per narzędzie")
    print(f"{'narzędzie':<10}{'wywołań':>8}{'bajtów':>10}{'~tokenów':>10}{'udział':>8}{'max ~tok':>10}")
    for tool, (calls, byt, mx) in sorted(per.items(), key=lambda kv: -kv[1][1]):
        print(f"{tool:<10}{calls:>8}{byt:>10}{byt // 4:>10}{100 * byt / total_bytes:>7.1f}%{mx // 4:>10}")

    print()
    print(f"2) Top {a.top} pożeraczy: rozmiar wyniku x liczba tur, które go dźwigały")
    eaters = []
    seen_turns = 0
    for kind, tool, size, _ in events:
        if kind == "assistant":
            seen_turns += 1
        elif kind == "result":
            eaters.append((tool, size // 4, (turns - seen_turns) * (size // 4), turns - seen_turns))
    eaters.sort(key=lambda e: -e[2])
    print(f"{'narzędzie':<10}{'~tokenów':>10}{'tur potem':>11}{'token-tur':>12}")
    for tool, tok, tt, left in eaters[:a.top]:
        print(f"{tool:<10}{tok:>10}{left:>11}{tt:>12}")
    top_share = sum(e[2] for e in eaters[:a.top]) / (sum(e[2] for e in eaters) or 1)
    print(f"Te {a.top} wyników = {100 * top_share:.1f}% całego 'dźwigania' wyników przez kolejne tury.")

    print()
    print(f"3) What-if (okno {a.window} tok., baza {a.base} tok.)")
    print(f"{'wariant':<44}{'szczyt ~tok':>12}{'token-tur':>13}{'compactów':>10}")
    variants = [
        ("bez zmian", {}),
        (f"delegacja wyników > {a.delegate_over} tok. (raport {a.report_tokens})",
         {"delegate_over": a.delegate_over, "report_tokens": a.report_tokens}),
        (f"auto-compact przy {int(a.compact_at * 100)}% okna (summary {a.summary_tokens})",
         {"compact_limit": a.window * a.compact_at, "summary_tokens": a.summary_tokens}),
        ("delegacja + auto-compact",
         {"delegate_over": a.delegate_over, "report_tokens": a.report_tokens,
          "compact_limit": a.window * a.compact_at, "summary_tokens": a.summary_tokens}),
    ]
    for name, kw in variants:
        peak, total, comp = simulate(events, a.base, **kw)
        print(f"{name:<44}{peak:>12.0f}{total:>13.0f}{comp:>10}")
    if peak_usage:
        print(f"\nSzczyt kontekstu wg pól usage w pliku: {peak_usage} tok. (do porównania z wierszem 'bez zmian')")


if __name__ == "__main__":
    main()
