# Kod do wydania #2 — hook na konwencje commitów + skill do review migracji EF Core

Pełny artykuł: [`../ARTICLE.md`](../ARTICLE.md). Poniżej te same pliki + jak je
zweryfikować/użyć.

## Fragment prasówki, którego dotyczy ten kod

> Dwa kolejne pliki do `.claude/`: **hook `PreToolUse` na `Bash`**, który czyta komendę
> `git commit ...` i odrzuca wiadomość łamiącą Conventional Commits (kod wyjścia 2 +
> uzasadnienie na stderr, które wraca do Claude), oraz **skill do review migracji EF
> Core**, który najpierw odpala deterministyczny skaner (DropColumn, NOT NULL bez
> sensownego defaultu, pusty `Down()`, indeks na dużej tabeli), a dopiero potem prosi
> model o ocenę kontekstową.

## Struktura

```
code/
├── claude-hooks/
│   ├── check-commit-message.py      # .claude/hooks/check-commit-message.py w docelowym repo
│   ├── settings.snippet.json        # wpięcie w .claude/settings.json (PreToolUse, matcher Bash)
│   └── test-fixtures/               # payloady stdin: block-commit.json, allow-commit.json
├── claude-skills/
│   └── ef-migration-review/
│       ├── SKILL.md                 # .claude/skills/ef-migration-review/SKILL.md
│       ├── scan_migration.py        # skaner wywoływany przez skill (krok 1)
│       └── test-fixtures/           # dwie przykładowe migracje .cs (NIE kompilowane)
├── test_commit_hook.py              # 21 przypadków: realne komendy -> hook -> exit code
└── validate.py                      # walidacja statyczna (frontmatter, JSON, składnia, skaner)
```

Wymagania: Python 3.8+, do `validate.py` dodatkowo `PyYAML` (`pip install pyyaml`).
Hook i skaner używają wyłącznie biblioteki standardowej.

## Jak użyć w prawdziwym repo

```bash
mkdir -p /ścieżka/do/repo/.claude/hooks /ścieżka/do/repo/.claude/skills
cp claude-hooks/check-commit-message.py /ścieżka/do/repo/.claude/hooks/
cp -r claude-skills/ef-migration-review /ścieżka/do/repo/.claude/skills/
```

Potem dopisz zawartość `claude-hooks/settings.snippet.json` do `.claude/settings.json`
(sekcja `hooks.PreToolUse`; jeśli masz już inne hooki, dopisz element do istniejącej
listy). Komenda hooka to `python3 "$CLAUDE_PROJECT_DIR/.claude/hooks/check-commit-message.py"`,
więc bit wykonywalności nie jest potrzebny. Restart Claude Code w repo.
Skill w docelowym repo zostaw z `test-fixtures/` albo usuń ten katalog - to tylko dane testowe.

## Weryfikacja — co uruchomiono naprawdę

Środowisko: `Python 3.10.4`. Wszystkie polecenia z katalogu `code/`.

### Hook — jeden payload ze stdin (jak od Claude Code)

```bash
python3 claude-hooks/check-commit-message.py < claude-hooks/test-fixtures/block-commit.json
```

Exit code **2**, stderr:

```
BLOKADA: wiadomosc commita lamie konwencje (Conventional Commits):
  - subject nie pasuje do formatu 'typ(scope)!: opis' (typy: feat, fix, docs, style, refactor, perf, test, build, ci, chore, revert)
  - subject nie powinien konczyc sie kropka
Subject: 'Dodalem filtrowanie zamowien.'
Przyklad poprawnego: feat(orders): dodaj filtrowanie po statusie
Popraw wiadomosc i ponow `git commit`.
```

```bash
python3 claude-hooks/check-commit-message.py < claude-hooks/test-fixtures/allow-commit.json
```

Exit code **0**, brak outputu (commit `feat(orders): dodaj filtrowanie po statusie` przechodzi).

### Hook — 21 przypadków

```bash
python3 test_commit_hook.py
```

```
OK   exit=0 (oczekiwano 0)  poprawny commit
OK   exit=0 (oczekiwano 0)  poprawny, breaking (!)
OK   exit=2 (oczekiwano 2)  zly typ / wielka litera
OK   exit=2 (oczekiwano 2)  brak spacji po dwukropku
OK   exit=2 (oczekiwano 2)  kropka na koncu
OK   exit=2 (oczekiwano 2)  subject za dlugi
OK   exit=2 (oczekiwano 2)  flagi sklejone -am
OK   exit=2 (oczekiwano 2)  --message=...
OK   exit=2 (oczekiwano 2)  git -C repo commit
OK   exit=2 (oczekiwano 2)  w lancuchu && (add + commit)
OK   exit=0 (oczekiwano 0)  heredoc poprawny
OK   exit=2 (oczekiwano 2)  heredoc zly
OK   exit=2 (oczekiwano 2)  brak pustej linii przed body
OK   exit=0 (oczekiwano 0)  wiele -m (paragrafy) poprawne
OK   exit=0 (oczekiwano 0)  merge commit przepuszczony
OK   exit=0 (oczekiwano 0)  --amend --no-edit przepuszczony
OK   exit=0 (oczekiwano 0)  -F plik przepuszczony
OK   exit=0 (oczekiwano 0)  zmienna powloki przepuszczona
OK   exit=0 (oczekiwano 0)  inna komenda git
OK   exit=0 (oczekiwano 0)  komenda z 'commit' w tekscie
OK   exit=0 (oczekiwano 0)  inne narzedzie niz Bash

WYNIK: 21/21 przypadkow zgodnych
```

### Skaner migracji

```bash
python3 claude-skills/ef-migration-review/scan_migration.py claude-skills/ef-migration-review/test-fixtures/20260925101500_RiskyChanges.cs
```

Exit code **1**:

```
claude-skills/ef-migration-review/test-fixtures/20260925101500_RiskyChanges.cs:15 | HIGH   | DropColumn - utrata danych; rozważ najpierw wdrozenie kodu, ktory kolumny nie uzywa (expand/contract)
claude-skills/ef-migration-review/test-fixtures/20260925101500_RiskyChanges.cs:19 | MEDIUM | AddColumn NOT NULL z defaultValue - istniejace wiersze dostana wartosc domyslna (scaffolder daje 0/""/false); czy to poprawne biznesowo?
claude-skills/ef-migration-review/test-fixtures/20260925101500_RiskyChanges.cs:26 | MEDIUM | AlterColumn - sprawdz zawezenie typu/dlugosci/nullability; na duzych tabelach moze blokowac
claude-skills/ef-migration-review/test-fixtures/20260925101500_RiskyChanges.cs:36 | MEDIUM | CreateIndex - na duzej tabeli SQL Server blokuje zapisy; rozwaz .Annotation("SqlServer:Online", true) (edycje z online index)
claude-skills/ef-migration-review/test-fixtures/20260925101500_RiskyChanges.cs:44 | HIGH   | Down() jest pusta - migracji nie da sie wycofac

Znalezisk: 5
```

Dla `20260925103000_SafeAddColumn.cs` (nullable kolumna, sensowny `Down()`): exit **0**,
output `Znalezisk: 0`.

### Walidacja statyczna

```bash
python3 validate.py
```

```
[skill] ef-migration-review/SKILL.md
    OK  name == nazwa katalogu
    OK  description (311 znakow)
    OK  allowed-tools: Read, Glob, Grep, Bash(python3 *scan_migration.py*), Bash(do
[hook] settings.snippet.json
    OK  matcher = Bash
    OK  command wskazuje na istniejacy skrypt: python3 "$CLAUDE_PROJECT_DIR/.claude/hooks/check-commit-message.py"
[py] skladnia
    OK  claude-hooks/check-commit-message.py
    OK  claude-skills/ef-migration-review/scan_migration.py
    OK  test_commit_hook.py
[scan] exit code skanera
    OK  20260925101500_RiskyChanges.cs -> exit 1
    OK  20260925103000_SafeAddColumn.cs -> exit 0

WYNIK: wszystkie pliki poprawne.
```

### Czego NIE zweryfikowano

- Samego działania w Claude Code: że `settings.json` z tym snippetem faktycznie wywoła
  hook przed `git commit` i że model zareaguje na stderr — pipeline odtworzono
  ręcznie (JSON na stdin → exit code), ale nie w żywej sesji.
- Że model faktycznie zaaktywuje skill po `description` i użyje skanera wg `SKILL.md` —
  to zachowanie modelu; zweryfikowano tylko frontmatter i sam skaner.
- Skaner nie był puszczony na migracjach wygenerowanych prawdziwym `dotnet ef` — pliki w
  `test-fixtures/` są pisane ręcznie w stylu scaffoldera i nie są kompilowane.
