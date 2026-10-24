<div align="center">

# 📰 TECH PRASÓWKA
### Wydanie #7 — 29 września 2026

![SQL Server](https://img.shields.io/badge/SQL_Server-CC2927?style=for-the-badge&logo=microsoftsqlserver&logoColor=white)
![Poziom](https://img.shields.io/badge/poziom-zaawansowany-orange?style=for-the-badge)
![Zweryfikowane](https://img.shields.io/badge/kod-uruchomiony_2x_na_SQL_Server_2022_CU27-brightgreen?style=for-the-badge)

## Columnstore w OLTP i wyścig, którego SERIALIZABLE nie rozwiązuje elegancko

</div>

---

> _"SERIALIZABLE brzmi jak najsilniejsza gwarancja, jaką możesz dostać. I faktycznie
> jest — tylko że czasem realizuje ją przez zabicie jednej z Twoich transakcji."_

**🎣 Dlaczego to ważne:** dziś dwie rzeczy, które brzmią jak ciekawostki z
dokumentacji, dopóki nie zderzysz się z nimi na produkcji.

1. **Columnstore na tabeli OLTP** — do tej pory (wydanie #4) columnstore było
   osobną tabelą tylko do raportów. Dziś: **ten sam** stół, który obsługuje zwykłe
   `INSERT`/punktowe `SELECT`, ma **dodatkowo** indeks kolumnowy do analityki w czasie
   rzeczywistym. Haczyk: nowe wiersze nie trafiają od razu do skompresowanej,
   szybkiej postaci — lądują w **delta store**, zwykłym B-drzewie, dopóki ktoś (Ty
   albo tuple mover w tle) ich nie skompresuje.
2. **SERIALIZABLE kontra `sp_getapplock`** — klasyczny generator "następny numer
   faktury" (`MAX+1`). Pod `READ COMMITTED` dostajesz **realny duplikat**.
   Podniesienie izolacji do `SERIALIZABLE` **też nie daje gładkiej serializacji** —
   dostajesz **deadlock 1205**. Poprawność jest zachowana, ale kosztem wyjątku, który
   trzeba złapać i ponowić. `sp_getapplock` rozwiązuje to bez błędu w ogóle.

Wszystkie liczby i wydruki poniżej pochodzą z **realnego, dwukrotnie powtórzonego**
uruchomienia kodu z [`code/`](code/) na `mcr.microsoft.com/mssql/server:2022-latest`
(SQL Server 2022 RTM-CU27, 16.0.4295.3, Developer Edition on Linux, Docker) —
oba przebiegi dały identyczne wyniki.

---

## 1️⃣ Nonclustered columnstore: analityka obok OLTP, bez kopiowania danych

W wydaniu #4 columnstore był **osobną** tabelą faktów — dane trafiały tam hurtowo, raz.
Ale co, jeśli chcesz agregować dane z tabeli, która **jednocześnie** obsługuje zwykły
ruch aplikacji (nowe zamówienia, płatności, punktowe odczyty)? Nie musisz kopiować
danych do osobnego magazynu — SQL Server pozwala dołożyć `NONCLUSTERED COLUMNSTORE
INDEX` (NCCI) **obok** zwykłego klucza klastrowanego. Tabela `dbo.Orders` (klucz
klastrowany na `OrderId`, 1 200 000 historycznych wierszy) dostaje drugi indeks:

```sql
CREATE NONCLUSTERED COLUMNSTORE INDEX NCCI_Orders
    ON dbo.Orders (CustomerId, OrderDate, Status, Amount);
```

To nie jest przełącznik "albo/albo". Baza sama wybiera, którego indeksu użyć, zależnie
od zapytania:

| Zapytanie | Wybrany plan | Logical reads / lob reads | CPU / elapsed |
|---|---|---:|---:|
| `WHERE OrderId = 600000` (punktowy odczyt OLTP) | **Clustered Index Seek** (PK) | 3 | ~0 ms |
| `GROUP BY CustomerId` (raport, plan automatyczny) | **Columnstore Index Scan** (NCCI) | 1536 (lob) | **99 ms** / 106 ms |
| `GROUP BY CustomerId` wymuszony hintem na PK | Clustered Index Scan (rowstore) | 5098 | **278 ms** / 153 ms |

Optymalizator **sam** dostrzegł, że NCCI jest tańszy do agregacji (mniej danych do
przeczytania — tylko 4 kolumny zamiast całego wiersza, skompresowane) i wybrał go bez
żadnego hintu. Punktowy odczyt po kluczu nadal korzysta ze zwykłego B-drzewa — NCCI
w ogóle się do niego nie miesza. **To jest sedno "operational analytics"**: ta sama
tabela, dwa różne silniki dostępu, każdy używany tam, gdzie ma sens.

> 💡 **Dla .NET-owca:** to nie wymaga zmiany ani jednej linii aplikacji. EF Core czy
> Dapper strzelające `WHERE OrderId = @id` dalej dostaną seek po PK; osobny raport
> `GROUP BY CustomerId` (BI, dashboard, cron) automatycznie poleci przez NCCI. Nie ma
> potrzeby pisać dwóch osobnych zapytań ani `WITH (INDEX(...))` — chyba że chcesz to
> świadomie wymusić.

### 🧨 Haczyk: nowe wiersze nie są od razu skompresowane

Bulk load 1,2 mln wierszy z `01-setup-oltp.sql` **poprzedził** budowę NCCI — dlatego
`CREATE INDEX` od razu zbudował dane w postaci **skompresowanej**:

```
row_group_id  state_description  total_rows  deleted_rows
0             COMPRESSED         1048576     0
1             COMPRESSED         38136       0
2             COMPRESSED         113288      0
```

(Ciekawostka, której nie zbadaliśmy do końca: build podzielił 1 200 000 wierszy na
**trzy** rowgroupy, nie dwa — mimo że maksymalny rozmiar rowgroupu to 1 048 576, a
kontener miał tylko 2 CPU wg `sys.dm_os_sys_info`. Związku z liczbą wątków budowy nie
sprawdzaliśmy.)

Ale to nie jest scenariusz OLTP. Symulujemy prawdziwy ruch: pięć małych partii po 2000
wierszy, jak zwykłe zamówienia wpadające przez aplikację przez cały dzień
(`04-trickle-insert.sql`). Po nich stan rowgroupów:

```
row_group_id  state_description  total_rows  deleted_rows
0             COMPRESSED         1048576     0
1             COMPRESSED         38136       0
2             COMPRESSED         113288      0
3             OPEN               10000       NULL          <- NOWY
```

Nowy rowgroup **3** ma stan `OPEN` — to jest **delta store**: zwykłe, nieskompresowane
B-drzewo, w które SQL Server ładuje świeże wiersze, dopóki nie uzbiera ich
**1 048 576** (albo ktoś ręcznie nie każe skompresować). Dopiero wtedy tuple mover w
tle (albo Ty) zamienia go w prawdziwy, skompresowany segment kolumnowy.

Dobra wiadomość: zapytania **od razu** widzą te wiersze poprawnie — NCCI Scan czyta i
skompresowane rowgroupy, i delta store, transparentnie:

```sql
SELECT CustomerId, SUM(Amount), COUNT(*) FROM dbo.Orders GROUP BY CustomerId;
-- 40000 grup, Suma=542615350.00, WierszyRazem=1210000 (obejmuje tez 10000 z delta store)
-- logical reads 41 (delta store), lob logical reads 1106 (3 compressed rowgroupy), CPU 119 ms
```

A jeśli zapytanie trafia **wyłącznie** w świeże dane, dzieje się coś jeszcze
ciekawszego — **eliminacja segmentów** (segment elimination, znana z #4) pozwala
optymalizatorowi **całkowicie pominąć** wszystkie trzy skompresowane rowgroupy, bo ich
zakresy dat (zapisane jako min/max w metadanych segmentu) nie pokrywają się z
filtrem:

```sql
SELECT COUNT(*), SUM(Amount) FROM dbo.Orders WHERE OrderDate = '2026-09-29';
-- Segment reads 0, segment skipped 3 (!)   <- wszystkie compressed rowgroupy pominiete
-- logical reads 41 (tylko delta store), CPU 5 ms (vs 119 ms wyzej)
```

### 🛠️ Kiedy Ty sam wymuszasz kompresję: `REORGANIZE`

Zostawiony sam sobie delta store będzie rósł z każdą kolejną partią — dopóki nie
osiągnie progu 1 048 576 wierszy, zapytania analityczne będą musiały przedzierać się
przez coraz większe, nieskompresowane B-drzewo (drogie w porównaniu do segmentu
kolumnowego). Jeśli chcesz to skompresować **od razu**, a nie czekać na tuple mover:

```sql
ALTER INDEX NCCI_Orders ON dbo.Orders REORGANIZE WITH (COMPRESS_ALL_ROW_GROUPS = ON);
```

Prawdziwy wynik — i tu jest druga niespodzianka:

```
PRZED:  0(COMPRESSED,1048576)  1(COMPRESSED,38136)  2(COMPRESSED,113288)  3(OPEN,10000)
PO:     0(COMPRESSED,1048576)
        1(TOMBSTONE,38136)  2(TOMBSTONE,113288)  3(TOMBSTONE,10000)   <- stare, "martwe"
        4(COMPRESSED,10000)                                          <- delta store skompresowany
        5(COMPRESSED,151424)                                         <- 38136 + 113288 SCALONE
```

`REORGANIZE` nie tylko skompresował delta store (nowy rowgroup 4) — **scalił też** dwa
małe, już skompresowane rowgroupy (1 i 2) w jeden większy (5: 38136 + 113288 =
**151 424**, dokładnie). Stare rowgroupy nie znikają natychmiast — dostają status
`TOMBSTONE` i są fizycznie sprzątane w tle później (sprawdziliśmy to ręcznie drugim,
zwykłym `REORGANIZE` — stare tombstony zniknęły z widoku, pojawiły się nowe po kolejnym
scaleniu; mechanizmu i harmonogramu czyszczenia nie badaliśmy głębiej). Efekt: mniej,
gęstszych rowgroupów = tańsze skanowanie przy kolejnych raportach.

> ⚠️ **Zastrzeżenie:** `REORGANIZE WITH (COMPRESS_ALL_ROW_GROUPS = ON)` to operacja
> online, ale i tak generuje realną pracę I/O i CPU na produkcyjnym serwerze — planuj
> ją tak jak inne zadania utrzymaniowe (poza godzinami szczytu albo w małych krokach).
> Rozmiar końcowy: `PK_Orders` (rowstore, wszystkie kolumny) **39,83 MB**;
> `NCCI_Orders` (4 z 5 kolumn, skompresowany) **10,1–10,5 MB** — mierzone dwukrotnie,
> lekka różnica przez tombstony jeszcze nie posprzątane w drugim pomiarze.

---

## 2️⃣ SERIALIZABLE nie jest "magicznym przełącznikiem" na poprawność

Klasyczny problem: generator kolejnego numeru faktury dla danego najemcy (tenant).
Pozornie proste zapytanie:

```sql
BEGIN TRAN;
SELECT @next = MAX(InvoiceNo) + 1 FROM dbo.Invoices WHERE TenantId = @tenant;
-- (tu realna logika biznesowa: liczenie podatku, generowanie PDF-a, ...)
INSERT dbo.Invoices (TenantId, InvoiceNo) VALUES (@tenant, @next);
COMMIT;
```

### Pod `READ COMMITTED` (domyślny poziom): realny duplikat

Sesja A liczy `@next = 2`, robi coś przez 3 sekundy (symulujemy `WAITFOR DELAY`).
Sesja B startuje sekundę później, **też** liczy `@next = 2` — bo zwykły `SELECT` pod
`READ COMMITTED` nie trzyma żadnej blokady po odczycie. Prawdziwy wynik:

```
A: policzylem nastepny numer = 2, czekam 3 s...
B: policzylem nastepny numer = 2, czekam 3 s...
A: COMMIT - wstawilem InvoiceNo = 2
B: COMMIT - wstawilem InvoiceNo = 2
```

```
InvoiceId  TenantId  InvoiceNo  CreatedAt
1          1         1          2026-09-29 02:32:08.506
2          1         2          2026-09-29 02:32:14.299
3          1         2          2026-09-29 02:32:15.398   <- DUPLIKAT
```

Dwie faktury z tym samym numerem. W realnym systemie księgowym to nie jest "bug do
poprawki później" — to złamana integralność danych.

### Pod `SERIALIZABLE`: poprawność jest zachowana, ale przez deadlock

Intuicja podpowiada: `SERIALIZABLE` to najsilniejszy poziom izolacji, więc powinien to
naprawić "grzecznie" — kolejkując transakcje. Sprawdziliśmy to empirycznie:

```sql
SET TRANSACTION ISOLATION LEVEL SERIALIZABLE;
BEGIN TRAN;
SELECT @next = MAX(InvoiceNo) + 1 FROM dbo.Invoices WHERE TenantId = @tenant;
...
```

Podglądając `sys.dm_tran_locks` **w trakcie** trwania obu transakcji (zanim któraś
zdąży zrobić `INSERT`), zobaczyliśmy coś, czego nie było widać "z zewnątrz":

```
Spid  Typ  Zasob                    Tryb      Status
70    KEY  (ffffffffffff)           RangeS-S  GRANT
70    KEY  (0ca2219ccd86)           RangeS-S  GRANT
72    KEY  (ffffffffffff)           RangeS-S  GRANT   <- TE SAME zasoby co spid 70
72    KEY  (0ca2219ccd86)           RangeS-S  GRANT
```

**Obie** sesje dostały blokadę zakresową (`RangeS-S` — "range shared", chroni przed
wstawieniem nowego wiersza w danym zakresie kluczy przez kogoś innego) na **tych
samych** kluczach, obie od razu, bez czekania. To dlatego, że `RangeS-S` jest
**kompatybilny sam ze sobą** — dwie transakcje mogą jednocześnie *czytać* ten sam
zakres. Problem pojawia się dopiero przy `INSERT`: żeby wstawić nowy wiersz w ten
zakres, transakcja potrzebuje blokady insercji, która **koliduje** z `RangeS-S`
drugiej, wciąż aktywnej transakcji. Obie próbują wstawić w ten sam zakres, obie czekają
na siebie nawzajem:

```
B: BLAD 1205 - Transaction (Process ID 72) was deadlocked on lock resources with
   another process and has been chosen as the deadlock victim. Rerun the transaction.
A: COMMIT - wstawilem InvoiceNo = 2
```

```
InvoiceId  TenantId  InvoiceNo  CreatedAt
1          1         1          2026-09-29 02:32:20.817
2          1         2          2026-09-29 02:32:27.166     <- TYLKO JEDEN wiersz, bez duplikatu
```

Poprawność jest w porządku — nie ma duplikatu. Ale `SERIALIZABLE` "naprawił" to w
najbardziej brutalny możliwy sposób: **zabijając jedną transakcję błędem 1205**, tym
samym, który widzieliśmy w #4 przy klasycznym deadlocku dwóch przelewów. Aplikacja
**musi** mieć logikę retry na 1205, inaczej użytkownik dostanie wyjątek zamiast
faktury. To kosztowne (cała transakcja od nowa, łącznie z liczeniem podatku i PDF-em) i
nieprzewidywalne w czasie.

> 💡 **Dlaczego to ważne:** `SERIALIZABLE` daje gwarancję **poprawności końcowego
> stanu danych**, a nie gwarancję **braku błędów w trakcie**. To fundamentalna różnica
> względem tego, czego często intuicyjnie oczekuje się po "najsilniejszym poziomie
> izolacji".

### `sp_getapplock`: ten sam problem, zero błędów

`sp_getapplock` to **nazwany mutex na poziomie aplikacji** — nie jest powiązany z
żadnym konkretnym wierszem, indeksem ani tabelą. To Ty decydujesz, co nazwa oznacza.
Tu: "generowanie numeru faktury dla tenanta 1" to jeden zasób, niezależnie od tego, po
jakiej kolumnie/indeksie faktycznie szukasz `MAX`:

```sql
BEGIN TRAN;
EXEC sp_getapplock
    @Resource = 'InvoiceGen:Tenant:1',
    @LockMode = 'Exclusive',
    @LockOwner = 'Transaction',   -- zwalnia sie automatycznie przy COMMIT/ROLLBACK
    @LockTimeout = 15000;
SELECT @next = MAX(InvoiceNo) + 1 FROM dbo.Invoices WHERE TenantId = 1;
...
INSERT dbo.Invoices (TenantId, InvoiceNo) VALUES (1, @next);
COMMIT;
```

Zwykły `READ COMMITTED` wystarczy — `sp_getapplock` nie potrzebuje `SERIALIZABLE`.
Prawdziwy wynik:

```
A: sp_getapplock wynik = 0 (od razu, bez czekania)
A: policzylem nastepny numer = 2, czekam 3 s...
B: sp_getapplock wynik = 1, czekalem 1919 ms na blokade      <- CZEKAL, nie zginal
A: COMMIT - wstawilem InvoiceNo = 2
B: policzylem nastepny numer = 3 (widze juz insert od A)     <- policzyl PO zwolnieniu
B: COMMIT - wstawilem InvoiceNo = 3
```

```
InvoiceId  TenantId  InvoiceNo
1          1         1
2          1         2
3          1         3            <- brak duplikatu, brak bledu 1205
```

Sesja B **zablokowała się grzecznie** na `sp_getapplock` (`@lockResult = 1` oznacza
"grant po oczekiwaniu", `0` = "grant od razu", wartości ujemne = timeout/błąd — patrz
dokumentacja `sp_getapplock`), poczekała, aż A zrobi `COMMIT` (co automatycznie
zwalnia lock, bo `@LockOwner = 'Transaction'`), i dopiero wtedy policzyła `MAX` **na
nowo** — widząc już wiersz od A. Żadnego wyjątku, żadnego retry po stronie aplikacji.

### 🧾 Dlaczego `sp_getapplock`, a nie tylko wyższa izolacja

| | `READ COMMITTED` | `SERIALIZABLE` | `sp_getapplock` |
|---|---|---|---|
| Duplikat numeru faktury | ✅ (realny, zmierzony) | ❌ (poprawność OK) | ❌ (poprawność OK) |
| Sposób ochrony | brak | blokada zakresowa na indeksie | nazwany mutex aplikacyjny |
| Efekt dla drugiej sesji | brak blokowania (stąd wyścig) | **deadlock 1205**, aplikacja musi retry | **blokuje się i czeka**, zero błędu |
| Działa bez odpowiedniego indeksu na predykacie | — | nie (musi być zakres do zablokowania) | tak (nazwa zasobu jest dowolna) |
| Działa dla logiki rozproszonej na wiele tabel | nie dotyczy | nie wprost (trzeba blokować każdy zakres osobno) | tak — jeden nazwany zasób obejmuje całą logikę |

`sp_getapplock` jest szczególnie przydatny, gdy niezmiennik, który chronisz, **nie
mapuje się na jeden zakres jednego indeksu** — np. logika rozciąga się na kilka tabel,
albo "następna wartość" nie odpowiada żadnemu fizycznemu wierszowi, który dałoby się z
góry zablokować. Cena: to blokada **kooperacyjna** — chroni tylko kod, który
świadomie po nią sięga. Ktoś, kto wstawi wiersz do `Invoices` z pominięciem
`sp_getapplock`, przejdzie bez przeszkód.

---

## 🧾 Ściąga na dziś

| Pojęcie | Jedno zdanie |
|---|---|
| `NONCLUSTERED COLUMNSTORE INDEX` (NCCI) | indeks kolumnowy **obok** zwykłego OLTP-owego — optymalizator wybiera sam, zależnie od zapytania |
| Delta store | nowe, małe `INSERT`-y lądują w nieskompresowanym B-drzewie (`state = OPEN`), nie od razu w segmencie kolumnowym |
| `sys.column_store_row_groups` | pokazuje realny stan: `COMPRESSED` / `OPEN` / `CLOSED` / `TOMBSTONE` |
| Eliminacja segmentów + delta store | zapytanie trafiające tylko w świeże dane może pominąć WSZYSTKIE compressed rowgroupy |
| `REORGANIZE WITH (COMPRESS_ALL_ROW_GROUPS = ON)` | wymusza kompresję delta store I scala małe compressed rowgroupy w większe |
| `RangeS-S` | blokada zakresowa przy `SERIALIZABLE` — kompatybilna z inną `RangeS-S`, ale nie z `INSERT` w ten sam zakres |
| `SERIALIZABLE` a duplikat MAX+1 | naprawia poprawność, ale przez **deadlock 1205**, nie przez gładkie kolejkowanie |
| `sp_getapplock` | nazwany mutex aplikacyjny — blokuje się i czeka, zero błędu, działa nawet pod `READ COMMITTED` |
| `@LockOwner = 'Transaction'` | applock zwalnia się automatycznie przy `COMMIT`/`ROLLBACK` — nie trzeba pamiętać o `sp_releaseapplock` |

**Pełny, uruchamialny kod + komendy:** [`code/README.md`](code/README.md).

**Co dalej:** `UPDATE`/`DELETE` na tabeli z nonclustered columnstore (jak wygląda
usuwanie w segmencie kolumnowym — bitmapa skasowanych wierszy, nie fizyczne
usunięcie), Query Store hints (`sp_query_store_set_hints`), Parameter Sensitive Plan
optimization (temat z #3, który nam wtedy nie zadziałał — wart ponowienia w innym
scenariuszu).

---

## ✅ Status weryfikacji

Kod uruchomiony realnie, **dwukrotnie od zera**: kontener
`mcr.microsoft.com/mssql/server:2022-latest` (SQL Server 2022 RTM-CU27, 16.0.4295.3),
skrypty `01`–`11` wykonane ręcznie przez `docker exec ... sqlcmd` (sesje A/B jako dwa
równoległe procesy, jeden w tle przez `docker exec -d`). Oba przebiegi dały
**identyczne** liczby rowgroupów, logical reads i zachowanie (duplikat/deadlock/brak
błędu) — jedynie czasy CPU/elapsed w ms wahały się nieznacznie (np. 97 vs 99 ms).

Uczciwe uwagi:

1. `run-demo.sh` jako całość **nie został odpalony** (uruchomienie pliku `.sh`
   odrzucone przez uprawnienia sandboksa) — wszystkie kroki wykonano ręcznie, dwa
   razy, z tym samym wynikiem.
2. Kontener miał tylko **2 CPU** (`sys.dm_os_sys_info`) — dlaczego bulk build NCCI dał
   3 rowgroupy zamiast 2 (1 200 000 / 1 048 576 ≈ 1,14) nie zbadaliśmy.
3. Fizyczne czyszczenie rowgroupów `TOMBSTONE` w tle zaobserwowane ręcznie (poza
   plikami `.sql` w repo) — harmonogram/mechanizm nie zbadany.
4. **Niezweryfikowane:** `UPDATE`/`DELETE` na tabeli z NCCI, `sp_getapplock` z
   `@LockOwner = 'Session'` i jawny `sp_releaseapplock`, zachowanie przy więcej niż
   dwóch równoległych sesjach generatora faktur, formalna gwarancja kolejności
   blokad `RangeS-S` przy wielu kluczach jednocześnie.

---

<div align="center">

[← wróć do wydania #7 (wszystkie rubryki)](../README.md) · [spis wydań](../../README.md)

</div>
