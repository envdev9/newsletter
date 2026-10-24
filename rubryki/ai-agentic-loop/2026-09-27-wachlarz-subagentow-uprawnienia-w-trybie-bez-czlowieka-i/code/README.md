# Kod do wydania #4 — wachlarz subagentów, uprawnienia headless, bramka CI

Pełny artykuł: [`../ARTICLE.md`](../ARTICLE.md).

Wymagania: **python3** (testowane na 3.10), bez zależności. Komenda `claude` **nie została
uruchomiona** (próba odrzucona przez uprawnienia) — reviewery, `fake_claude.py` i model polityki to
**atrapy skryptowe**, nie modele ani prawdziwe CLI.

## Fragment prasówki, którego dotyczy ten kod

> Wachlarz subagentów (fan-out) skraca czas ścienny do najwolniejszego workera, ale scalanie (fan-in)
> to kod, który trzeba napisać poprawnie: dedupe po (plik, linia, kategoria), severity = najwyższa,
> sort, limit, a awaria jednego workera to `PARTIAL` i niezerowy exit code — brak wyniku nie znaczy
> „czysto”. W CI nikt nie klika zgody, więc uprawnienia to jawny `allow` + `deny` + domyślna odmowa
> (w headless „zapytaj” = „odmów”); uwaga na polecenia złożone omijające wzorce prefiksowe. Wokół
> `claude -p` stawiamy bramkę: timeout, walidacja JSON, limit tur i niezależny weryfikator, który ma
> ostatnie słowo.

## Pliki

| Plik | Rola |
|---|---|
| `reviewer.py` | atrapa subagenta: reguły regex per rola, wyjście JSON Lines; rola `crash` pada celowo |
| `fanout.py` | równoległe uruchomienie ról + scalanie (dedupe, sort, `--top`, `PARTIAL`) |
| `sample-src/*.cs` | kod z celowymi antywzorcami (nie jest kompilowany) |
| `permission_policy.py`, `policy-headless.json` | model decyzji allow/deny/ask (założenia z pamięci) |
| `fake_claude.py`, `ci_gate.py`, `gate-project/` | atrapa `claude -p` i bramka CI z niezależnym weryfikatorem |
| `claude-agents/security-reviewer.md` | przykład prawdziwego pliku subagenta (jak w #3), nieprzetestowany w sesji |
| `ci/agent-gate.example.yml` | szkic GitHub Actions — **niezweryfikowany** |
| `run_tests.py` | 19 sprawdzeń całości |

## Uruchomienie (z katalogu `code/`)

```bash
# wszystko naraz; ostatnia linia: "WYNIK: 19/19"
python3 run_tests.py

# wachlarz: rownolegle vs sekwencyjnie
python3 fanout.py sample-src/OrderService.cs sample-src/Cache.cs
python3 fanout.py --sequential sample-src/OrderService.cs sample-src/Cache.cs
# awaria jednego workera -> PARTIAL, exit 1
python3 fanout.py --roles style,crash --delay 0 sample-src/OrderService.cs

# polityka uprawnien
python3 permission_policy.py policy-headless.json

# bramka CI: agent "ok", ale weryfikator czerwony -> exit 14
python3 ci_gate.py --project gate-project --agent "python3 ../fake_claude.py ok" \
  --verify "python3 -m unittest -q test_red"
echo $?
```

`fanout.py` kończy się exit 1, gdy są znaleziska `high` (to zamierzone — tak czerwieni build).

## Podpięcie prawdziwego agenta (NIEZWERYFIKOWANE)

Podmień `--agent` w `ci_gate.py` na `claude -p "..." --output-format json --max-turns 10
--allowedTools "Read,Edit,Bash(dotnet test*)"` (flagi z pamięci; sprawdź `claude --help`).
Pola JSON czytane przez bramkę (`is_error`, `num_turns`) mogą się różnić w Twojej wersji.
Agenta z `claude-agents/` skopiuj do `.claude/agents/`.

## Czego NIE zweryfikowano

- Czegokolwiek z prawdziwym `claude` (CLI odrzucone): `-p`, flagi, format JSON, `permissionMode`.
- Równoległego odpalania subagentów przez rodzica i przestrzegania kontraktu formatu przez model.
- Semantyki dopasowania `Bash(...)` (w tym poleceń złożonych) — `permission_policy.py` to mój model.
- Workflow GitHub Actions.
