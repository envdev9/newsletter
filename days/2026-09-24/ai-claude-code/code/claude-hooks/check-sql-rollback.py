#!/usr/bin/env python3
"""PreToolUse hook Claude Code: blokuje zapis pliku migracji SQL bez sekcji rollbacku.

Wpinany w .claude/settings.json pod zdarzenie PreToolUse (matcher "Write|Edit").
Claude Code przekazuje na stdin JSON opisujący wywołanie narzędzia; hook decyduje
o dopuszczeniu operacji kodem wyjścia:
  - exit 0  -> operacja dozwolona
  - exit 2  -> operacja ZABLOKOWANA, stderr trafia z powrotem do Claude jako
               informacja zwrotna (model widzi powód i może się sam poprawić)
  - inny kod -> błąd hooka, niekrytyczny (widoczny dla użytkownika, nie blokuje)
"""
import json
import re
import sys

ROLLBACK_PATTERN = re.compile(r"--\s*ROLLBACK", re.IGNORECASE)


def main() -> int:
    try:
        payload = json.load(sys.stdin)
    except json.JSONDecodeError as exc:
        print(f"check-sql-rollback: nie mogę sparsować JSON ze stdin: {exc}", file=sys.stderr)
        return 1

    tool_name = payload.get("tool_name", "")
    if tool_name not in ("Write", "Edit"):
        return 0

    tool_input = payload.get("tool_input") or {}
    file_path = (tool_input.get("file_path") or "").replace("\\", "/")

    if "/migrations/" not in file_path or not file_path.endswith(".sql"):
        return 0

    # Write ma "content", Edit ma "new_string" - bierzemy co jest dostępne.
    content = tool_input.get("content")
    if content is None:
        content = tool_input.get("new_string", "")

    if ROLLBACK_PATTERN.search(content):
        return 0

    print(
        "BLOKADA: plik migracji '"
        + file_path
        + "' nie zawiera sekcji '-- ROLLBACK'.\n"
        "Każda migracja SQL w tym repo musi mieć blok rollbacku, np.:\n\n"
        "-- ROLLBACK\n"
        "-- DROP INDEX ix_orders_customer;\n\n"
        "Dopisz sekcję rollbacku do tej migracji i spróbuj ponownie.",
        file=sys.stderr,
    )
    return 2


if __name__ == "__main__":
    sys.exit(main())
