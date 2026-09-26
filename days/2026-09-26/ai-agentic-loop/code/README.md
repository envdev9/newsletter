# Kod do wydania #3 — własny subagent, pętla z weryfikacją, hooki PreCompact/SessionStart

Pełny artykuł: [`../ARTICLE.md`](../ARTICLE.md).

Wymagania: **python3** (testowane na 3.10.4), bez zależności. Uruchamiaj z katalogu `code/`
(przykłady poniżej używają ścieżek względnych). Komenda `claude` **nie była dostępna** przy
pisaniu — wszystko, co jej dotyczy, jest oznaczone jako niezweryfikowane.

## Fragment prasówki, którego dotyczy ten kod

> Subagent to plik Markdown z frontmatterem (`name`, `description`, `tools`, `model`) i promptem
> systemowym. `description` decyduje o delegowaniu, `tools` o tym, co agent może zrobić (pominięte
> = dziedziczy wszystko), a izolacja kontekstu sprawia, że rodzic dostaje tylko końcową odpowiedź.
> Pętla z weryfikacją opiera się na exit code weryfikatora (testów), nie na słowie agenta, i ma
> twardy limit iteracji. `PreCompact` utrwala stan na dysku przed kompaktowaniem, a `SessionStart`
> ze `source=compact` odtwarza go w nowym kontekście.

## Pliki

| Plik | Rola |
|---|---|
| `claude-agents/dotnet-reviewer.md` | subagent read-only (`Read, Grep, Glob`) do review C# |
| `claude-agents-bad/sloppy.md` | celowo zły agent — test negatywny linta |
| `validate_agent.py` | lint agenta: frontmatter, kebab-case, opis „co i kiedy”, literówki w `tools`, `--read-only` |
| `verify_loop.py` | pętla worker → weryfikacja → feedback, limit iteracji, pracuje na kopii projektu |
| `loop-demo/` | projekt z 2 błędami + **skryptowy** zastępnik agenta (nie model!) |
| `hooks/precompact_snapshot.py` | `PreCompact`: zapis pliku zadan do `claude-state/` |
| `hooks/sessionstart_restore.py` | `SessionStart`: data na starcie, odtworzenie snapshotu po `compact` |
| `hooks/settings.example.json` | jak zarejestrować hooki (składnia z pamięci, niezweryfikowana) |
| `fixtures/`, `sample-tasks/` | payloady stdin i przykładowy `TASKS.md` |
| `demo_hooks.py` | 7 przypadków hooków w katalogu tymczasowym |

## Uruchomienie

```bash
# 1. lint agenta: dobry -> OK, zły -> FAIL (exit 1)
python3 validate_agent.py claude-agents/dotnet-reviewer.md --read-only
python3 validate_agent.py claude-agents-bad/sloppy.md --read-only

# 2. pętla z weryfikacją (worker skryptowy): sukces w 2. iteracji
python3 verify_loop.py --project loop-demo/project --max-iter 3 \
  --worker "python3 loop-demo/scripted_worker.py" --verify "python3 -m unittest -q"
# z limitem 1: porażka, exit 1
python3 verify_loop.py --project loop-demo/project --max-iter 1 \
  --worker "python3 loop-demo/scripted_worker.py" --verify "python3 -m unittest -q"

# 3. hooki PreCompact/SessionStart
python3 demo_hooks.py
# koniec outputu: "WYNIK: 7/7 zgodnych"
```

## Prawdziwy output (skrót)

```
OK: dotnet-reviewer.md

BLAD: name 'Sloppy Helper' musi byc kebab-case (male litery, cyfry, myslniki)
BLAD: agent ma byc read-only, a ma: Bash, Write
FAIL: sloppy.md (5 bledow)

=== iteracja 1/3
  worker: brak feedbacku -> naprawiam add (pierwsze co widze)
  weryfikacja: exit=1   (AssertionError: 8 != 2 w test_sub)
=== iteracja 2/3
  worker: feedback wspomina test_sub -> naprawiam sub
  weryfikacja: exit=0
SUKCES po 2 iteracji(ach)

WYNIK: 7/7 zgodnych
```

## Podpięcie do prawdziwej sesji (niezweryfikowane)

Zapis do `.claude/` bywa odrzucany, dlatego repo trzyma pliki w katalogach bez kropki. U siebie skopiuj:

```bash
mkdir -p .claude/agents .claude/hooks
cp claude-agents/dotnet-reviewer.md .claude/agents/
cp hooks/precompact_snapshot.py hooks/sessionstart_restore.py .claude/hooks/
# wpisy "hooks" z hooks/settings.example.json wklej do .claude/settings.json
# (zmień ścieżki w "command" na .claude/hooks/...)
```

Agenta sprawdzisz komendą `/agents` w sesji. Do `.gitignore` dodaj `claude-state/`.

### Zamiana skryptowego workera na prawdziwego agenta (NIEZWERYFIKOWANE)

Sesja pisząca ten kod nie miała dostępu do `claude` (polecenie odrzucone przez uprawnienia),
więc poniższa forma pochodzi z pamięci — sprawdź `claude --help` u siebie:

```bash
claude -p "Napraw testy w tym katalogu. Uzyj FEEDBACK z pliku, jesli istnieje." \
  --max-turns 10 --allowedTools "Read,Edit,Bash(python3 -m unittest*)"
```

Najprostsza integracja: `--worker` w `verify_loop.py` = skrypt-opakowanie, który wywołuje
`claude -p` z treścią `$FEEDBACK_FILE` w prompcie.

## Czego NIE zweryfikowano

- Czegokolwiek w żywej sesji Claude Code: czy agent zostanie wybrany na podstawie `description`,
  czy `tools` faktycznie go ogranicza, czy hooki dostają dokładnie takie payloady (fixtury z pamięci).
- Komendy `claude -p` i jej flag.
- Że `PreCompact` w Twojej wersji odpala się w opisanych warunkach i że `SessionStart` ma `source=compact`.
- `scripted_worker.py` to stub z z góry zaplanowanym zachowaniem — dowodzi mechaniki pętli, nie zdolności modelu.
