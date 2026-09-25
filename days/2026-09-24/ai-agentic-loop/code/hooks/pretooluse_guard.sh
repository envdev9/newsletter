#!/usr/bin/env bash
# PreToolUse hook: blokuje szczególnie niebezpieczne komendy Bash, zanim
# Claude Code je wykona.
#
# Uruchamiany przez harness Claude Code TUŻ PRZED wywołaniem narzędzia Bash.
# Dostaje na stdin JSON opisany w code/README.md. Jeśli komenda pasuje do
# jednego z wzorców - drukuje JSON z decyzją "deny" na stderr i kończy się
# kodem 2 (to jest kontrakt: exit 2 = "zablokuj, a treść stderr pokaż
# Claude'owi jako powód"). W przeciwnym razie kończy się kodem 0 (= zezwól,
# narzędzie wykona się normalnie).
#
# Parsowanie JSON celowo idzie przez python3, nie jq - jq nie jest domyślnie
# dostępne na każdej maszynie, python3 praktycznie zawsze jest.
set -euo pipefail

input="$(cat)"

tool_name="$(python3 -c '
import json, sys
data = json.load(sys.stdin)
print(data.get("tool_name", ""))
' <<<"$input")"

# Hook jest zarejestrowany z matcherem "Bash", ale sprawdzamy jeszcze raz -
# tani, deterministyczny hook nie powinien ślepo ufać matcherowi.
if [[ "$tool_name" != "Bash" ]]; then
  exit 0
fi

command="$(python3 -c '
import json, sys
data = json.load(sys.stdin)
print(data.get("tool_input", {}).get("command", ""))
' <<<"$input")"

deny() {
  local reason="$1"
  REASON="$reason" python3 -c '
import json, os
reason = os.environ["REASON"]
print(json.dumps({
    "hookSpecificOutput": {
        "hookEventName": "PreToolUse",
        "permissionDecision": "deny",
        "permissionDecisionReason": reason,
    },
    "systemMessage": reason,
}, ensure_ascii=False))
' >&2
  exit 2
}

# 1) Rekurencyjne, wymuszone kasowanie w katalogu domowym albo root.
if [[ "$command" =~ rm[[:space:]]+-[a-zA-Z]*r[a-zA-Z]*f[a-zA-Z]*[[:space:]]+(/|~)([[:space:]]|$) ]] \
  || [[ "$command" =~ rm[[:space:]]+-[a-zA-Z]*f[a-zA-Z]*r[a-zA-Z]*[[:space:]]+(/|~)([[:space:]]|$) ]]; then
  deny "Zablokowano: rekurencyjne kasowanie w katalogu domowym lub root ('$command')."
fi

# 2) Operacje bezpośrednio na urządzeniach blokowych / formatowanie.
if [[ "$command" =~ mkfs ]] \
  || [[ "$command" =~ dd[[:space:]].*of=/dev/ ]] \
  || [[ "$command" =~ \>[[:space:]]*/dev/sd ]]; then
  deny "Zablokowano: bezpośrednia operacja na urządzeniu blokowym ('$command')."
fi

# 3) Force push na main/master.
if [[ "$command" =~ git[[:space:]]+push ]] \
  && [[ "$command" =~ (--force|-f)([[:space:]]|$) ]] \
  && [[ "$command" =~ (main|master) ]]; then
  deny "Zablokowano: force push na gałąź main/master ('$command')."
fi

# 4) Pobranie skryptu z internetu i natychmiastowe uruchomienie go w powłoce.
if [[ "$command" =~ (curl|wget)[[:space:]].*\|[[:space:]]*(bash|sh)([[:space:]]|$) ]]; then
  deny "Zablokowano: pobranie i uruchomienie skryptu z internetu bez przeglądu ('$command')."
fi

# Nic nie pasowało - zezwól.
exit 0
