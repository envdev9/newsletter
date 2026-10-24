# Kod do wydania #4 — skill `sql-plan-review` (T-SQL + plan wykonania)

Pełny artykuł: [`../ARTICLE.md`](../ARTICLE.md).

## Fragment prasówki, którego dotyczy ten kod

> **Skill `sql-plan-review`**: dwa deterministyczne skanery (`scan_sql.py` — antywzorce w `.sql`;
> `scan_plan.py` — Showplan XML: brakujące indeksy z gotowym `CREATE INDEX`, skany dużych tabel,
> Key Lookup, niejawna konwersja, spill, brak predykatu JOIN, rozjazd estymat) plus instrukcja
> oceny kontekstowej w `SKILL.md`. Skaner łapie kandydatów, Claude ocenia sens (rozmiar danych,
> istniejące indeksy, koszt zapisu). Ważne: **środowisko autora nie miało SQL Server ani `sqlcmd`**
> — pliki planów w `samples/` są napisane ręcznie, nie pochodzą z prawdziwej bazy.

## Struktura

```
code/
├── claude-skills/sql-plan-review/   # -> .claude/skills/sql-plan-review/
│   ├── SKILL.md
│   ├── scan_sql.py                  # regexowy skaner T-SQL (stdlib)
│   └── scan_plan.py                 # skaner Showplan XML (stdlib, xml.etree)
├── samples/
│   ├── bad_orders.sql / good_orders.sql       # antywzorce vs przepisane
│   └── bad_plan.sqlplan / good_plan.sqlplan   # RĘCZNIE napisane fixtury planów
└── run_tests.py                     # 4 przypadki: zły plik -> reguły, dobry -> cisza
```

Wymagania: Python 3.8+ (tylko stdlib). SQL Server **nie** jest potrzebny do uruchomienia skanerów.

## Jak uruchomić

Z katalogu `code/`:

```bash
python3 run_tests.py
python3 claude-skills/sql-plan-review/scan_sql.py samples/bad_orders.sql
python3 claude-skills/sql-plan-review/scan_plan.py samples/bad_plan.sqlplan
```

Użycie w prawdziwym repo:

```bash
mkdir -p .claude/skills
cp -r claude-skills/sql-plan-review .claude/skills/
```

Własny plan: w SSMS „Save Execution Plan As…" albo w T-SQL `SET STATISTICS XML ON; <zapytanie>; SET STATISTICS XML OFF;`
i zapisz kolumnę XML do pliku.

## Weryfikacja — co uruchomiono naprawdę

Python 3.10.4:

```
$ python3 run_tests.py
OK    scan_sql.py    bad_orders.sql       reguly: FK-NO-INDEX, LEADING-WILDCARD, N-LITERAL, NOLOCK, NON-SARGABLE, NOT-IN-SUBQUERY, SELECT-STAR, TOP-NO-ORDER
OK    scan_sql.py    good_orders.sql      reguly: -
OK    scan_plan.py   bad_plan.sqlplan     reguly: ESTIMATE-SKEW, IMPLICIT-CONVERT, KEY-LOOKUP, MEMORY-GRANT, MISSING-INDEX, NO-JOIN-PREDICATE, NO-STATISTICS, SCAN, SPILL
OK    scan_plan.py   good_plan.sqlplan     reguly: -

WYNIK: 4/4 przypadkow zgodnych
```

### Czego NIE zweryfikowano

- **Żadnego prawdziwego SQL Server / `sqlcmd`** (brak w środowisku). Skanery nie były uruchomione
  na planie wygenerowanym przez silnik — fixtury są ręczne, więc test dowodzi tylko, że skaner
  robi to, co zakładam o formacie.
- **Nazwy elementów/atrybutów Showplan XML** (`MissingIndexGroup@Impact`, `PlanAffectingConvert@ConvertIssue`,
  `Warnings@NoJoinPredicate`, `SpillToTempDb`, `IndexScan@Lookup`, `MemoryGrantInfo`, `RunTimeCountersPerThread@ActualRows`)
  zapisane z pamięci. Realne plany mogą mieć inne warianty (np. `SpillToTempDb` vs `SortSpillDetails`;
  obsłużyłem oba). Zweryfikuj na własnym planie.
- Heurystyki `scan_sql.py` to regexy: możliwe fałszywe alarmy (np. `LEFT(col,3)=` w JOIN, `FORMAT` w SELECT bywa flagowane
  tylko gdy występuje przed porównaniem) i przeoczenia (wielolinijkowe konstrukcje, dynamiczny SQL w stringach).
- Progi (`10 000` wierszy dla „dużej tabeli", rozjazd `x10`) są moje, arbitralne.
- Że Claude Code sam wybierze ten skill po `description` i że `allowed-tools` z `Bash(python3 *...*)` zadziała w żywej sesji.
