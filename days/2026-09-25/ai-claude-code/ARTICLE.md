<div align="center">

# 📰 TECH PRASÓWKA
### Wydanie #2 — 25 września 2026

![AI](https://img.shields.io/badge/AI_%2F_Claude_Code-D97757?style=for-the-badge&logo=anthropic&logoColor=white)
![Poziom](https://img.shields.io/badge/poziom-%C5%9Brednio%20zaawansowany-orange?style=for-the-badge)
![Zweryfikowane](https://img.shields.io/badge/hook-21%2F21%20test%C3%B3w-brightgreen?style=for-the-badge)

## Strażnik commitów i recenzent migracji EF Core — dwa kolejne pliki do `.claude/`

</div>

---

> _"Reguła, którą egzekwuje człowiek, działa do pierwszego piątku po 16:00. Reguła,
> którą egzekwuje kod wyjścia 2, działa zawsze."_

Wczoraj (#1): komenda generująca testy, hook na migracje SQL bez rollbacku, skill do
review Angulara. Dziś ciąg dalszy z tej samej półki, ale ciekawszy technicznie:
**hook, który czyta komendę powłoki** (a nie tylko ścieżkę pliku), oraz **skill, który
łączy skrypt z instrukcją** - model dostaje deterministyczne fakty, a dopiero potem
myśli. Kod: [`code/`](code/).

---

## 1️⃣ 🪝 Hook: `git commit` z niepoprawną wiadomością nie przejdzie

### 🎯 Dlaczego to ważne

Konwencja commitów (Conventional Commits: `feat(orders): ...`) ma sens tylko wtedy,
gdy jest **stosowana zawsze** - z niej generuje się changelog i wersjonowanie
semantyczne. A agent piszący commity sam z siebie robi to "po swojemu" (`Dodałem
filtrowanie.`), chyba że coś go fizycznie zatrzyma. Instrukcja w `CLAUDE.md` to prośba;
hook to bariera.

### Jak to działa

Wczorajszy hook łapał `Write|Edit` i czytał `file_path`. Ten łapie `Bash` i czyta
`tool_input.command`. Konfiguracja
([`settings.snippet.json`](code/claude-hooks/settings.snippet.json)):

```json
{
  "hooks": {
    "PreToolUse": [
      {
        "matcher": "Bash",
        "hooks": [
          { "type": "command",
            "command": "python3 \"$CLAUDE_PROJECT_DIR/.claude/hooks/check-commit-message.py\"" }
        ]
      }
    ]
  }
}
```

Trudność: `command` to **dowolny tekst powłoki**. `git commit` może stać po `&&`,
mieć flagi sklejone (`-am "msg"`), być wywołany jako `git -C ../repo commit`, a
Claude Code lubi przekazywać wiadomość przez heredoc `-m "$(cat <<'EOF' ... EOF)"`.
[`check-commit-message.py`](code/claude-hooks/check-commit-message.py) radzi sobie z tym
tak: tokenizuje komendę `shlex`-em, tnie na segmenty po `; && || |`, w każdym szuka
`git [opcje globalne] commit`, wyciąga wiadomości z `-m`/`-am`/`--message=`,
rozwija heredoc regexem - i dopiero wtedy waliduje pierwszą linię:

| Reguła | Przykład złamania |
|---|---|
| format `typ(scope)!: opis` (typy: feat, fix, docs, style, refactor, perf, test, build, ci, chore, revert) | `Dodalem filtrowanie` |
| subject ≤ 72 znaki | 80-znakowy opis |
| bez kropki na końcu | `fix(api): napraw null.` |
| pusta linia między subjectem a body | `-m "fix(a): b\nbody"` |

### ▶️ Prawdziwy przebieg

Payload na stdin - dokładnie to, co dostałby hook od Claude Code
(`{"tool_name":"Bash","tool_input":{"command":"git commit -am \"Dodalem filtrowanie zamowien.\""}}`):

```
$ python3 claude-hooks/check-commit-message.py < claude-hooks/test-fixtures/block-commit.json
BLOKADA: wiadomosc commita lamie konwencje (Conventional Commits):
  - subject nie pasuje do formatu 'typ(scope)!: opis' (typy: feat, fix, docs, style, refactor, perf, test, build, ci, chore, revert)
  - subject nie powinien konczyc sie kropka
Subject: 'Dodalem filtrowanie zamowien.'
Przyklad poprawnego: feat(orders): dodaj filtrowanie po statusie
Popraw wiadomosc i ponow `git commit`.
(exit code: 2)
```

Ten sam commit z `feat(orders): dodaj filtrowanie po statusie` → exit **0**, cisza.
Cały zestaw - 21 komend (heredoc, `&&`, `git -C`, `-am`, `--message=`, merge, `--amend
--no-edit`, `-F`, `echo "git commit ..."`, inne narzędzie niż Bash):

```
$ python3 test_commit_hook.py
...
WYNIK: 21/21 przypadkow zgodnych
```

(pełna lista: [`code/README.md`](code/README.md)). Komunikat na stderr jest
napisany pod model, nie pod człowieka: zawiera regułę, co było złe i **przykład
poprawnego** - dlatego agent zwykle poprawia się w następnym kroku bez pytania Cię o cokolwiek.

> ⚠️ **Uczciwie o granicach.** To bariera na *typowe* przypadki, nie granica bezpieczeństwa.
> Hook celowo **przepuszcza**, gdy nie umie ustalić treści: `-F plik`, wiadomość ze
> zmiennej powłoki (`-m "$MSG"`), `git commit` bez `-m` (edytor), `--amend --no-edit`,
> oraz subjecty `Merge `/`Revert `/`fixup!`/`squash!`. Wolimy fałszywy pass niż
> zablokowanie poprawnej pracy nieczytelnym błędem. Do twardej egzekucji dołóż
> `commit-msg` hook w samym gicie / check w CI.

---

## 2️⃣ 🧙 Skill: review migracji EF Core - skrypt + instrukcja

### 🎯 Dlaczego to ważne

Migracja EF Core wygląda niewinnie, a bywa najgroźniejszą częścią PR-a. Klasyk:
zmieniasz nazwę właściwości, scaffolder generuje `DropColumn` + `AddColumn`, i na
produkcji znika kolumna z danymi. Albo `AddColumn` NOT NULL z `defaultValue: ""`, które
po cichu wypełnia miliony wierszy śmieciową wartością. Albo pusty `Down()`. Review "na
oko" tego nie łapie systematycznie; LLM-owi samemu też zdarza się coś pominąć.

### Wzorzec: najpierw fakty, potem osąd

[`SKILL.md`](code/claude-skills/ef-migration-review/SKILL.md) ma dwa kroki:

1. **Skaner** [`scan_migration.py`](code/claude-skills/ef-migration-review/scan_migration.py)
   (bez zależności, regex po liniach) wypisuje *kandydatów*: `DropTable`/`DropColumn`
   w `Up()`, `AlterColumn`, `AddColumn` NOT NULL (i czy z wartością domyślną),
   `CreateIndex`, surowy `migrationBuilder.Sql`, brakujący lub pusty `Down()`.
   `DropColumn` w `Down()` jest ignorowany - to legalne cofnięcie `AddColumn`.
2. **Ocena kontekstowa** - lista pytań, na które skaner nie odpowie: czy to miał być
   rename, czy stara wersja aplikacji przeżyje nowy schemat (rolling deploy →
   expand/contract), jak duża jest tabela pod `CreateIndex`, czy snapshot jest spójny
   (`dotnet ef migrations has-pending-model-changes`), czy dać DBA skrypt
   `dotnet ef migrations script --idempotent`.

Zysk: model nie musi "pamiętać", czego szukać i nie halucynuje numerów linii - dostaje
je ze skryptu. Skill deklaruje też wąskie `allowed-tools` (Read/Glob/Grep + konkretne
polecenia `python3 ...scan_migration.py` i `dotnet ef ...`).

### ▶️ Prawdziwy przebieg skanera

Na ręcznie napisanej, "grzesznej" migracji
([`20260925101500_RiskyChanges.cs`](code/claude-skills/ef-migration-review/test-fixtures/20260925101500_RiskyChanges.cs)):

```
$ python3 scan_migration.py .../20260925101500_RiskyChanges.cs
...RiskyChanges.cs:15 | HIGH   | DropColumn - utrata danych; rozważ najpierw wdrozenie kodu, ktory kolumny nie uzywa (expand/contract)
...RiskyChanges.cs:19 | MEDIUM | AddColumn NOT NULL z defaultValue - istniejace wiersze dostana wartosc domyslna (scaffolder daje 0/""/false); czy to poprawne biznesowo?
...RiskyChanges.cs:26 | MEDIUM | AlterColumn - sprawdz zawezenie typu/dlugosci/nullability; na duzych tabelach moze blokowac
...RiskyChanges.cs:36 | MEDIUM | CreateIndex - na duzej tabeli SQL Server blokuje zapisy; rozwaz .Annotation("SqlServer:Online", true) (edycje z online index)
...RiskyChanges.cs:44 | HIGH   | Down() jest pusta - migracji nie da sie wycofac

Znalezisk: 5
(exit code: 1)
```

Na bezpiecznej migracji (nullable `AddColumn` + `Down()` z `DropColumn`): `Znalezisk: 0`,
exit **0**.

---

## 📊 Wydanie #1 vs #2 w jednej tabeli

| | Wydanie #1 | Wydanie #2 |
|---|---|---|
| Hook czyta | `file_path` / treść zapisu | **komendę powłoki** (`command`) |
| Matcher | `Write\|Edit` | `Bash` |
| Trudność | prosty regex | parsowanie powłoki (`shlex`, segmenty, heredoc) |
| Skill | sama checklista | **checklista + skrypt** (fakty przed osądem) |

---

## 📎 Co zweryfikowano, a czego nie

| ✅ Uruchomione naprawdę | ⚠️ Niezweryfikowane |
|---|---|
| Hook: 2 payloady ze stdin (exit 2 + stderr / exit 0) i 21 przypadków w `test_commit_hook.py` | Wpięcie `settings.json` w żywej sesji Claude Code i reakcja modelu na stderr |
| Skaner na 2 migracjach (exit 1 / exit 0) | Samoczynna aktywacja skilla po `description` i użycie skanera przez model |
| `validate.py`: frontmatter skilla, JSON snippetu, składnia skryptów | Skaner na migracjach z prawdziwego `dotnet ef` (fixtury pisane ręcznie, niekompilowane) |

Środowisko: Python 3.10.4, kod bez zależności poza `PyYAML` w `validate.py`.

---

<div align="center">

[← wróć do wydania #2 (wszystkie rubryki)](../README.md) · [spis wydań](../../README.md)

</div>
