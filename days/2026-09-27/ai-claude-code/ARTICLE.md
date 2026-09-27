<div align="center">

# 📰 TECH PRASÓWKA
### Wydanie #4 — 27 września 2026

![AI](https://img.shields.io/badge/AI_%2F_Claude_Code-D97757?style=for-the-badge&logo=anthropic&logoColor=white)
![Poziom](https://img.shields.io/badge/poziom-zaawansowany-red?style=for-the-badge)
![Testy](https://img.shields.io/badge/skanery-4%2F4%20(bez%20prawdziwego%20SQL%20Server)-yellow?style=for-the-badge)

## Skill do SQL: Claude czyta plan wykonania, zanim zrobi to DBA

</div>

---

> _"Indeks zasugerowany przez optymalizator to podpowiedź, nie polecenie. Model, który wkleja go
> na ślepo, po miesiącu zostawi Ci tabelę z dwudziestoma indeksami."_

W wydaniach #1–#3 były komendy, hooki i konfiguracja zespołu. Dziś **skill do SQL** — trzeci
rodzaj rozszerzenia obok komendy i hooka (jak w wydaniu #2: skill = instrukcja + skrypty, które
model ładuje, gdy `description` pasuje do zadania). Kod: [`code/`](code/).

---

## 1️⃣ 🗄️ `sql-plan-review`: dwa skanery + ocena kontekstowa

### 🎯 Dlaczego to ważne

Zapytanie "czemu to jest wolne?" kończy się zwykle jednym z kilkunastu powtarzalnych powodów:
funkcja na kolumnie w `WHERE`, brakujący indeks na kluczu obcym, `Key Lookup` w pętli,
niejawna konwersja `varchar`/`nvarchar`, spill do `tempdb`. Model bez pomocy **zgaduje** i bywa
przekonujący, kiedy się myli. Skill odwraca kolejność: najpierw deterministyczny skaner wskazuje
kandydatów (nic nie umknie, wynik jest powtarzalny), dopiero potem model ocenia sens — rozmiar
tabeli, istniejące indeksy, koszt zapisu.

| Krok | Kto | Co robi |
|---|---|---|
| 1 | 🐍 `scan_sql.py` | antywzorce w plikach `.sql` (regexy, stdlib) |
| 1 | 🐍 `scan_plan.py` | Showplan XML: indeksy, skany, lookupy, konwersje, spille, estymaty |
| 2 | 🤖 Claude wg `SKILL.md` | przepisuje zapytanie, waży DDL indeksu, prosi o brakujący kontekst |

### 🔎 Skaner `.sql` w akcji

[`samples/bad_orders.sql`](code/samples/bad_orders.sql) zbiera typowe grzechy. Prawdziwy wynik:

```
bad_orders.sql:14 | WARN | FK-NO-INDEX | klucz obcy na kolumnie 'CustomerId' bez indeksu z ta kolumna na pierwszym miejscu ...
bad_orders.sql:18 | WARN | SELECT-STAR | SELECT * - zwraca zbedne kolumny, uniemozliwia indeks pokrywajacy ...
bad_orders.sql:19 | WARN | NOLOCK | NOLOCK = READ UNCOMMITTED: brudne odczyty, pominiete/zdublowane wiersze; rozwaz RCSI
bad_orders.sql:20 | WARN | NON-SARGABLE | funkcja MONTH(...) na kolumnie w predykacie - blokuje Index Seek ...
bad_orders.sql:20 | WARN | NON-SARGABLE | funkcja YEAR(...) na kolumnie w predykacie - blokuje Index Seek ...
bad_orders.sql:25 | INFO | N-LITERAL | literal N'...' - jesli kolumna jest varchar, SQL Server konwertuje KOLUMNE ...
bad_orders.sql:25 | WARN | LEADING-WILDCARD | LIKE '%...' - wiodacy wildcard wymusza skan ...
bad_orders.sql:30 | WARN | NOT-IN-SUBQUERY | NOT IN (SELECT ...) - jedna wartosc NULL w podzapytaniu zwraca 0 wierszy; uzyj NOT EXISTS
bad_orders.sql:33 | INFO | TOP-NO-ORDER | TOP bez ORDER BY - wynik niedeterministyczny
```

(opisy skrócone `...`; pełne w wyjściu skryptu). Kilka rzeczy wartych uwagi:

- **Sargowalność** (`SARG` = *search ARGument able*): `YEAR(CreatedAt) = 2026` zmusza silnik do
  policzenia funkcji dla każdego wiersza, więc indeks po `CreatedAt` nie służy do seeka. Poprawka
  to zakres: `CreatedAt >= '2026-01-01' AND CreatedAt < '2027-01-01'` (półotwarty — działa też z `datetime2`
  z ułamkami sekund, w przeciwieństwie do `BETWEEN`).
- **`N'...'` na kolumnie `varchar`**: `nvarchar` ma wyższy priorytet typu, więc konwertowana jest *kolumna*,
  nie literał. Skaner daje tu tylko `INFO`, bo nie zna typu kolumny — to wiedza, którą ma dopiero model
  w kroku 2 (czyta `CREATE TABLE`).
- **`NOT IN (SELECT ...)`**: jeśli podzapytanie zwróci choć jedno `NULL`, całe wyrażenie nigdy nie jest prawdziwe.
  To bug logiczny, nie tylko wydajnościowy.
- Skaner **ignoruje komentarze** (w pliku jest `SELECT *` w komentarzu — nie jest zgłoszony) i traktuje
  `EXISTS (SELECT * ...)` jako poprawne.

Wersja przepisana, [`good_orders.sql`](code/samples/good_orders.sql): zakres zamiast funkcji, `NOT EXISTS`,
jawne kolumny, dwa indeksy z `INCLUDE`. Skaner: **zero uwag**, exit 0.

### 🗺️ Skaner planu wykonania

Jak zdobyć plan (Showplan XML): w SSMS/Azure Data Studio *Save Execution Plan As…*, albo w T-SQL:

```sql
SET STATISTICS XML ON;
SELECT o.OrderId, o.Total FROM dbo.Orders o WHERE o.CustomerId = @p;
SET STATISTICS XML OFF;
```

[`scan_plan.py`](code/claude-skills/sql-plan-review/scan_plan.py) czyta ten XML i zgłasza m.in.:

| Reguła | Co oznacza | Dlaczego boli |
|---|---|---|
| `MISSING-INDEX` | sugestia optymalizatora + wygenerowany `CREATE INDEX` | tylko podpowiedź; nie zna innych zapytań |
| `SCAN` | skan tabeli/indeksu (WARN od 10 tys. wierszy) | O(N) zamiast O(log N) |
| `KEY-LOOKUP` | dobieranie kolumn z klastrowego dla każdego wiersza | tysiące losowych odczytów |
| `IMPLICIT-CONVERT` | `PlanAffectingConvert` (`Seek Plan` = WARN) | seek zamienia się w skan |
| `SPILL` / `NO-STATISTICS` | dane nie mieszczą się w grancie / brak statystyk | zapis do `tempdb`, złe estymaty |
| `ESTIMATE-SKEW` | estymowane vs rzeczywiste wiersze (≥ x10, tylko plan „actual") | pierwszy trop na parameter sniffing |
| `NO-JOIN-PREDICATE` | join bez warunku | iloczyn kartezjański |

Wynik na fixturze `bad_plan.sqlplan` (fragment, `MISSING-INDEX` dosłownie):

```
bad_plan.sqlplan | stmt 1 | WARN | MISSING-INDEX | optymalizator sugeruje indeks (szacowany zysk 93.4%): CREATE NONCLUSTERED INDEX [IX_Orders_CustomerId] ON [dbo].[Orders] ([CustomerId]) INCLUDE ([Total]);  <- to PODPOWIEDZ, nie gotowiec: ...
bad_plan.sqlplan | stmt 1 | WARN | SCAN | NodeId=1 Clustered Index Scan na [Orders].[PK_Orders] (tabela ~5000000 wierszy, odczyt ~5000000) - ...
bad_plan.sqlplan | stmt 1 | WARN | SPILL | NodeId=3 Sort: spill do tempdb (poziom 1) - ...
```

`good_plan.sqlplan` (Index Seek, 12 estymowanych vs 14 rzeczywistych wierszy) daje ciszę.

> ⚠️ **Uczciwie: oba pliki planu są napisane ręcznie.** Środowisko, w którym powstał ten
> artykuł, nie ma ani SQL Server, ani `sqlcmd`, więc **nie mam prawdziwego planu** do pokazania.
> Fixtury mają komentarz w nagłówku, że nie są zrzutem z silnika. Test `4/4` dowodzi tylko, że skaner
> robi to, co zakładam o formacie XML — nie że format jest dokładnie taki. Nazwy elementów i atrybutów
> zapisałem z pamięci. **Nie mierzyłem też żadnego przyspieszenia** — liczby "zysk 93.4%" i "5 mln wierszy"
> pochodzą z fixtury, nie z pomiaru.

### 🐛 Błąd, który wyłapał test

Pierwsza wersja liczyła `ActualRows` operatora przez przeszukanie *wszystkich potomków*. Dla węzła
`Nested Loops` sumowała więc wiersze całego poddrzewa i raportowała absurdalny rozjazd estymat
(x525000) na operatorze, który nie miał własnych liczników. Po poprawce (tylko własne
`RunTimeInformation` operatora) ostrzeżenie pojawia się tam, gdzie powinno — na `Sort`. Klasyczna
pułapka przy przechodzeniu po drzewie planu: **`iter()` wchodzi w dół, a liczniki są per operator**.

### 📋 Skill: jak model ma z tego korzystać

[`SKILL.md`](code/claude-skills/sql-plan-review/SKILL.md) zawiera frontmatter (`description` mówi *kiedy* skill
uruchomić: prośba o optymalizację, wklejony plan, nowy `.sql`; `allowed-tools` ogranicza Bash do dwóch skryptów),
krok 1 (skanery) i krok 2, czyli pytania, na które skaner nie odpowie:

1. Czy `MISSING-INDEX` nie dubluje istniejącego indeksu z innym `INCLUDE`? (Grep po migracjach.)
2. Ile wierszy ma tabela? Skan 500 wierszy to nie problem.
3. Czy rozjazd estymat zależy od parametru (sniffing), czy od nieaktualnych statystyk?
4. Jak zmierzyć efekt: `SET STATISTICS IO, TIME ON;` przed i po.

Format odpowiedzi to tabela `Plik:linia | Ryzyko | Problem | Poprawka` + przepisane zapytanie + jedno zdanie o tym,
czego nie da się stwierdzić bez uruchomienia na prawdziwych danych.

### 💬 Przykładowe użycie (do skopiowania)

```text
Zrób review tego zapytania i planu: @Reports/MonthlyOrders.sql @Reports/MonthlyOrders.sqlplan
Użyj skilla sql-plan-review. Tabela Orders ma ok. 5 mln wierszy, zapisów ~200/s.
```

Ostatnie zdanie ma znaczenie: dajesz modelowi rząd wielkości i profil zapisu, czyli dokładnie to,
czego skaner nie widzi.

---

## 📎 Co zweryfikowano, a czego nie

| ✅ Uruchomione naprawdę | ⚠️ Niezweryfikowane |
|---|---|
| `run_tests.py` 4/4: `scan_sql.py` na złym i dobrym pliku, `scan_plan.py` na dwóch fixturach | **Cokolwiek na prawdziwym SQL Server** (`sqlcmd` niedostępny): plany są ręczne, żadnych pomiarów |
| Ignorowanie komentarzy, `EXISTS (SELECT *)`, poprawka liczenia `ActualRows` | Dokładne nazwy elementów/atrybutów Showplan XML (z pamięci) |
| | Fałszywe alarmy/przeoczenia regexów na dużych, realnych plikach `.sql` (dynamiczny SQL, wielolinijkowe konstrukcje) |
| | Progi (10 tys. wierszy, x10) — moje, arbitralne |
| | Auto-aktywacja skilla po `description` i `allowed-tools` w żywej sesji Claude Code |

Środowisko: Python 3.10.4 (tylko stdlib). Następny krok w rubryce: review komponentu Angular na signals
albo uruchomienie tego skilla przeciw prawdziwej bazie, gdy `sqlcmd` będzie dostępny.

---

<div align="center">

[← wróć do wydania #4 (wszystkie rubryki)](../README.md) · [spis wydań](../../README.md)

</div>
