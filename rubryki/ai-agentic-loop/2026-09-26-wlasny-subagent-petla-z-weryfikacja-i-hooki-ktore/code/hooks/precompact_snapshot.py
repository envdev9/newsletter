#!/usr/bin/env python3
"""Hook PreCompact: przed kompaktowaniem zapisuje na dysk to, co MUSI przezyc (plik zadan).

Kompaktowanie zastepuje historie streszczeniem - detale (lista TODO, decyzje) moga zginac.
Ten hook nie wpuszcza niczego do kontekstu; utrwala stan na dysku, a odczytuje go hook
SessionStart (source=compact), patrz sessionstart_restore.py.

stdin (z pamieci kontraktu - niezweryfikowane w zywej sesji): JSON z polami session_id,
cwd, hook_event_name, trigger ("manual" | "auto").
Konfiguracja: TASKS_FILE (domyslnie TASKS.md w cwd), SNAPSHOT_DIR (domyslnie <cwd>/claude-state).
Zawsze exit 0 - nieudany snapshot nie moze blokowac kompaktowania.
"""
import json
import os
import re
import sys
from datetime import datetime, timezone
from pathlib import Path


def main() -> int:
    try:
        data = json.load(sys.stdin)
    except json.JSONDecodeError:
        print("precompact_snapshot: niepoprawny JSON na stdin", file=sys.stderr)
        return 0
    cwd = Path(data.get("cwd") or ".")
    # session_id trafia do nazwy pliku -> zostaw tylko bezpieczne znaki (brak ../)
    sid = re.sub(r"[^A-Za-z0-9_-]", "", str(data.get("session_id", "unknown")))[:64] or "unknown"
    tasks = Path(os.environ.get("TASKS_FILE", cwd / "TASKS.md"))
    out_dir = Path(os.environ.get("SNAPSHOT_DIR", cwd / "claude-state"))
    body = tasks.read_text(encoding="utf-8") if tasks.is_file() else "(brak pliku zadan)"
    out_dir.mkdir(parents=True, exist_ok=True)
    stamp = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    (out_dir / f"precompact-{sid}.md").write_text(
        f"snapshot: {stamp}, trigger: {data.get('trigger', '?')}\n\n{body}\n", encoding="utf-8")
    print(f"precompact_snapshot: zapisano precompact-{sid}.md ({len(body)} znakow)", file=sys.stderr)
    return 0


if __name__ == "__main__":
    sys.exit(main())
