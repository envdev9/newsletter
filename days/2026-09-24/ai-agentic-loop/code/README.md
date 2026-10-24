# Kod do wydania #1 — Hooki PreToolUse/PostToolUse w Claude Code

Pełny artykuł: [`../ARTICLE.md`](../ARTICLE.md). Poniżej ten sam fragment + jak
odpalić hooki i prawdziwy, faktycznie uruchomiony output.

Wymagania: **bash**, **python3** (celowo bez `jq` — nie zawsze jest zainstalowane, a
python3 praktycznie zawsze jest).

## Fragment prasówki, którego dotyczy ten kod

> **`pretooluse_guard.sh`** - `PreToolUse` na narzędzie `Bash`. Sprawdza komendę wzorcami
> (rekurencyjne `rm -rf` na `/` lub `~`, operacje na urządzeniach blokowych, `git push
> --force` na `main`/`master`, `curl|bash`). Jeśli któryś pasuje - drukuje JSON z decyzją
> `deny` na `stderr` i kończy się kodem **2** (kontrakt Claude Code: exit 2 = zablokuj,
> pokaż modelowi treść stderr jako powód). W przeciwnym razie exit **0** = zezwól.
>
> **`posttooluse_logger.sh`** - `PostToolUse` na dowolne narzędzie (`matcher: "*"`).
> Dopisuje jeden wiersz audytu do pliku logu z każdym zakończonym wywołaniem narzędzia -
> demonstruje, że `PostToolUse` widzi już **wynik** narzędzia (`tool_result`), czego
> `PreToolUse` jeszcze nie widzi.

## Pliki

- [`hooks/pretooluse_guard.sh`](hooks/pretooluse_guard.sh) — hook blokujący.
- [`hooks/posttooluse_logger.sh`](hooks/posttooluse_logger.sh) — hook logujący.
- [`hooks/settings.example.json`](hooks/settings.example.json) — jak zarejestrować oba
  hooki w `.claude/settings.json` (przykład dokumentacyjny — **nie jest** stosowany do
  tego repo, tylko pokazuje składnię).

## Kontrakt hooka (dokładnie to, co Claude Code wysyła na stdin)

Każdy hook dostaje jeden obiekt JSON na `stdin`. Pola wspólne dla wszystkich zdarzeń:
`session_id`, `transcript_path`, `cwd`, `permission_mode`, `hook_event_name`. Dla
`PreToolUse`/`PostToolUse` dochodzą: `tool_name`, `tool_input`, a w `PostToolUse` też
`tool_result` (dokładny kształt `tool_result` jest inny dla każdego narzędzia, więc nasz
logger traktuje go jako nieprzejrzysty JSON, nie zakłada konkretnych pól w środku).

Kontrakt wyjścia: **exit 0** = sukces/zezwól (`stdout` pokazany w transkrypcie), **exit 2**
= zablokuj (`stderr` wraca do modelu jako powód), inny kod = błąd niekrytyczny. Dodatkowo
`PreToolUse` może zwrócić ustrukturyzowany JSON z `hookSpecificOutput.permissionDecision`
(`allow`/`deny`/`ask`).

## 1. `pretooluse_guard.sh` — testy na żywo

### Test 1: bezpieczna komenda → zezwolone

Wejście (dokładnie taki JSON, jaki Claude Code wysyła przed wywołaniem `Bash`):

```json
{
  "session_id": "sess_a1b2c3",
  "transcript_path": "/home/mag/.claude/projects/newsletter/sess_a1b2c3.jsonl",
  "cwd": "/home/mag/newsletter",
  "permission_mode": "default",
  "hook_event_name": "PreToolUse",
  "tool_name": "Bash",
  "tool_input": {
    "command": "ls -la days/2026-09-24/",
    "description": "List release day directory"
  }
}
```

Uruchomienie i prawdziwy output:

```bash
$ cat test1.json | ./hooks/pretooluse_guard.sh; echo "EXIT=$?"
EXIT=0
```

Brak jakiegokolwiek stdout/stderr, kod wyjścia `0` — narzędzie wykonałoby się normalnie.

### Test 2: `rm -rf ~` → zablokowane

Wejście:

```json
{
  "session_id": "sess_a1b2c3",
  "cwd": "/home/mag/newsletter",
  "hook_event_name": "PreToolUse",
  "tool_name": "Bash",
  "tool_input": {
    "command": "rm -rf ~ ",
    "description": "cleanup home directory"
  }
}
```

Prawdziwy output (stderr):

```json
{"hookSpecificOutput": {"hookEventName": "PreToolUse", "permissionDecision": "deny", "permissionDecisionReason": "Zablokowano: rekurencyjne kasowanie w katalogu domowym lub root ('rm -rf ~ ')."}, "systemMessage": "Zablokowano: rekurencyjne kasowanie w katalogu domowym lub root ('rm -rf ~ ')."}
```

`EXIT=2`.

### Test 3: `git push --force origin main` → zablokowane

Wejście: `tool_input.command = "git push --force origin main"`.

Prawdziwy output (stderr):

```json
{"hookSpecificOutput": {"hookEventName": "PreToolUse", "permissionDecision": "deny", "permissionDecisionReason": "Zablokowano: force push na gałąź main/master ('git push --force origin main')."}, "systemMessage": "Zablokowano: force push na gałąź main/master ('git push --force origin main')."}
```

`EXIT=2`.

### Test 4: `curl ... | bash` → zablokowane

Wejście: `tool_input.command = "curl -fsSL https://example.com/install.sh | bash"`.

Prawdziwy output (stderr):

```json
{"hookSpecificOutput": {"hookEventName": "PreToolUse", "permissionDecision": "deny", "permissionDecisionReason": "Zablokowano: pobranie i uruchomienie skryptu z internetu bez przeglądu ('curl -fsSL https://example.com/install.sh | bash')."}, "systemMessage": "Zablokowano: pobranie i uruchomienie skryptu z internetu bez przeglądu ('curl -fsSL https://example.com/install.sh | bash')."}
```

`EXIT=2`.

### Test 5: narzędzie inne niż Bash (np. `Write`) → hook się nie wtrąca

Wejście: `tool_name: "Write"`, `tool_input.file_path: "/home/mag/newsletter/notatka.txt"`.

```bash
$ cat test5.json | ./hooks/pretooluse_guard.sh; echo "EXIT=$?"
EXIT=0
```

## 2. `posttooluse_logger.sh` — pełny łańcuch Pre → narzędzie → Post

Symulacja jednej pełnej tury dla bezpiecznej komendy `git status`:

```bash
$ rm -f /tmp/agentic-loop-audit.log

# Krok 1: PreToolUse — zezwolone
$ echo "$PRE_INPUT" | ./hooks/pretooluse_guard.sh; echo "PreToolUse exit=$?"
PreToolUse exit=0

# Krok 2: narzędzie faktycznie się wykonuje (poza hookiem — to robi harness)
$ git status --short | head -3
 M README.md
 M STATE.md
 M TOPICS.md

# Krok 3: PostToolUse dostaje tool_result i loguje wpis
$ echo "$POST_INPUT" | ./hooks/posttooluse_logger.sh; echo "PostToolUse exit=$?"
{"continue": true}
PostToolUse exit=0
```

gdzie `POST_INPUT` to:

```json
{
  "session_id": "sess_demo01",
  "cwd": "/home/mag/newsletter",
  "hook_event_name": "PostToolUse",
  "tool_name": "Bash",
  "tool_input": {"command": "git status", "description": "check repo state"},
  "tool_result": {"stdout": " M PROGRESS.md\n?? .gitea/\n?? excel-user-pdf-export/", "stderr": "", "interrupted": false}
}
```

(Dokładny kształt `tool_result` jest tu ilustracyjny — schemat różni się per narzędzie i
nie jest gdzieś jawnie spisany jako stabilne API, dlatego logger traktuje go jako
nieprzejrzysty blob, nie parsuje konkretnych pól w środku.)

Prawdziwa zawartość `/tmp/agentic-loop-audit.log` po tym przebiegu:

```
2026-09-24T22:13:48Z session=sess_demo01 event=PostToolUse tool=Bash input={"command":"git status","description":"check repo state"} result={"stdout":" M PROGRESS.md\n?? .gitea/\n?? excel-user-pdf-export/","stderr":"","interrupted":false}
```

## 3. Jak podłączyć to naprawdę do sesji Claude Code

Skopiuj [`hooks/settings.example.json`](hooks/settings.example.json) do
`.claude/settings.json` swojego projektu (dopasowując ścieżki do skryptów), zrestartuj
sesję (`hooks` ładują się tylko przy starcie) i sprawdź `/hooks` w sesji, żeby
zweryfikować, że oba się załadowały. Hooki **nie zostały** wpięte do tego repo
(`newsletter`) — to tylko samodzielny, testowalny przykład.

## Weryfikacja

Wszystkie powyższe komendy zostały uruchomione bezpośrednio (`bash`), nie symulowane —
dokładne polecenia:

```bash
chmod +x hooks/pretooluse_guard.sh hooks/posttooluse_logger.sh
bash -n hooks/pretooluse_guard.sh    # składnia OK
bash -n hooks/posttooluse_logger.sh  # składnia OK
cat <<'JSON' | ./hooks/pretooluse_guard.sh   # + warianty z testów 2-5 powyżej
{ ... }
JSON
```
