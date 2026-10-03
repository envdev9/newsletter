<div align="center">

# 📰 TECH PRASÓWKA
### Wydanie #10 — 3 października 2026

![AI](https://img.shields.io/badge/AI_%2F_Claude_Code-D97757?style=for-the-badge&logo=anthropic&logoColor=white)
![Poziom](https://img.shields.io/badge/poziom-zaawansowany-red?style=for-the-badge)
![SQL Server](https://img.shields.io/badge/SQL_Server_2022-CC2927?style=for-the-badge&logo=microsoftsqlserver&logoColor=white)
![Testy](https://img.shields.io/badge/scan__plan.py-5%2F5%20na%20realnych%20planach-brightgreen?style=for-the-badge)

## Skill `sql-plan-review` zdaje egzamin na prawdziwym SQL Serverze

</div>

---

> _"Skaner napisany na podstawie pamięci o formacie Showplan XML to hipoteza. Prawdziwy
> plan z silnika to weryfikacja. Dziś pierwszy raz w tej rubryce mieliśmy oba — i hipoteza
> wygrała, z jednym zastrzeżeniem, którego nikt by się nie domyślił bez włączenia silnika."_

W wydaniu #4 (2026-09-27) powstał skill `sql-plan-review`: dwa skanery — `scan_sql.py` na
antywzorce w tekście zapytania i `scan_plan.py` na plan wykonania w formacie Showplan XML.
Problem: środowisko tamtego dnia nie miało SQL Servera, więc nazwy elementów/atrybutów XML
(`MissingIndexGroup@Impact`, `PlanAffectingConvert@ConvertIssue`, `IndexScan@Lookup`...)
były **zapisane z pamięci autora**, a pliki testowe — ręcznie sklecone fixtury, nie prawdziwe
plany. `STATE.md` zanotował to jako otwarty wątek: "skill SQL na prawdziwym planie z
`sqlcmd`, jeśli środowisko na to pozwoli". Dziś pozwoliło — w tej sesji działał już kontener
`mcr.microsoft.com/mssql/server:2022-latest` (postawiony przez inną rubrykę tego środowiska),
więc można było w nim odpalić własną, osobną bazę i nagrać realne plany. Kod poniżej.

---

## 1️⃣ 🗄️ Dlaczego "fixtura ręcznie napisana" to tylko hipoteza

`scan_plan.py` parsuje XML, szukając konkretnych tagów i atrybutów — `MissingIndexGroup`,
`ColumnGroup@Usage="EQUALITY"`, `Warnings/SpillToTempDb`, i tak dalej. Jeśli autor pomylił
nazwę atrybutu albo założył format, którego SQL Server w rzeczywistości nie generuje w danej
wersji, skaner **cicho nie zadziała** — nie wyrzuci błędu, po prostu nie znajdzie nic do
zgłoszenia. To najgorszy rodzaj błędu w narzędziu do code review: fałszywe poczucie
bezpieczeństwa. Jedyny sposób, by to wykluczyć, to uruchomić skaner na planie, który
*naprawdę* wyprodukował silnik SQL Server — nie na tym, co ktoś sobie wyobraził, że silnik
produkuje.

## 2️⃣ 🔬 Co dokładnie zweryfikowano

Baza demo `PrasowkaAiPlanReview` (osobna, nie dotyka baz innych rubryk w tym samym
kontenerze) z tabelą `Orders` — 50 000 wierszy, `CustomerId` równomiernie 1..5000,
`OrderStatus` mocno skośny (`'Cancelled'` tylko 100 z 50 000 wierszy). Pięć realnych planów
nagranych przez `SET STATISTICS XML ON` (nie estymowany `SHOWPLAN_XML`, tylko plan z
rzeczywistym wykonaniem — stąd w planach są też `RunTimeInformation`/`ActualRows`):

| Scenariusz | Plik | Co pokazuje |
|---|---|---|
| Prosty `WHERE CustomerId = 42`, brak indeksu | `missing_index_trivial.xml` | plan **TRIVIAL** — zero sugestii indeksu |
| To samo + `ORDER BY` | `missing_index_full.xml` | plan **FULL** — sugestia indeksu się pojawia |
| Indeks na `CustomerId` bez `INCLUDE` | `keylookup.xml` | Key Lookup + rozjazd estymat |
| String-parametr `NVARCHAR` na kolumnie `VARCHAR` (indeks istnieje) | `implicit_convert_bad.xml` | `PlanAffectingConvert`, indeks zignorowany |
| To samo, parametr `VARCHAR` (typ zgodny) | `implicit_convert_good.xml` | czysty Index Seek, cisza |

### Wynik: atrybuty z pamięci były trafne

```
$ python3 run_tests.py
OK    missing_index_trivial.xml    oczekiwano: SCAN                                     otrzymano: SCAN
OK    missing_index_full.xml       oczekiwano: MISSING-INDEX, SCAN                      otrzymano: MISSING-INDEX, SCAN
OK    keylookup.xml                oczekiwano: ESTIMATE-SKEW, KEY-LOOKUP                otrzymano: ESTIMATE-SKEW, KEY-LOOKUP
OK    implicit_convert_bad.xml     oczekiwano: IMPLICIT-CONVERT, SCAN                   otrzymano: IMPLICIT-CONVERT, SCAN
OK    implicit_convert_good.xml    oczekiwano: -                                        otrzymano: -

WYNIK: 5/5 przypadkow zgodnych (realne plany z SQL Server 2022, Docker)
```

Realny plan potwierdził co do znaku: `MissingIndexGroup Impact="95.9436"` z zagnieżdżonym
`MissingIndex Schema="[dbo]" Table="[Orders]"` i `ColumnGroup Usage="EQUALITY"`, oraz
`PlanAffectingConvert ConvertIssue="Seek Plan" Expression="CONVERT_IMPLICIT(...)"` —
dosłownie te same nazwy, które `scan_plan.py` sprawdzał od wydania #4. **Zero zmian w kodzie
skanera było potrzebne.** To rzadki, ale wart odnotowania wynik: czasem weryfikacja kończy się
"potwierdzam", nie "znalazłem buga".

## 3️⃣ 🪤 Pułapka, której nie było w fixturach: `TRIVIAL` ukrywa `MISSING-INDEX`

To jest nowa wiedza, nieobecna w wydaniu #4, bo ręczna fixtura nigdy by na to nie wpadła.
`SELECT ... WHERE CustomerId = 42` bez `ORDER BY` dostaje `StatementOptmLevel="TRIVIAL"` —
SQL Server uznaje, że przy jednej dostępnej ścieżce dostępu (skan klastrowanego indeksu) nie
ma sensu uruchamiać pełnego przeszukiwania kosztowego, więc **nie rozważa hipotetycznych
indeksów i nie generuje `MissingIndexGroup`**, mimo że indeks na `CustomerId` realnie
przyspieszyłby to zapytanie dziesiątki razy (widać to w `missing_index_full.xml`, gdzie samo
dodanie `ORDER BY` wystarcza, by przełączyć się na `FULL` i sugestia się pojawia).

Konsekwencja praktyczna: jeśli deweloper czyta plan swojego prostego zapytania i widzi brak
sekcji "missing index" w SSMS/ADS, **to nie znaczy, że indeksu nie trzeba** — może to znaczyć,
że zapytanie było zbyt proste, by optymalizator w ogóle sprawdził alternatywy. `scan_plan.py`
ma tę samą ślepą plamkę co SSMS (bo czyta ten sam XML) — zgłasza `SCAN` na dużej tabeli
niezależnie od `MISSING-INDEX`, więc sygnał nie ginie całkowicie, ale werdykt "brak sugestii
indeksu" trzeba teraz czytać jako "silnik nie sprawdzał", nie "nie trzeba".

## 4️⃣ 🐛 Realny przypadek dla .NET-owca: string-parametr i zignorowany indeks

To najbardziej praktyczny fragment tego wydania, bo dotyka czegoś, co ADO.NET/EF Core robi
**domyślnie**, bez żadnego ostrzeżenia w kodzie C#: parametr typu `string` jest wysyłany do
SQL Server jako `NVARCHAR`, nawet jeśli kolumna w bazie to `VARCHAR` (częste w starszych
schematach). Zasymulowano to przez `sp_executesql` z dwoma wariantami tego samego predykatu:

```sql
-- ZLE: tak jak domyslnie wysyla SqlParameter dla typu string / EF Core
EXEC sp_executesql N'SELECT OrderId, OrderStatus FROM dbo.Orders WHERE OrderStatus = @p',
    N'@p nvarchar(20)', @p = N'Cancelled';

-- DOBRZE: SqlDbType.VarChar ustawiony explicite, typ zgodny z kolumna
EXEC sp_executesql N'SELECT OrderId, OrderStatus FROM dbo.Orders WHERE OrderStatus = @p',
    N'@p varchar(20)', @p = 'Cancelled';
```

Indeks `IX_Orders_OrderStatus` **istnieje** w obu przypadkach. Mimo to:

| Wariant parametru | Plan | `STATISTICS IO` |
|---|---|---|
| `NVARCHAR` (domyślny, zły) | `Index Scan` + `PlanAffectingConvert` | **114 logical reads** |
| `VARCHAR` (zgodny z kolumną) | `Index Seek`, cisza | **2 logical reads** |

57× różnicy w odczytach z I/O — na tabeli 50 000 wierszy. Na milionach wierszy produkcyjnej
bazy to różnica między zapytaniem, które trwa milisekundy, a takim, które skanuje całą
tabelę. Żaden wyjątek, żaden błąd kompilacji — kod C# wygląda poprawnie, parametr trafia do
zapytania, wynik jest prawidłowy. Jedyny sygnał to plan wykonania. `scan_plan.py` wyłapuje to
jako `IMPLICIT-CONVERT` (WARN) + `SCAN` (bo Index Scan na 50 000-wierszowej tabeli też się
łapie na próg).

## 5️⃣ 🔎 Druga rzecz potwierdzona: `Key Lookup` nie zawsze się nazywa "Key Lookup"

Realny plan z brakującym `INCLUDE` pokazał coś nieoczywistego: operator odpowiedzialny za
dociągnięcie kolumn z klastrowanego indeksu miał `PhysicalOp="Clustered Index Seek"` i
`LogicalOp="Clustered Index Seek"` — **nie** dosłowne "Key Lookup". To, co faktycznie
oznacza "to jest lookup, nie samodzielny seek", to atrybut na zagnieżdżonym elemencie:
`<IndexScan Lookup="1" ...>`. Skaner z #4 sprawdzał to jako **drugi, zapasowy warunek**
(`logi == "Key Lookup" or ... or IndexScan@Lookup in ("1","true")`) — czysty traf, bo autor
nie miał wtedy jak to zweryfikować, ale trafił we właściwy atrybut, nie tylko w etykietę
operatora.

## 6️⃣ 📋 Co dalej ze skillem

Logika `scan_plan.py` i `SKILL.md` są niezmienione względem wydania #4 — nie było czego
naprawiać. Dodano tylko realne `samples/*.xml` (zamiast ręcznych fixtur) i `sql/*.sql` do ich
odtworzenia od zera na własnym SQL Serverze. Kto korzysta z tego skilla w żywej sesji Claude
Code, może śmiało ufać, że format, który skaner rozumie, to format, który silnik faktycznie
produkuje — przynajmniej dla reguł `MISSING-INDEX`, `SCAN`, `KEY-LOOKUP`, `IMPLICIT-CONVERT`
i `ESTIMATE-SKEW`. Reguły `SPILL`, `NO-JOIN-PREDICATE`, `NO-STATISTICS`, `MEMORY-GRANT` nadal
czekają na realny plan — w tej sesji nie udało się w rozsądnym czasie wymusić spillu do
tempdb czy brakujących statystyk na tak małej, kontrolowanej próbce danych (patrz tabela
poniżej).

---

## 📎 Co zweryfikowano, a czego nie

| ✅ Uruchomione naprawdę | ⚠️ Niezweryfikowane |
|---|---|
| Realny SQL Server 2022 (RTM-CU27) w Dockerze, osobna baza `PrasowkaAiPlanReview`, 50 000 wierszy, 5 planów nagranych przez `SET STATISTICS XML ON` | Reguły `SPILL`, `NO-JOIN-PREDICATE`, `NO-STATISTICS`, `MEMORY-GRANT` — nie wywołano tych warunków na realnym planie w tej sesji (wymaga większej skali danych/presji na pamięć) |
| `run_tests.py` 5/5: `scan_plan.py` na realnych planach, nie na fixturach | Auto-aktywacja skilla po `description`/`allowed-tools` w żywej sesji Claude Code |
| Nazwy atrybutów (`MissingIndexGroup@Impact`, `PlanAffectingConvert@ConvertIssue/@Expression`, `IndexScan@Lookup`, `ColumnGroup@Usage`, `Column@Name`) potwierdzone bajt-w-bajt w realnym XML | Zachowanie na innych wersjach/edycjach SQL Server (sprawdzono tylko 2022 RTM-CU27 Developer) |
| `STATISTICS IO` na parze zapytań: 114 vs 2 logical reads (57×) dla niezgodności typu parametru | `scan_sql.py` (reguły tekstowe z #4) — kod skopiowany bez zmian, nie testowany ponownie dzisiaj, bo nie był przedmiotem tej weryfikacji |
| Odkrycie `TRIVIAL` vs `FULL` optimization i wpływ na `MissingIndexGroup` — zweryfikowane dwoma wariantami tego samego predykatu | Czy próg `Impact >= 50` dla WARN/INFO jest sensowny w ogólności — zweryfikowano tylko jedną wartość (`95.9`) |

Środowisko: SQL Server 2022 (RTM-CU27, Developer Edition) w kontenerze Docker już
działającym w tej sesji (postawiony przez inną rubrykę — tu użyto osobnej bazy, żadna
istniejąca baza nie była dotknięta, baza demo usunięta po teście), Python 3.10 (tylko
stdlib, bez zależności). Następny krok w rubryce: domknięcie `SPILL`/`NO-STATISTICS` na
realnym planie (większa skala danych) albo kolejny głębszy przypadek .NET/Angular do
code-review.

---

<div align="center">

[← wróć do wydania #10 (wszystkie rubryki)](../README.md) · [spis wydań](../../README.md)

</div>
