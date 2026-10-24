#!/usr/bin/env bash
# PostToolUse hook: dopisuje jeden wiersz audytu do pliku logu za KAŻDYM
# razem, gdy jakiekolwiek narzędzie skończy działanie.
#
# Uruchamiany przez harness Claude Code TUŻ PO wykonaniu narzędzia (a więc
# już PO ewentualnym PreToolUse i po samym wykonaniu narzędzia). Dostaje na
# stdin JSON zawierający m.in. tool_result - wynik, jaki narzędzie faktycznie
# zwróciło. Nie zakładamy konkretnych pól wewnątrz tool_result (różnią się
# per narzędzie) - logujemy go jako nieprzejrzysty, skompresowany do jednej
# linii obiekt JSON.
set -euo pipefail

LOG_FILE="${AGENTIC_LOOP_LOG:-/tmp/agentic-loop-audit.log}"

input="$(cat)"

read -r session_id hook_event tool_name < <(python3 -c '
import json, sys
data = json.load(sys.stdin)
print(
    data.get("session_id", "unknown"),
    data.get("hook_event_name", "-"),
    data.get("tool_name", "-"),
)
' <<<"$input")

tool_input_compact="$(python3 -c '
import json, sys
data = json.load(sys.stdin)
print(json.dumps(data.get("tool_input", {}), separators=(",", ":")))
' <<<"$input")"

tool_result_compact="$(python3 -c '
import json, sys
data = json.load(sys.stdin)
print(json.dumps(data.get("tool_result"), separators=(",", ":")))
' <<<"$input")"

timestamp="$(date -u +"%Y-%m-%dT%H:%M:%SZ")"

printf '%s session=%s event=%s tool=%s input=%s result=%s\n' \
  "$timestamp" "$session_id" "$hook_event" "$tool_name" \
  "$tool_input_compact" "$tool_result_compact" >> "$LOG_FILE"

# PostToolUse nie blokuje niczego tutaj - zawsze "continue: true".
echo '{"continue": true}'
exit 0
