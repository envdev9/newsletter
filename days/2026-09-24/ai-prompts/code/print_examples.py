#!/usr/bin/env python3
"""Waliduje i wypisuje pary zły/dobry prompt z examples.yaml.

Walidacja: każdy wpis musi mieć pola id, kategoria, zly, dobry, dlaczego, wszystkie
niepuste (po strip()). Jeśli którykolwiek wpis nie spełnia warunku, skrypt kończy się
kodem != 0 i wypisuje listę błędów zamiast ładnego wydruku.

Użycie:
    python3 print_examples.py            # pełny, sformatowany wydruk
    python3 print_examples.py --check     # tylko walidacja, bez wydruku (do CI)
"""
import sys
import textwrap

import yaml

REQUIRED_FIELDS = ("id", "kategoria", "zly", "dobry", "dlaczego")
WRAP_WIDTH = 88


def load_examples(path="examples.yaml"):
    with open(path, encoding="utf-8") as f:
        data = yaml.safe_load(f)
    if not isinstance(data, list) or not data:
        raise ValueError(f"{path}: oczekiwano niepustej listy przykładów")
    return data


def validate(examples):
    errors = []
    seen_ids = set()
    for i, ex in enumerate(examples):
        label = f"przykład #{i} (id={ex.get('id', '?')})"
        for field in REQUIRED_FIELDS:
            val = ex.get(field)
            if val is None or not str(val).strip():
                errors.append(f"{label}: brak/puste pole '{field}'")
        ex_id = ex.get("id")
        if ex_id in seen_ids:
            errors.append(f"{label}: zduplikowane id={ex_id}")
        seen_ids.add(ex_id)
    return errors


def wrap(label, text, indent="    "):
    body = textwrap.fill(
        str(text).strip(),
        width=WRAP_WIDTH,
        initial_indent=indent,
        subsequent_indent=indent,
    )
    return f"{indent}{label}:\n{body}\n"


def print_examples(examples):
    print(f"Znaleziono {len(examples)} przykładów w examples.yaml\n")
    print("=" * WRAP_WIDTH)
    for ex in examples:
        print(f"[{ex['id']}] {ex['kategoria']}")
        print("-" * WRAP_WIDTH)
        print(wrap("❌ ZŁY PROMPT", ex["zly"]))
        print(wrap("✅ DOBRY PROMPT", ex["dobry"]))
        print(wrap("💡 DLACZEGO", ex["dlaczego"]))
        print("=" * WRAP_WIDTH)
    print(f"\nWYNIK: {len(examples)}/{len(examples)} przykładów poprawnych "
          f"(pola id/kategoria/zly/dobry/dlaczego obecne i niepuste).")


def main():
    check_only = "--check" in sys.argv
    try:
        examples = load_examples()
    except (OSError, yaml.YAMLError, ValueError) as exc:
        print(f"BŁĄD wczytywania examples.yaml: {exc}", file=sys.stderr)
        sys.exit(1)

    errors = validate(examples)
    if errors:
        print(f"WALIDACJA NIEUDANA: {len(errors)} błąd(ów):", file=sys.stderr)
        for e in errors:
            print(f"  - {e}", file=sys.stderr)
        sys.exit(1)

    if check_only:
        print(f"WYNIK: {len(examples)}/{len(examples)} przykładów poprawnych.")
        return

    print_examples(examples)


if __name__ == "__main__":
    main()
