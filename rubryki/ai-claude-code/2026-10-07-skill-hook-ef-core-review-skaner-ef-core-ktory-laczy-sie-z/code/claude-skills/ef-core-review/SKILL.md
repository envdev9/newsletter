---
name: ef-core-review
description: Review kodu EF Core (pliki .cs z DbContext, LINQ do bazy, konfiguracja modelu) pod katem antywzorcow dajacych zle plany i zbedne zapytania - N+1, ToList() przed Where, Include bez AsSplitQuery, funkcje na kolumnie w predykacie, brak AsNoTracking, SaveChanges w petli, string -> nvarchar na kolumnie varchar. Uzyj gdy ktos prosi o review kodu dostepu do danych, pisze/edytuje repozytorium lub handler z EF Core, pyta "czemu to zapytanie jest wolne" albo wkleja plan wykonania wygenerowany przez aplikacje .NET.
allowed-tools: Read, Glob, Grep, Bash(python3 *scan_ef.py*), Bash(python3 *scan_plan.py*)
---

# ef-core-review

Najpierw **skaner deterministyczny**, potem **ocena kontekstowa**. Skill niczego nie uruchamia
na bazie ani nie zmienia plikow - to review.

## Krok 1 - skaner kodu

```bash
python3 .claude/skills/ef-core-review/scan_ef.py <plik.cs | katalog>
```

Wyjscie: `plik:linia | WARN/INFO | REGULA | opis`; exit 1 = sa WARN. To **kandydaci**, nie werdykt
(skaner jest tekstowy: nie widzi typow z kompilatora, a kontekst rozpoznaje po nazwie zmiennej:
`db`, `ctx`, `context`, `dbContext`, `*Context`, `*Db`).

| Regula | Znaczy |
|---|---|
| `N-PLUS-1` | zapytanie do bazy w petli |
| `SAVECHANGES-IN-LOOP` | `SaveChanges` w petli |
| `TOLIST-BEFORE-FILTER` | `ToList()`/`ToArray()` przed `Where`/`Count`/... |
| `INCLUDE-NO-SPLIT` | >= 2 x `Include` bez `AsSplitQuery`/`AsSingleQuery` |
| `FUNC-ON-COLUMN` | `ToLower`/`Trim`/`Year`... na kolumnie w predykacie |
| `NO-ASNOTRACKING` (INFO) | odczyt bez `AsNoTracking()` w metodzie bez zapisu |
| `STRING-UNICODE` (INFO) | indeksowany `string` bez `IsUnicode(false)` / `varchar` |

Swiadoma decyzja: `// ef-review: ignore REGULA` nad instrukcja (albo na jej linii).

## Krok 2 - ocena kontekstowa

1. **N+1 / Include.** Czy petla jest po malej, ograniczonej liczbie elementow? Zaproponuj
   przepisanie na jedno zapytanie (`Select` z agregatem, `Include`, `Where(ids.Contains(...))`).
   Dla `INCLUDE-NO-SPLIT`: jedna kolekcja i wiele referencji to NIE problem - dwie kolekcje to tak;
   `AsSplitQuery` ma wlasny koszt (kilka rund, brak spojnosci migawki bez transakcji).
2. **STRING-UNICODE.** Sprawdz typ kolumny w bazie (migracje, `INFORMATION_SCHEMA.COLUMNS`).
   Jesli to `varchar` - dodaj `IsUnicode(false)` (migracja bez zmiany schematu) i zmierz plan.
   Jesli `nvarchar` - ignoruj regule.
3. **FUNC-ON-COLUMN.** Kolacja SQL Server zwykle jest case-insensitive - `ToLower()` jest zbedne.
   Dla dat przepisz `x.Date.Year == 2026` na zakres `>= ... && < ...`.
4. **NO-ASNOTRACKING.** Nie dodawaj, jesli encje sa potem modyfikowane/zapisywane w innej metodzie.
5. **Plan.** Jesli masz plan (`SET STATISTICS XML ON`, `.sqlplan`, plan z cache), przepusc przez
   `scan_plan.py` ze skilla `sql-plan-review` - potwierdza `IMPLICIT-CONVERT`/`SCAN` tym, co
   zrobil prawdziwy silnik. Nie obiecuj przyspieszenia bez pomiaru (`SET STATISTICS IO ON`).

## Format odpowiedzi

| Plik:linia | Regula | Problem | Poprawka |
|---|---|---|---|

Pod tabela: **przepisany kod**, a na koncu jedno zdanie o tym, **czego nie da sie stwierdzic
bez uruchomienia na prawdziwych danych**.
