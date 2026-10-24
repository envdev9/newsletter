#!/usr/bin/env python3
"""Hook SessionStart: dokleja kontekst na starcie sesji; po kompaktowaniu odtwarza snapshot.

stdin (z pamieci kontraktu - niezweryfikowane w zywej sesji): JSON z polami session_id, cwd,
hook_event_name, source ("startup" | "resume" | "clear" | "compact").
stdout przy exit 0 trafia do kontekstu modelu (jak w UserPromptSubmit) - dlatego limit dlugosci.
Konfiguracja: SNAPSHOT_DIR (domyslnie <cwd>/claude-state), MAX_CHARS (domyslnie 1500).
"""
import json
import os
import re
import sys
from datetime import date
from pathlib import Path


def main() -> int:
    try:
        data = json.load(sys.stdin)
    except json.JSONDecodeError:
        return 0
    source = data.get("source", "startup")
    cwd = Path(data.get("cwd") or ".")
    sid = re.sub(r"[^A-Za-z0-9_-]", "", str(data.get("session_id", "unknown")))[:64] or "unknown"
    if source == "compact":
        snap = Path(os.environ.get("SNAPSHOT_DIR", cwd / "claude-state")) / f"precompact-{sid}.md"
        if not snap.is_file():
            print("[hook] Sesja po kompaktowaniu, ale brak snapshotu - odtworz stan z TASKS.md.")
            return 0
        limit = int(os.environ.get("MAX_CHARS", "1500"))
        text = snap.read_text(encoding="utf-8")
        cut = len(text) > limit
        print("[hook] Kontekst zostal skompaktowany. Stan zadan sprzed kompaktowania:")
        print(text[:limit] + ("\n[...obciete...]" if cut else ""))
    elif source in ("startup", "resume"):
        print(f"[hook] Dzisiejsza data: {date.today().isoformat()}. Zrodlo sesji: {source}.")
    # clear: celowo cisza - uzytkownik chcial czysty kontekst
    return 0


if __name__ == "__main__":
    sys.exit(main())
