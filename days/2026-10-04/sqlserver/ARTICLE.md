<div align="center">

# 📰 TECH PRASÓWKA
### Wydanie #8 — 4 października 2026

![SQL Server](https://img.shields.io/badge/SQL_Server-CC2927?style=for-the-badge&logo=microsoftsqlserver&logoColor=white)
![Poziom](https://img.shields.io/badge/poziom-zaawansowany-orange?style=for-the-badge)
![Zweryfikowane](https://img.shields.io/badge/kod-uruchomiony_na_SQL_Server_2022_CU27-brightgreen?style=for-the-badge)

## DELETE na columnstore nie usuwa nic. I licznik, który to powinien pokazać, też milczy

</div>

---

> _"Skasowałem 300 000 wierszy. Baza natychmiast liczy poprawnie. A metadane, które
> miały mi powiedzieć »tu jest 300 000 skasowanych wierszy«, uparcie pokazują zero —
> dopóki nie dotknę indeksu ręką."_

**🎣 Dlaczego to ważne:** w wydaniu #7 pokazaliśmy, że `NONCLUSTERED COLUMNSTORE
INDEX` (NCCI) świetnie żyje obok zwykłego OLTP — ale tylko przy `INSERT`. Dziś
sprawdzamy **realny** `DELETE`/`UPDATE`, czyli to, co się dzieje w codziennej
aplikacji, i trafiamy na coś, czego nie było w dokumentacji, którą czytaliśmy przed
pisaniem tego wydania: **licznik skasowanych wierszy w katalogu systemowym nie jest
licznikiem w czasie rzeczywistym**. Druga część: `sys.sp_query_store_set_hints` —
nowa(ish) procedura, którą **zweryfikowaliśmy, że faktycznie istnieje** w tej
wersji silnika (nie zgadujemy) — pozwala wstrzyknąć `OPTION(RECOMPILE)` do
konkretnego zapytania **bez zmiany ani jednej linii kodu aplikacji**.

Wszystkie liczby poniżej pochodzą z **realnego** uruchomienia kodu z [`code/`](code/)
na `mcr.microsoft.com/mssql/server:2022-latest` (SQL Server 2022 RTM-CU27,
16.0.4295.3, Developer Edition on Linux, Docker) — główny przebieg przez pliki
`.sql` plus dodatkowy, mniejszy test izolujący (opisany niżej), który potwierdził tę
samą, nieoczywistą obserwację drugi raz.

---

## 1️⃣ `DELETE` na NCCI: dane giną natychmiast, metadane — nie

Tabela `dbo.Orders` z wydania #7: klucz klastrowany (`PK_Orders`) + `NCCI_Orders` na
czterech kolumnach, 1 200 000 wierszy historycznych, 300 000 z nich ze
`Status = 3` (Anulowane). Baseline agregacji analitycznej (`GROUP BY CustomerId`,
zero skasowanych wierszy):

```sql
SELECT CustomerId, SUM(Amount) AS Suma, COUNT(*) AS Ile FROM dbo.Orders GROUP BY CustomerId;
-- 40000 grup, Suma=540904500.00, WierszyRazem=1200000
-- lob logical reads 1536, Segment reads 3 skipped 0, CPU 115-120 ms / elapsed 128-133 ms
```

### Prawdziwy `DELETE` dużej porcji — i metadane, które milczą

```sql
DELETE FROM dbo.Orders WHERE Status = 3;   -- 300 000 wierszy, logical reads 906055, CPU ~3000 ms
```

Intuicja (i dokumentacja `sys.column_store_row_groups`) mówi: skasowane wiersze w
skompresowanym rowgroupie nie są usuwane fizycznie, tylko **oznaczane w bitmapie**, a
kolumna `deleted_rows` ma to pokazać. Sprawdziliśmy — **natychmiast po `COMMIT`**:

```
row_group_id  state_description  total_rows   deleted_rows
0             COMPRESSED          1048576      0
1             COMPRESSED            38136      0
2             COMPRESSED           113288      0

COUNT(*) FROM dbo.Orders  -> 900000   (poprawne! 1200000 - 300000)
SUM(total_rows) w rowgroupach -> 1200000,  SUM(deleted_rows) -> 0
```

**`deleted_rows` = 0 wszędzie**, mimo że dane logicznie **już zniknęły** — zapytanie
przez NCCI natychmiast zwraca poprawne 900 000 wierszy (`Index Scan` na
`NCCI_Orders`, `COUNT(*)`/`SUM` zgadzają się z rzeczywistością). Żeby się upewnić, że
to nie jest kwestia opóźnienia, sprawdziliśmy to **dwa razy**: raz na dużej tabeli
(300 000/1 200 000), i raz na osobnej, minimalnej tabeli testowej (5000 wierszy,
usunięto 500) — z `CHECKPOINT`, 15-sekundowym oczekiwaniem **i** kilkukrotnym pełnym
skanem tabeli pomiędzy. Wynik identyczny: `deleted_rows` zostaje na zero.

> 💡 **Co to znaczy w praktyce:** jeśli monitorujesz "zdrowie" columnstore przez
> `sys.column_store_row_groups.deleted_rows` (np. w dashboardzie — "ile % rowgroupu
> jest martwe, czy czas na REBUILD") — **ten numer może drastycznie nie doceniać
> rzeczywistego rozmiaru problemu**, dopóki ktoś nie dotknie indeksu operacją
> konserwacyjną. Index Scan i tak filtruje usunięte wiersze poprawnie (poprawność
> danych nie jest zagrożona) — zagrożone jest tylko **Twoje wyobrażenie o tym, ile
> miejsca faktycznie odzyskasz**.

### Ten sam raport PO `DELETE` — czyta mniej, ale nie proporcjonalnie mniej

```sql
-- 30000 grup, Suma=405679800.00, WierszyRazem=900000  (poprawne)
-- lob logical reads 1106 (vs 1536 baseline), Segment reads 3 skipped 0, CPU 233-235 ms / elapsed 239-242 ms
```

Reads spadły (1536 → 1106), ale **nie proporcjonalnie** do usuniętych 25% wierszy
(oczekiwane ~1152 przy liniowej skali — więc spadek jest nawet trochę większy), a CPU
i elapsed **wzrosły** względem baseline. Nie nadinterpretujemy tego pomiaru — licznik
`lob logical reads` zależy od stanu cache'a i nie jest tu monotoniczny; jedyny
twardy fakt to: **segmenty do przeczytania wciąż te same 3**, bez żadnej eliminacji —
martwe wiersze fizycznie tam siedzą i są czytane (i dekompresowane) razem z żywymi.

## 2️⃣ `UPDATE` na NCCI = `DELETE` starej wersji + `INSERT` nowej (dowód, nie opowieść)

```sql
UPDATE dbo.Orders SET Status = 1 WHERE Status = 0 AND CustomerId BETWEEN 1 AND 2000;
-- 15000 wierszy zaktualizowanych, logical reads 50302, CPU 530-536 ms
```

Natychmiast po `COMMIT`, stan rowgroupów:

```
row_group_id  state_description  total_rows   deleted_rows
0             COMPRESSED          1048576      0
1             COMPRESSED            38136      0
2             COMPRESSED           113288      0
3             OPEN                  15000      NULL   <- NOWY, dokladnie 15000 = @@ROWCOUNT
```

To jest **bezpośredni, policzalny dowód** na "UPDATE to DELETE+INSERT": nowy
rowgroup **3** (`OPEN` = delta store) pojawia się **od razu**, z liczbą wierszy
**identyczną** co liczba zaktualizowanych (`@@ROWCOUNT = 15000`) — to jest strona
`INSERT`. Strona `DELETE` (stare wersje tych samych 15 000 wierszy w rowgroupach
0/1/2) jest — jak w punkcie 1 — logicznie usunięta (zapytania jej nie widzą), ale
**niewidoczna w `deleted_rows`** (wciąż 0/0/0) do czasu dotknięcia indeksu.

## 3️⃣ `REORGANIZE` budzi licznik, ale nie oddaje miejsca. `REBUILD` — tak

```sql
ALTER INDEX NCCI_Orders ON dbo.Orders REORGANIZE WITH (COMPRESS_ALL_ROW_GROUPS = ON);
```

| | Rozmiar `NCCI_Orders` (used/reserved) | `PK_Orders` (rowstore) |
|---|---:|---:|
| Przed REORGANIZE | 17,58 MB / 17,77 MB | 39,50 MB |
| Po REORGANIZE | **13,80 MB** / 14,09 MB | 39,50 MB (bez zmian) |
| Po REBUILD | **6,63 MB** / 6,76 MB | 39,50 MB (bez zmian) |

Stan rowgroupów **dopiero teraz** (po REORGANIZE) ujawnia prawdę:

```
0  COMPRESSED  total=1048576  deleted=275610   <- NAJWIEKSZY rowgroup, 26.3% martwych - NIE scalony, NIE skompaktowany
1  TOMBSTONE   total=38136    deleted=9568      (stary, zastapiony)
2  TOMBSTONE   total=113288   deleted=29822     (stary, zastapiony)
3  TOMBSTONE   total=15000    deleted=NULL      (byly delta store, teraz tez tombstone)
4  COMPRESSED  total=15000    deleted=0         <- skompresowany delta store (byl rowgroup 3)
5  COMPRESSED  total=112034   deleted=0         <- SCALENIE 1+2: (38136-9568)+(113288-29822) = 112034 dokladnie
```

`REORGANIZE` zrobiło dwie rzeczy: **ujawniło** prawdziwą liczbę martwych wierszy
(275 610 w samym rowgroupie 0!) **i** scaliło dwa małe rowgroupy w jeden, **przy
okazji wyrzucając z nich martwe wiersze** (112 034 = suma żywych). Ale **nie
dotknęło** największego, już w pełni zapełnionego rowgroupu 0 — tam 275 610 martwych
wierszy (26,3% jego zawartości!) wciąż fizycznie zajmuje miejsce. Druga `REORGANIZE`
tego nie zmienia (sprawdzone na mniejszej tabeli testowej: powtórzenie dało identyczny
wynik — zero dodatkowej kompakcji).

```sql
ALTER INDEX NCCI_Orders ON dbo.Orders REBUILD;
```

Dopiero to daje **pełny** reclaim: jeden świeży rowgroup, `total_rows = 900000`
(dokładnie liczba żywych wierszy), `deleted_rows = 0`, rozmiar indeksu **6,63 MB** —
62% mniej niż oryginalne 17,58 MB, 52% mniej niż po samym REORGANIZE. Zapytanie
analityczne po REBUILD: **1 segment** do przeczytania (było 3), CPU **78 ms**
(najniższe ze wszystkich etapów, łącznie z baseline).

> ⚠️ **PK_Orders (zwykły rowstore) pozostaje na 39,5 MB przez cały ten proces** —
> `REORGANIZE`/`REBUILD` columnstore nie dotyka klucza klastrowanego. Ghost cleanup
> tych samych 315 000 "martwych" wierszy w B-drzewie to **osobny, asynchroniczny
> mechanizm**, który tu nie badaliśmy (nie zmierzyliśmy, kiedy/czy się odpalił).

---

## 4️⃣ `sp_query_store_set_hints`: `OPTION(RECOMPILE)` bez dotykania kodu

Najpierw fakt, który trzeba **zweryfikować**, nie zgadnąć: na tym silniku
(16.0.4295.3) `sys.sp_query_store_set_hints` **istnieje** —
`SELECT * FROM sys.all_objects WHERE name = 'sp_query_store_set_hints'` zwraca wiersz
typu `EXTENDED_STORED_PROCEDURE`, a wywołanie z realnym `@query_id` kończy się
sukcesem (sprawdzone próbą z nieistniejącym ID — błąd 12402 "query not found",
czyli procedura **poprawnie parsuje parametry**, nie ginie na "nieznana procedura").

### Scenariusz: klasyczny parameter sniffing, bez zmiany procedury

`dbo.Events` — 200 000 wierszy, skośny rozkład: `TenantId = 1` ma 190 000 wierszy
(95%), 100 innych tenantów ma po 100 wierszy. Indeks nieklastrowany na `TenantId`.
Procedura:

```sql
CREATE PROCEDURE dbo.GetEventsByTenant @TenantId int AS
    SELECT EventId, TenantId, Payload FROM dbo.Events WHERE TenantId = @TenantId;
```

```sql
EXEC dbo.GetEventsByTenant @TenantId = 1;   -- kompiluje i cachuje plan (190 000 wierszy)
-- Table 'Events'. logical reads 3141
EXEC dbo.GetEventsByTenant @TenantId = 2;   -- DOSTAJE TEN SAM plan z cache (100 wierszy)
-- Table 'Events'. logical reads 3141   <- IDENTYCZNE! Zly plan, zle dopasowany
```

Klasyka: drugie wywołanie powinno czytać **o rząd wielkości mniej**, ale dostaje plan
wycechowany pod 95% selektywność. W poprzednich wydaniach (#2/#3) lekiem było
`OPTION (RECOMPILE)` **wpisane w kod proceduy**. Dziś: zero zmian w
`dbo.GetEventsByTenant`.

```sql
EXEC sys.sp_query_store_set_hints @query_id = 6, @query_hints = N'OPTION(RECOMPILE)';
EXEC sys.sp_recompile 'dbo.GetEventsByTenant';   -- hint dziala od NASTEPNEJ kompilacji
```

Prawdziwy wynik — `sys.query_store_query_hints` potwierdza przyjęcie hintu:

```
query_hint_id  query_id  query_hint_text      source_desc  last_query_hint_failure_reason_desc
1              6         OPTION(RECOMPILE)     User         NONE
```

### Po hincie: każde wywołanie dostaje WŁASNY plan

```sql
EXEC dbo.GetEventsByTenant @TenantId = 1;   -- Table 'Events'. logical reads 3141 (bez zmian - to i tak byl dobry plan)
EXEC dbo.GetEventsByTenant @TenantId = 2;   -- Table 'Events'. logical reads 318  <- NOWY plan, 10x mniej reads!
```

`sys.query_store_plan` pokazuje teraz **dwa różne plany** dla tego samego
`query_id = 6`: `plan_id = 6` (stary, nadal używany dla `TenantId = 1` — bo to wciąż
właściwy plan dla 95% selektywności) i **nowy** `plan_id = 15`, skompilowany
specjalnie dla `TenantId = 2`. To jest dokładnie zachowanie `OPTION(RECOMPILE)` — ale
ustawione **raz, po stronie serwera**, bez wdrożenia ani jednej linii zmiany w
aplikacji czy w samej procedurze.

> 💡 **Dla .NET-owca:** to realna przewaga nad hardkodowaniem `OPTION (RECOMPILE)` w
> `.sql`/EF raw query — możesz to włączyć/wyłączyć **produkcyjnie, bez deployu**, dla
> konkretnego zapytania, które akurat zaczęło się źle zachowywać (np. po migracji
> danych, która zmieniła rozkład). `sp_query_store_clear_hints` usuwa hint tak samo
> łatwo.

---

## 🕳️ Wątek wciąż otwarty: Parameter Sensitive Plan (PSP) — sprawdzone, nie rozwiązane

W #3 PSP nie zadziałało i nie wiedzieliśmy, dlaczego. Dziś zweryfikowaliśmy
**konkretne, realne liczby** na tym kontenerze (nie zgadujemy):

```sql
SELECT compatibility_level FROM sys.databases WHERE name = 'model';        -- 160
SELECT name, value FROM sys.database_scoped_configurations
WHERE name = 'PARAMETER_SENSITIVE_PLAN_OPTIMIZATION';                      -- 1 (ON)
```

Obydwa wymagane warunki (compatibility level ≥ 160, PSPO włączone) są **spełnione
domyślnie** na tym silniku — więc to **nie jest** przyczyna, dla której PSP nie
zadziałało w #3. (Ciekawostka: `DATABASEPROPERTYEX(db, 'IsParameterSensitivityPlanOptimizationEnabled')`
zwraca `NULL` — ta konkretna nazwa właściwości nie jest tu rozpoznawana; właściwy
sposób sprawdzenia to `sys.database_scoped_configurations`, nie
`DATABASEPROPERTYEX`). Prawdziwa przyczyna niezadziałania PSP w konkretnym
scenariuszu z #3 **nadal nie jest zbadana** — nie zdążyliśmy zrobić pełnego nowego
repro w tym wydaniu. Zostaje na następny raz.

---

## 🧾 Ściąga na dziś

| Pojęcie | Jedno zdanie |
|---|---|
| `sys.column_store_row_groups.deleted_rows` | **NIE jest licznikiem na żywo** — po realnym `DELETE`/`UPDATE` zostaje na 0, zweryfikowane nawet po `CHECKPOINT` + 15 s + pełnych skanach |
| Dlaczego zapytania mimo to są poprawne | NCCI poprawnie filtruje usunięte wiersze przy skanie — poprawność danych nie jest zagrożona, tylko ta jedna metadana |
| `UPDATE` na NCCI | fizyczny dowód: nowy rowgroup `OPEN` pojawia się z `total_rows` == liczbie zaktualizowanych wierszy (DELETE+INSERT) |
| `ALTER INDEX ... REORGANIZE` | **ujawnia** prawdziwy `deleted_rows` i scala/kompaktuje MAŁE rowgroupy — ale NIE dotyka już pełnych, dużych rowgroupów |
| `ALTER INDEX ... REBUILD` | jedyny sposób na **pełny** reclaim miejsca — u nas: 17,58 MB → 6,63 MB (-62%) |
| Rowstore (`PK_Orders`) podczas tego wszystkiego | rozmiar bez zmian — ghost cleanup klucza klastrowanego to osobny, nie badany tu mechanizm |
| `sys.sp_query_store_set_hints` | **istnieje** w SQL Server 2022 RTM-CU27 (zweryfikowane) — wstrzykuje hint (np. `OPTION(RECOMPILE)`) do konkretnego `query_id` w Query Store |
| Kiedy hint zaczyna działać | od NASTĘPNEJ kompilacji — trzeba wymusić `sp_recompile` (albo czekać na naturalną eksmisję z cache) |
| Efekt u nas | 3141 vs 3141 logical reads (przed hintem, zły reuse) → 3141 vs **318** (po hincie, własny plan per parametr) |
| PSP w SQL 2022 (ten kontener) | compat level 160 ✅, `PARAMETER_SENSITIVE_PLAN_OPTIMIZATION=1` ✅ — oba warunki spełnione, przyczyna niezadziałania z #3 wciąż NIEZNANA |

**Pełny, uruchamialny kod + komendy:** [`code/README.md`](code/README.md).

**Co dalej:** nowe repro PSP (inny kształt zapytania/predykatu — może problem był w
samym zapytaniu z #3, nie w konfiguracji bazy), `sp_query_store_clear_hints` i co się
dzieje z hintem po `OPTIMIZE FOR UNKNOWN`/force plan jednocześnie, fizyczny ghost
cleanup `PK_Orders` po dużym `DELETE` na tabeli z NCCI.

---

## ✅ Status weryfikacji

Kod uruchomiony realnie: kontener `mcr.microsoft.com/mssql/server:2022-latest` (SQL
Server 2022 RTM-CU27, 16.0.4295.3), skrypty `01`–`15` wykonane ręcznie przez
`docker exec ... sqlcmd`, **pełna sekwencja 01→10 (temat NCCI) przepuszczona dwa razy
od zera** (druga, "brudna" eksploracyjna próba + czysty przebieg przez pliki) —
identyczne liczby w obu. Dodatkowo kluczowe, nieoczywiste zachowanie (`deleted_rows`
zostaje na zero) **potwierdzone osobno** na niezależnej, minimalnej tabeli testowej
(5000 wierszy, 500 skasowanych) z `CHECKPOINT` i 15-sekundowym oczekiwaniem między
pomiarami — nie jest to artefakt jednego przebiegu. Temat Query Store hints (`11`–`14`)
wykonany jeden raz w pełni, z potwierdzeniem w `sys.query_store_query_hints` i
`sys.query_store_plan` (dwa różne `plan_id` dla jednego `query_id` po hincie).

Uczciwe uwagi:

1. `run-demo.sh` jako całość **nie został odpalony** (`chmod +x`/uruchomienie `.sh`
   odrzucone przez uprawnienia sandboksa — ten sam, znany problem co w poprzednich
   wydaniach) — wszystkie kroki wykonano ręcznie, `docker exec ... sqlcmd -i`, dwa
   razy dla tematu 1, raz dla tematu 2.
2. **Niezweryfikowane:** dokładny mechanizm/harmonogram tego, KIEDY i CZYM
   `sys.column_store_row_groups.deleted_rows` faktycznie się odświeża w tle (poza
   tym, że `REORGANIZE`/`REBUILD` go odświeżają) — nie znaleźliśmy innego triggera
   (próbowaliśmy: `CHECKPOINT`, 15 s oczekiwania, pełne skany tabeli bazowej i NCCI —
   żaden nie pomógł).
3. **Niezweryfikowane:** ghost cleanup wierszy usuniętych z `PK_Orders` (rowstore) —
   nie sprawdziliśmy, czy/kiedy się odpalił, rozmiar `PK_Orders` pozostał 39,5 MB przez
   cały przebieg.
4. **Niezweryfikowane:** `sp_query_store_clear_hints` (istnienie sprawdzone, działanie
   nie przetestowane), zachowanie hintu po `sp_query_store_force_plan` na tym samym
   `query_id`, zachowanie przy więcej niż dwóch różnych "kształtach" parametru.
5. **PSP (Parameter Sensitive Plan) wciąż nierozwiązane** — sprawdziliśmy realnie
   `compatibility_level = 160` i `PARAMETER_SENSITIVE_PLAN_OPTIMIZATION = 1` (obydwa
   wymagane warunki spełnione), ale nie zrobiliśmy nowego pełnego repro w tym
   wydaniu — przyczyna niezadziałania w scenariuszu z #3 zostaje otwarta.

---

<div align="center">

[← wróć do wydania #11 (wszystkie rubryki)](../README.md) · [spis wydań](../../README.md)

</div>
