#!/usr/bin/env python3
"""Szacuje, ile "miejsca w kontekście" zajmie tekst podany na stdin.

To NIE jest prawdziwy tokenizer Claude'a (ten jest zamknięty i oparty o BPE,
więc dokładna liczba tokenów zależy od modelu). To zgrubna, ale w praktyce
użyteczna heurystyka: ~4 znaki angielskiego/kodu ≈ 1 token - ten sam rząd
wielkości, jakiego używa się przy szybkim "ile to zje kontekstu" w głowie,
zanim faktycznie coś wklei się do rozmowy z modelem.

Użycie:
    cat plik.log | python3 token_budget.py
    grep ERROR plik.log | python3 token_budget.py
    head -n 50 plik.log | python3 token_budget.py
"""

import sys

CHARS_PER_TOKEN = 4  # zgrubna heuristyka, nie dokładny tokenizer


def main() -> None:
    text = sys.stdin.read()
    chars = len(text)
    lines = text.count("\n") + (1 if text and not text.endswith("\n") else 0)
    est_tokens = chars / CHARS_PER_TOKEN

    print(f"linii:              {lines:>8}")
    print(f"znaków:             {chars:>8}")
    print(f"~tokenów (heurystyka, {CHARS_PER_TOKEN} znaki/token): {est_tokens:>8.0f}")


if __name__ == "__main__":
    main()
