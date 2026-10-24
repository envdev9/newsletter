#!/usr/bin/env python3
"""UserPromptSubmit: blokuje prompt zawierajacy cos co wyglada na sekret.

Wejscie (stdin): JSON ze zdarzenia UserPromptSubmit, pole `prompt`.
Wyjscie: exit 2 + stderr = prompt jest odrzucony (nie trafia do modelu),
stderr widzi uzytkownik. Exit 0 = przepusc. Sekretu NIE powtarzamy w komunikacie.
"""
import json
import os
import re
import sys
import time

PATTERNS = [
    (r"AKIA[0-9A-Z]{16}", "klucz dostepowy AWS"),
    (r"-----BEGIN (?:RSA |EC |OPENSSH )?PRIVATE KEY-----", "klucz prywatny PEM"),
    (r"gh[pousr]_[A-Za-z0-9]{36}", "token GitHub"),
    (r"(?i)\b(?:password|haslo|pwd)\s*[=:]\s*\S{4,}", "haslo w postaci jawnej"),
]


def main() -> int:
    time.sleep(float(os.environ.get("HOOK_DELAY", "0")))
    try:
        event = json.load(sys.stdin)
    except json.JSONDecodeError:
        return 1  # niekrytyczny blad hooka - prompt przechodzi
    prompt = event.get("prompt", "")
    for pattern, label in PATTERNS:
        if re.search(pattern, prompt):
            sys.stderr.write(
                f"Prompt odrzucony: wykryto {label}. Usun sekret z promptu "
                "(podaj nazwe zmiennej srodowiskowej zamiast wartosci) i wyslij ponownie.\n"
            )
            return 2
    return 0


if __name__ == "__main__":
    sys.exit(main())
