# Kod do wydania #1 — trzy konfiguracje Claude Code dla .NET/Angular/SQL

Pełny artykuł: [`../ARTICLE.md`](../ARTICLE.md). Poniżej te same pliki + jak je
zweryfikować/użyć.

## Fragment prasówki, którego dotyczy ten kod

> Trzy konkretne pliki konfiguracyjne, które można wrzucić do repo `.claude/`
> dzisiaj i mieć z nich korzyść jutro rano: **slash command** generujący testy
> jednostkowe dla klasy C#, **hook** blokujący zapis migracji SQL bez rollbacku,
> i **skill** do code-review komponentu Angular.

## Struktura

```
code/
├── claude-commands/
│   └── gen-csharp-tests.md          # .claude/commands/gen-csharp-tests.md w docelowym repo
├── claude-hooks/
│   ├── check-sql-rollback.py        # .claude/hooks/check-sql-rollback.py w docelowym repo
│   ├── settings.snippet.json        # jak wpiąć hook do .claude/settings.json
│   └── test-fixtures/               # przykładowe payloady stdin do testów hooka
├── claude-skills/
│   └── angular-component-review/
│       └── SKILL.md                 # .claude/skills/angular-component-review/SKILL.md
└── validate.py                      # walidator frontmatter + składni hooka
```

## Jak użyć w prawdziwym repo

1. Skopiuj odpowiedni plik/katalog pod `.claude/` w swoim projekcie:
   ```bash
   cp claude-commands/gen-csharp-tests.md   /ścieżka/do/repo/.claude/commands/
   mkdir -p /ścieżka/do/repo/.claude/hooks
   cp claude-hooks/check-sql-rollback.py    /ścieżka/do/repo/.claude/hooks/
   chmod +x /ścieżka/do/repo/.claude/hooks/check-sql-rollback.py
   cp -r claude-skills/angular-component-review /ścieżka/do/repo/.claude/skills/
   ```
2. Dorzuć zawartość `claude-hooks/settings.snippet.json` do `.claude/settings.json`
   tego repo (sekcja `hooks.PreToolUse`) - jeśli plik już ma inne hooki, dopisz do
   istniejącej listy, nie nadpisuj.
3. Restart Claude Code w tym repo, żeby podjął nowy `settings.json`.
4. Slash command: `/gen-csharp-tests src/Services/OrderService.cs`.
   Skill: uruchamia się automatycznie, gdy poprosisz o review komponentu Angular,
   albo jawnie: "użyj skilla angular-component-review dla tego diffu".
   Hook: działa w tle, bez wywoływania - zobaczysz go tylko, gdy zablokuje zapis.

## Weryfikacja — co dało się uruchomić i jak

**Slash command i skill** to pliki instrukcji dla Claude Code (Markdown +
frontmatter) - nie da się ich "uruchomić" bez samego Claude Code jako procesu.
Zweryfikowano więc to, co da się sprawdzić statycznie: że frontmatter jest poprawnym
YAML-em z wymaganymi kluczami, i (dla skilla) że `name` w frontmatterze zgadza się z
nazwą katalogu.

**Hook** to zwykły skrypt Pythona przyjmujący JSON na stdin - w pełni uruchamialny
bez Claude Code, więc uruchomiono go naprawdę na 4 przykładowych wywołaniach.

### `python3 validate.py`

```
$ python3 validate.py
[command] claude-commands/gen-csharp-tests.md
    description: OK (Generuje kompletny plik testów jednostkowych (xUnit) dla wsk)
    argument-hint: OK ([ścieżka-do-pliku.cs])
    allowed-tools: OK (Read, Write, Glob, Bash(dotnet build:*), Bash(dotnet test:*))
[skill]   claude-skills/angular-component-review/SKILL.md
    name: OK (angular-component-review)
    description: OK (270 znaków)
[hook]    claude-hooks/check-sql-rollback.py
    składnia Pythona: OK
    bit wykonywalności: OK

WYNIK: wszystkie pliki poprawne.
$ echo "exit: $?"
exit: 0
```

### Hook na 4 przykładowych payloadach (`claude-hooks/test-fixtures/`)

```bash
python3 claude-hooks/check-sql-rollback.py < claude-hooks/test-fixtures/block-write.json
echo "exit: $?"
```

Migracja `Write` bez `-- ROLLBACK` → **zablokowane**:

```
BLOKADA: plik migracji '/repo/db/migrations/2026-09-24_add_customer_index.sql' nie zawiera sekcji '-- ROLLBACK'.
Każda migracja SQL w tym repo musi mieć blok rollbacku, np.:

-- ROLLBACK
-- DROP INDEX ix_orders_customer;

Dopisz sekcję rollbacku do tej migracji i spróbuj ponownie.
exit: 2
```

```bash
python3 claude-hooks/check-sql-rollback.py < claude-hooks/test-fixtures/allow-write-with-rollback.json
echo "exit: $?"
```

Ta sama migracja, ale z sekcją `-- ROLLBACK` w treści → **dozwolone** (brak outputu):

```
exit: 0
```

```bash
python3 claude-hooks/check-sql-rollback.py < claude-hooks/test-fixtures/allow-non-migration.json
echo "exit: $?"
```

Zapis pliku `.cs` (nie migracji) → hook nie ingeruje, **dozwolone**:

```
exit: 0
```

```bash
python3 claude-hooks/check-sql-rollback.py < claude-hooks/test-fixtures/block-edit.json
echo "exit: $?"
```

Narzędzie `Edit` (nie `Write`) dopisujące do migracji bez rollbacku w `new_string` →
hook sprawdza też `Edit`, **zablokowane**:

```
BLOKADA: plik migracji '/repo/db/migrations/2026-09-24_add_customer_index.sql' nie zawiera sekcji '-- ROLLBACK'.
Każda migracja SQL w tym repo musi mieć blok rollbacku, np.:

-- ROLLBACK
-- DROP INDEX ix_orders_customer;

Dopisz sekcję rollbacku do tej migracji i spróbuj ponownie.
exit: 2
```

Wszystkie cztery przebiegi i `validate.py` uruchomiono lokalnie (`python3 3.10.4`,
`PyYAML 5.4.1`) przed publikacją tego wpisu — output powyżej jest rzeczywisty, nie
zmyślony.
