# Kod do wydania #2 — UserPromptSubmit / Stop / SubagentStop, kompozycja hooków, własny skill

Pełny artykuł: [`../ARTICLE.md`](../ARTICLE.md).

Wymagania: **python3** (testowane na 3.10.4), bez zależności. Uruchamiaj z katalogu `code/`.

## Fragment prasówki, którego dotyczy ten kod

> `UserPromptSubmit` widzi prompt surowy: exit 2 odrzuca go (stderr widzi użytkownik), a
> stdout przy exit 0 jest doklejany do kontekstu modelu. `Stop`/`SubagentStop` mogą zawrócić
> agenta (`{"decision":"block","reason":...}` albo exit 2) — pole `stop_hook_active` chroni
> przed pętlą nieskończoną. Wiele hooków na jednym evencie startuje równolegle, bez wspólnego
> stanu i bez gwarancji kolejności; wystarczy jeden blokujący. Skill = `SKILL.md` z
> `description` jako mechanizmem aktywacji + skrypt robiący część deterministyczną.

## Pliki

| Plik | Rola |
|---|---|
| `hooks/ups_secret_guard.py` | `UserPromptSubmit`: blokuje prompt z sekretem (exit 2) |
| `hooks/ups_context.py` | `UserPromptSubmit`: dokleja kontekst na stdout |
| `hooks/stop_gate.py` | `Stop`/`SubagentStop`: bramka "testy zielone", z `stop_hook_active` |
| `hooks/settings.example.json` | jak zarejestrować (przykład składni, nie stosowany do repo) |
| `fixtures/*.json` | payloady stdin (kształt z pamięci kontraktu — patrz uwagi) |
| `sample_ok/`, `sample_broken/` | zielone / celowo czerwone testy dla bramki |
| `demo_hooks.py` | uruchamia hooki z fixtur, pokazuje exit/stdout/stderr, sprawdza oczekiwania |
| `run_hooks.py` | **symulator** kompozycji (równolegle, łączenie decyzji) — nie prawdziwy harness |
| `skills/changelog-entry/` | skill od zera: `SKILL.md`, `group_commits.py`, `test-fixtures/commits.txt` |
| `validate_skill.py` | lint skilla (frontmatter, opis, istnienie skryptów) |

## Uruchomienie

```bash
# 1. hooki: 7 przypadków z JSON-em na stdin
python3 demo_hooks.py
# koniec outputu: "WYNIK: 7/7 zgodnych"

# 2. kompozycja: dwa hooki UserPromptSubmit z sztucznym opóźnieniem 1 s
python3 run_hooks.py UserPromptSubmit fixtures/prompt-clean.json \
  "HOOK_DELAY=1 python3 hooks/ups_secret_guard.py" \
  "HOOK_DELAY=1 python3 hooks/ups_context.py"
# CZAS scienny: 1.05s (suma czasow hookow: 2.10s)  -> WYNIK POLACZONY: PRZEPUSZCZONE

# 3. ten sam zestaw z promptem z hasłem -> BLOK (exit 2 skryptu)
python3 run_hooks.py UserPromptSubmit fixtures/prompt-secret.json \
  "HOOK_DELAY=1 python3 hooks/ups_secret_guard.py" \
  "HOOK_DELAY=1 python3 hooks/ups_context.py"

# 4. dwa Stop-hooki, jeden na czerwonych testach -> BLOK
python3 run_hooks.py Stop fixtures/stop.json \
  "python3 hooks/stop_gate.py sample_broken" "python3 hooks/stop_gate.py sample_ok"

# 5. skill: lint + skrypt
python3 validate_skill.py skills/changelog-entry
python3 skills/changelog-entry/group_commits.py --version 1.4.0 --date 2026-09-25 \
  --input skills/changelog-entry/test-fixtures/commits.txt
# na prawdziwej historii: git log <tag>..HEAD --pretty=format:%s | python3 skills/changelog-entry/group_commits.py --version X --date Y
```

## Prawdziwy output (skrót; pełny w artykule)

`demo_hooks.py`:

```
### UserPromptSubmit: haslo w prompcie -> guard blokuje
    exit  : 2 (oczekiwano 2) OK
    stderr: Prompt odrzucony: wykryto haslo w postaci jawnej. Usun sekret z promptu (...)
### Stop: testy czerwone -> decision=block
    stdout: {"decision": "block", "reason": "[Stop] Testy sa czerwone - nie konczysz. ... AssertionError: 4 != 5 ..."}
### Stop: testy czerwone, ale stop_hook_active=true -> przepuszcza
    stdout: stop_gate: stop_hook_active=true - przepuszczam (bezpiecznik przed petla)
WYNIK: 7/7 zgodnych
```

`validate_skill.py`: `OK: changelog-entry (opis: 216 znakow)`.

## Podpięcie do prawdziwej sesji

Skopiuj skrypty do `.claude/hooks/`, wpisy z `hooks/settings.example.json` do
`.claude/settings.json` (dostosuj `tests` w `stop_gate.py` na np. wywołanie `dotnet test`),
skill do `.claude/skills/changelog-entry/`. Sprawdź `/hooks` po restarcie sesji.

## Czego NIE zweryfikowano

- Działania w żywej sesji Claude Code (reakcja modelu na block/exit 2, aktywacja skilla).
- Dokładnego kształtu payloadów (zwłaszcza `SubagentStop`) i reguł łączenia sprzecznych
  decyzji wielu hooków: fixtury i tabela reguł pochodzą z pamięci kontraktu, bo w tej sesji
  nie było dostępu do dokumentacji online. `run_hooks.py` to symulacja, nie harness.
- Sam kod: hooki i skrypt skilla uruchomione realnie (Python 3.10.4).
