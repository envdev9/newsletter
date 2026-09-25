#!/usr/bin/env python3
"""UserPromptSubmit: dokleja kontekst do promptu (stdout przy exit 0).

Zasada: to co hook wypisze na stdout przy exit 0 trafia do kontekstu modelu razem
z promptem uzytkownika. Tu: jesli prompt dotyczy migracji EF - przypominamy o
skillu, i zawsze dopisujemy date (modele jej nie znaja).
"""
import datetime
import json
import os
import sys
import time


def main() -> int:
    time.sleep(float(os.environ.get("HOOK_DELAY", "0")))
    try:
        event = json.load(sys.stdin)
    except json.JSONDecodeError:
        return 1
    prompt = event.get("prompt", "").lower()
    lines = [f"[hook] Dzisiejsza data: {datetime.date(2026, 9, 25).isoformat()}"]
    if "migrac" in prompt or "migration" in prompt:
        lines.append(
            "[hook] Zadanie dotyczy migracji: przed zmiana uzyj skilla ef-migration-review "
            "i nie edytuj wygenerowanych plikow *.Designer.cs."
        )
    print("\n".join(lines))
    return 0


if __name__ == "__main__":
    sys.exit(main())
