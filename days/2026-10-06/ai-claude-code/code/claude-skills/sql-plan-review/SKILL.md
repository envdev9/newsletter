---
name: sql-plan-review
description: Review zapytań T-SQL i planów wykonania SQL Server (pliki .sql, .sqlplan / Showplan XML) pod kątem indeksów, skanów, Key Lookup, niejawnych konwersji, spillów i rozjazdu estymat. Użyj gdy ktoś prosi o optymalizację zapytania, wkleja plan wykonania, dodaje nowy .sql/migrację z zapytaniami albo pyta "czemu to jest wolne".
allowed-tools: Read, Glob, Grep, Bash(python3 *scan_sql.py*), Bash(python3 *scan_plan.py*)
---

# sql-plan-review

Dwa kroki: **deterministyczne skanery** (nic nie umknie), potem **ocena kontekstowa**.
Ten skill niczego nie wykonuje na bazie i nie zmienia plików - to review.

## Krok 1 - skanery

Dla plików `.sql`:

```bash
python3 .claude/skills/sql-plan-review/scan_sql.py <plik.sql>
```

Dla planu (`.sqlplan` zapisany z SSMS/ADS albo `SET STATISTICS XML ON`):

```bash
python3 .claude/skills/sql-plan-review/scan_plan.py <plan.sqlplan>
```

Wyjście: linie `... | WARN/INFO | REGUŁA | opis`, exit 1 = są WARN. To **kandydaci**, nie werdykt
(skaner nie zna typów kolumn, rozmiaru danych ani reszty indeksów).

## Krok 2 - ocena kontekstowa

1. **Sargowalność.** Dla każdego `NON-SARGABLE`: napisz przepisane zapytanie (np. `YEAR(d)=2026`
   -> `d >= '2026-01-01' AND d < '2027-01-01'`). Sprawdź zgodność typów parametru z kolumną.
2. **Indeks.** Nie kopiuj `MISSING-INDEX` na ślepo: sprawdź istniejące indeksy tabeli (Grep po
   `CREATE INDEX`/migracjach), czy nowy nie dubluje istniejącego z innym `INCLUDE`, i wspomnij
   koszt zapisu (INSERT/UPDATE). Kolejność kluczy: równość przed nierównością.
3. **Key Lookup.** Ile wierszy? Kilka - ignoruj. Tysiące - `INCLUDE` brakujących kolumn albo
   zawężenie SELECT.
4. **Estymaty.** `ESTIMATE-SKEW`/`SPILL`: statystyki (`UPDATE STATISTICS`), parameter sniffing
   (zapytaj, czy problem zależy od parametru), a dopiero potem hinty.
5. **Dane.** Zapytaj o rząd wielkości tabeli, jeśli go nie znasz - skan 500 wierszy to nie problem.
6. **Nie obiecuj przyspieszenia** bez pomiaru. Zaproponuj sposób pomiaru:
   `SET STATISTICS IO, TIME ON;` przed i po, plus porównanie planów.

## Format odpowiedzi

| Plik:linia / węzeł | Ryzyko | Problem | Proponowana poprawka |
|---|---|---|---|

Pod tabelą: **przepisane zapytanie** (jeśli dotyczy), **DDL indeksu** (jeśli zasadny) i jedno zdanie
o tym, **czego nie da się stwierdzić bez uruchomienia na prawdziwych danych**.
