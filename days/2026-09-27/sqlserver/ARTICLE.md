<div align="center">

# 📰 TECH PRASÓWKA
### Wydanie #4 — 27 września 2026

![SQL Server](https://img.shields.io/badge/SQL_Server-CC2927?style=for-the-badge&logo=microsoftsqlserver&logoColor=white)
![Poziom](https://img.shields.io/badge/poziom-zaawansowany-orange?style=for-the-badge)
![Zweryfikowane](https://img.shields.io/badge/kod-uruchomiony_na_SQL_Server_2022_CU27-brightgreen?style=for-the-badge)

## Deadlock na żywo i columnstore: dwie rzeczy, które w produkcji bolą najbardziej

</div>

---

> _"Indeksy przyspieszają zapytania. Ale jak dwa zapytania wchodzą sobie w drogę,
> albo jak raport przegląda 5 milionów wierszy — indeksy B-drzewo to za mało."_

**🎣 Dlaczego to ważne:** dziś dwa problemy, które nie wychodzą na Twoim laptopie,
tylko w piątek na produkcji.

1. **Deadlock** — dwie transakcje czekają na siebie nawzajem; SQL Server zabija jedną
   błędem **1205**. Wywołamy go celowo, **odczytamy deadlock graph** z wbudowanej sesji
   `system_health` i naprawimy zmianą jednej reguły.
2. **Columnstore** — ta sama agregacja na 5 mln wierszy: **896 ms** na zwykłej tabeli,
   **28 ms** na columnstore. Ta sama baza, ta sama maszyna, te same wyniki.

Wszystkie liczby i wydruki poniżej pochodzą z **realnego uruchomienia** kodu z
[`code/`](code/) na `mcr.microsoft.com/mssql/server:2022-latest` (SQL Server 2022
RTM-CU27, 16.0.4295.3, Developer Edition on Linux, Docker).

---

## 1️⃣ Deadlock: dwa przelewy, które się zakleszczają

Tabela `dbo.Accounts` ma dwa wiersze (Alicja = konto 1, Bartek = konto 2). Dwie sesje
robią przelewy w przeciwnych kierunkach i — jak w prawdziwym kodzie — aktualizują
najpierw konto „z”, potem konto „na” (czasy w tabeli orientacyjne: B startował ok. 1–2 s po A,
obie sesje czekają 3 s między dwoma `UPDATE`):

| Czas | Sesja A (Alicja → Bartek) | Sesja B (Bartek → Alicja) |
|---|---|---|
| t0 | `UPDATE ... WHERE AccountId = 1` — dostaje blokadę **X** na wierszu 1 | |
| t0+2 s | | `UPDATE ... WHERE AccountId = 2` — dostaje blokadę **X** na wierszu 2 |
| t0+3 s | chce wiersz 2 → **czeka na B** | |
| t0+5 s | | chce wiersz 1 → **czeka na A** |
| | 🔥 **cykl** — nikt nie ruszy | |

Nikt nie zwolni blokady przed `COMMIT`, więc bez interwencji czekaliby wiecznie (SQL
Server domyślnie **nie ma timeoutu** na blokady: `lockTimeout="4294967295"` w grafie).
Wykrywa to wątek monitora deadlocków (sprawdza cykle co kilka sekund), wybiera **ofiarę**
(domyślnie tę, której wycofanie jest tańsze) i wycofuje jej transakcję. Prawdziwy output:

```
B: mam blokade na wierszu 2, czekam 3 s...
B: probuje wiersz 1
B: BLAD 1205 - Transaction (Process ID 55) was deadlocked on lock resources with another process and has been chosen as the deadlock victim. Rerun the transaction.
```
```
A: mam blokade na wierszu 1, czekam 3 s...
A: probuje wiersz 2
A: COMMIT - sesja A przezyla
```

> 💡 **Dla .NET-owca:** to `SqlException` z `Number == 1205`. SQL Server sam mówi
> „Rerun the transaction" — deadlock to jedyny błąd, przy którym **ślepy retry całej
> transakcji jest zalecany**. Szkic (nieskompilowany, ilustracyjny):
> `catch (SqlException e) when (e.Number == 1205) { /* ponów CAŁĄ transakcję, z krótkim opóźnieniem */ }`.
> Ponawiaj całość (od `BEGIN TRAN`), nie sam ostatni `UPDATE`.

### 🔍 Deadlock graph: skąd go wziąć po fakcie

Nie musiałeś nic włączać. Wbudowana sesja **Extended Events `system_health`** zapisuje
zdarzenie `xml_deadlock_report` domyślnie. Odczyt z pliku `.xel`:

```sql
SELECT TOP (1) CAST(event_data AS xml).query('(event/data[@name="xml_report"]/value/deadlock)[1]')
FROM sys.fn_xe_file_target_read_file(N'system_health*.xel', NULL, NULL, NULL)
WHERE object_name = N'xml_deadlock_report'
ORDER BY 1 DESC;   -- (pełny skrypt: code/03-read-deadlock-graph.sql)
```

Zapisany do pliku `.xdl` otwiera się w SSMS jako graficzny diagram (kółka = procesy,
prostokąty = zasoby). My nie używaliśmy SSMS — oto **skrócony** XML (usunąłem
kilkadziesiąt linii `<stackFrames>`; reszta to prawdziwe wartości):

```xml
<deadlock>
  <victim-list><victimProcess id="processf10c83468"/></victim-list>
  <process-list>
    <process id="processf10c83468" waitresource="KEY: 5:72057594045726720 (8194443284a0)"
             waittime="1595" lockMode="X" spid="55" isolationlevel="read committed (2)" ...>
      <inputbuf> -- 02-deadlock-b.sql - SESJA B: przelew Bartek -> Alicja ... </inputbuf>
    </process>
    <process id="processf07721848" waitresource="KEY: 5:72057594045726720 (61a06abd401c)"
             waittime="3492" lockMode="X" spid="54" isolationlevel="read committed (2)" ...>
      <inputbuf> -- 02-deadlock-a.sql - SESJA A: przelew Alicja -> Bartek ... </inputbuf>
    </process>
  </process-list>
  <resource-list>
    <keylock objectname="PrasowkaLock.dbo.Accounts" indexname="PK_Accounts" mode="X">
      <owner-list><owner id="processf07721848" mode="X"/></owner-list>     <!-- A trzyma... -->
      <waiter-list><waiter id="processf10c83468" mode="X" requestType="wait"/></waiter-list>  <!-- ...B czeka -->
    </keylock>
    <keylock objectname="PrasowkaLock.dbo.Accounts" indexname="PK_Accounts" mode="X">
      <owner-list><owner id="processf10c83468" mode="X"/></owner-list>     <!-- B trzyma... -->
      <waiter-list><waiter id="processf07721848" mode="X" requestType="wait"/></waiter-list>  <!-- ...A czeka -->
    </keylock>
  </resource-list>
</deadlock>
```

Jak to czytać, w 4 krokach:

1. `victim-list` — kto został zabity (tu: spid 55, czyli sesja B).
2. `process-list` — uczestnicy: `waitresource` (na co czekają), `inputbuf` (**jaki kod** — tu widać, że to nasze pliki), `isolationlevel`.
3. `resource-list` — zasoby: kto je **posiada** (`owner`), kto **czeka** (`waiter`).
4. Cykl: A posiada zasób 1 i czeka na zasób 2, B odwrotnie. Widać go, gdy „owner" jednego zasobu jest „waiterem" drugiego.

Ten sam graf w postaci tabeli (zapytanie nr 2 z `03-read-deadlock-graph.sql`, prawdziwy wynik):

```
spid  rola     czeka_na                                 tryb  izolacja
  55  OFIARA   KEY: 5:72057594045726720 (8194443284a0)  X    read committed (2)
  54  przezyl  KEY: 5:72057594045726720 (61a06abd401c)  X    read committed (2)
```

Dwa różne klucze (`(8194...)` i `(61a0...)` to hashe kluczy wierszy) w tej samej
tabeli/indeksie — to znaczy dwa różne wiersze, każdy trzymany przez kogoś innego.

> ⚠️ **Pułapka:** plik `.xel` jest zapisywany z opóźnieniem. Pierwsza próba odczytu
> zaraz po deadlocku zwróciła u nas **0 wierszy** (zapytanie do `ring_buffer` już
> widziało 1 zdarzenie); powtórka po chwili — graf był. Jak wynik pusty, poczekaj.

### 🛠️ Naprawa: jedna spójna kolejność dostępu

Deadlock wymaga **cyklu**. Cykl znika, jeśli wszyscy sięgają po zasoby w **tej samej
kolejności**. Reguła: niezależnie od kierunku przelewu blokuj konta **rosnąco po
`AccountId`**:

```sql
BEGIN TRAN;
SELECT AccountId FROM dbo.Accounts WITH (UPDLOCK, ROWLOCK)
WHERE AccountId IN (@from, @to) ORDER BY AccountId;   -- najpierw 1, potem 2, zawsze
UPDATE dbo.Accounts SET Balance = Balance - @amount WHERE AccountId = @from;
UPDATE dbo.Accounts SET Balance = Balance + @amount WHERE AccountId = @to;
COMMIT;
```

Ten sam scenariusz czasowy (A: 1→2, B: 2→1, każdy czeka 3 s w środku), prawdziwy wynik:

```
A: mam blokady na obu wierszach (1 potem 2), czekam 3 s...
A: COMMIT
B: mam blokady na obu wierszach (1 potem 2), czekam 3 s...
B: COMMIT
```

Brak 1205, obie transakcje przeszły — druga po prostu **poczekała** na pierwszą
(zwykła kolejka, nie cykl). Saldo końcowe zgadza się (990 / 1010).

Uczciwe zastrzeżenia:

* `UPDLOCK` = „czytam, ale zamierzam zapisać" — blokada aktualizacji zajmuje wiersz
  wyłącznie dla piszących. Bez niej dwie sesje mogłyby obie wziąć blokadę S i potem
  zakleszczyć się przy zamianie na X (klasyczny „deadlock konwersji").
* Że `ORDER BY` przy `IN (...)` daje blokady w kolejności klucza — **w naszym teście
  na dwóch wierszach zadziałało**; formalnej gwarancji kolejności blokowania w
  dokumentacji nie sprawdzałem. Pewniejsze: aktualizuj wiersze osobnymi poleceniami
  w jawnie posortowanej kolejności (po `MIN(id)`, potem `MAX(id)`).
* Retry na 1205 zostaje jako siatka bezpieczeństwa — nie da się wyeliminować
  deadlocków w 100% (np. przez inne indeksy, blokady stron, kolejność w innych
  procedurach).

### 📖 Bonus: blokowanie czytelników i `READ_COMMITTED_SNAPSHOT`

Deadlock to skrajność; codziennością jest zwykłe **blokowanie**. Pisarz trzyma
otwartą transakcję (6 s) z blokadą X na wierszu 1; czytelnik robi zwykły `SELECT`:

| Tryb bazy | Czas `SELECT` czytelnika | Co zobaczył |
|---|---:|---|
| domyślny `READ COMMITTED` (RCSI = 0) | **4 762 ms** ⏳ (czekał na commit pisarza) | 992,00 (po commit) |
| `READ_COMMITTED_SNAPSHOT ON` (RCSI = 1) | **0 ms** | 991,00 (ostatnia zatwierdzona wersja) |

```sql
ALTER DATABASE PrasowkaLock SET READ_COMMITTED_SNAPSHOT ON WITH ROLLBACK IMMEDIATE;
```

Z RCSI czytelnicy nie biorą blokad współdzielonych, tylko czytają **poprzednią
zatwierdzoną wersję** wiersza (wersje wiersza są trzymane w `tempdb`/PVS w zależności
od włączenia ADR — szczegółów nie badałem). Efekt: raporty nie czekają na zapisy. To
też często usuwa deadlocki typu „czytelnik vs pisarz". Cena: obciążenie wersjonowaniem
(nie mierzone) i **inna semantyka** — czytelnik może widzieć „starą" wartość, mimo że
ktoś właśnie ją zmienia. Sprawdź, zanim włączysz na produkcji (Entity Framework
domyślnie wszystko robi na READ COMMITTED — RCSI zmienia zachowanie całej aplikacji).
Uwaga: `ALTER DATABASE ... ROLLBACK IMMEDIATE` **zabija** otwarte transakcje —
przy testach zabił nam nawet trwającego pisarza.

---

## 2️⃣ Columnstore: tabela zapisana kolumnami

Zwykła tabela (**rowstore**) trzyma dane **wierszami**: strona 8 kB zawiera całe
wiersze. Agregacja `SUM(Amount)` musi przeczytać strony z **wszystkimi** kolumnami.
**Columnstore** trzyma dane **kolumnami**: każda kolumna osobno, silnie skompresowana,
w porcjach zwanych **rowgroup** (do ~1 048 576 wierszy) i **segmentach**. Raport
`SUM(Amount) GROUP BY StoreId` czyta tylko dwie kolumny z sześciu, a wartości w
kolumnie są podobne, więc kompresja jest świetna.

Dodatkowo operatory przetwarzają dane w **batch mode** — paczkami ok. 900 wierszy naraz
zamiast po jednym (**row mode**), co dobrze wykorzystuje CPU.

Eksperyment: tabela faktów `FactSales`, **5 000 000 wierszy** (6 kolumn: id, data,
produkt, sklep, ilość, kwota; dane deterministyczne z generatora), trzy wersje:

* `FactSales_Row` — zwykły klastrowany PK (rowstore),
* `FactSales_RowIx` — rowstore + **uczciwy rywal**: indeks pokrywający `(StoreId, SaleDate) INCLUDE (Quantity, Amount)`,
* `FactSales_CCI` — `CLUSTERED COLUMNSTORE INDEX`.

### 💾 Rozmiar

| Tabela | Rozmiar |
|---|---:|
| `FactSales_Row` | 189,1 MB |
| `FactSales_RowIx` (tabela + indeks pokrywający) | 344,1 MB |
| `FactSales_CCI` | **33,6 MB** (5,6× mniej niż rowstore) |

⚠️ Nasze dane są bardzo powtarzalne (deterministyczne wzorce), więc kompresja jest
tu wyjątkowo dobra. Na realnych danych współczynnik będzie inny — nie traktuj 5,6×
jako reguły.

### ⏱️ Wyniki (cały przebieg powtórzony, drugi = ciepły cache; `MAXDOP 1`)

**Q1** — `SUM/COUNT ... GROUP BY StoreId` po całej tabeli:

| Wariant | Logical reads | CPU / czas |
|---|---:|---:|
| rowstore, batch mode **wyłączony** hintem | 24 208 | 3 197 ms |
| rowstore + indeks pokrywający | 19 826 | 2 118 ms |
| rowstore (domyślny plan, batch mode) | 24 208 | 892 ms |
| **columnstore** | **1 254** (lob) | **27 ms** |

**Q2** — to samo, ale `WHERE SaleDate` w jednym kwartale (3 z 36 miesięcy):

| Wariant | Logical reads | CPU / czas |
|---|---:|---:|
| rowstore | 24 208 | 605 ms |
| rowstore + indeks pokrywający | 19 826 | 689 ms |
| **columnstore** | **2 249** (lob) | **15 ms** |

Trzy rzeczy, które warto wyciągnąć:

1. **Columnstore wygrywa o rzędy wielkości** dla agregacji: ~30–40× mniej czasu CPU niż
   domyślny rowstore, ~120× mniej niż rowstore z wyłączonym batch mode (Q1: 27 ms vs 3 197 ms).
2. **Indeks pokrywający nie uratował rowstore** — czytał 19 826 stron zamiast 24 208
   (nie tak dużo mniej) i był wolniejszy, bo (w naszym planie) skan był w **row mode**,
   podczas gdy skan zwykłej tabeli dostał **batch mode**.
3. **Batch mode działa też na rowstore** (SQL Server 2019+; tu domyślnie, bez
   `columnstore` w ogóle): ten sam plan, ten sam skan tej samej tabeli — **892 ms z batch
   mode vs 3 197 ms bez** (hint `DISALLOW_BATCH_MODE`). Tryb wykonania sprawdziliśmy w
   cache'owanych planach (`EstimatedExecutionMode`):

```
zapytanie                   tryb_skanu tryb_hash_agg
Q1 rowstore                 Batch      Batch
Q1 rowstore, DISALLOW_BATCH Row        Row
Q1 rowstore+ix              Row        NULL
Q1 columnstore              Batch      Batch
```

Dlaczego optymalizator wybrał row mode dla skanu indeksu pokrywającego, a batch dla
klastrowanego — nie badaliśmy (heurystyki batch mode on rowstore zależą m.in. od
poziomu zgodności bazy i szacunków; tu tego nie weryfikowałem).

### 🧨 Pułapka 1: columnstore nie jest do punktowych odczytów

**Q3** — `WHERE SaleId = 2500000`, jeden wiersz:

| Wariant | Logical reads |
|---|---:|
| rowstore (seek po PK) | **3** |
| columnstore (bez dodatkowego indeksu) | 1 373 (lob) |

To zupełnie inne zwierzę. Do OLTP zostaje B-tree; do analityki — columnstore.
Można je łączyć: nonclustered B-tree na tabeli z CCI albo nonclustered columnstore na
tabeli OLTP (tego dziś nie mierzyliśmy).

### 🧨 Pułapka 2: eliminacja segmentów wymaga posortowanych danych

W Q2 filtrowaliśmy po dacie, ale w wyniku widać `Segment reads 6, segment skipped 0` —
columnstore przeczytał **wszystkie** segmenty. Każdy segment ma zapisane min/max
wartości, a jeśli daty są w nim rozrzucone od początku do końca zakresu, nie da się
go pominąć. Naprawa: zbudować columnstore z danych **posortowanych po kolumnie
filtra**:

```sql
CREATE CLUSTERED INDEX CCI_FactSales_Ord ON dbo.FactSales_CCI_Ord (SaleDate);
CREATE CLUSTERED COLUMNSTORE INDEX CCI_FactSales_Ord ON dbo.FactSales_CCI_Ord WITH (DROP_EXISTING = ON, MAXDOP = 1);
```

Efekt (prawdziwy): zakresy dat w rowgroupach są teraz rozłączne (`min_data_id..max_data_id`:
738520–738749, 738749–738979, …), a Q2 daje `Segment reads 1, segment skipped 4`
i **743** odczytów lob zamiast 2 249 (czas 10 ms vs 15 ms — różnica mała przy
tak małej tabeli).

> 🪤 Nasza pierwsza próba — `INSERT ... SELECT ... ORDER BY SaleDate` do tabeli z CCI —
> **nie posortowała rowgroupów** (każdy nadal obejmował cały zakres dat; sprawdziliśmy
> w `sys.column_store_segments`). `ORDER BY` przy `INSERT` nie jest gwarancją, więc
> nie polegaj na tym.

---

## 🧾 Ściąga na dziś

| Pojęcie | Jedno zdanie |
|---|---|
| Deadlock (błąd 1205) | cykl oczekiwań: A czeka na B, B na A; SQL Server zabija jedną transakcję |
| `system_health` (XE) | domyślna sesja zdarzeń; `xml_deadlock_report` = deadlock graph po fakcie |
| Deadlock graph | `victim-list` → `process-list` (kto/co/jaki kod) → `resource-list` (owner/waiter) |
| Naprawa | jedna spójna kolejność dostępu do zasobów + retry na 1205 jako zabezpieczenie |
| `UPDLOCK` | „czytam, bo zaraz zapiszę" — zapobiega deadlockowi konwersji S→X |
| RCSI | czytelnicy czytają ostatnią zatwierdzoną wersję: 4 762 ms → 0 ms, ale zmiana semantyki |
| Columnstore (CCI) | dane kolumnami w rowgroupach; u nas 33,6 MB vs 189,1 MB i 27 ms vs 892 ms |
| Batch mode | przetwarzanie paczkami ~900 wierszy; działa też na rowstore (3 197 → 892 ms) |
| Segment elimination | wymaga danych posortowanych po kolumnie filtra |
| Punktowy odczyt | rowstore 3 odczyty vs columnstore 1 373 — nie do OLTP |

**Pełny, uruchamialny kod + komendy:** [`code/README.md`](code/README.md).

**Co dalej:** Query Store hints (`sp_query_store_set_hints`), Parameter Sensitive Plan
optimization, deadlocki z `SERIALIZABLE`/blokadami zakresów i `sp_getapplock`,
nonclustered columnstore na tabeli OLTP, aktualizacje/`DELETE` w columnstore
(delta store, `REORGANIZE`).

---

## ✅ Status weryfikacji

Kod uruchomiony realnie: kontener `mcr.microsoft.com/mssql/server:2022-latest`
(SQL Server 2022 RTM-CU27, 16.0.4295.3), skrypty `01`–`09` wykonane ręcznie przez
`docker exec ... sqlcmd` (`-C -I`; sesje A/B jako dwa równoległe procesy, jeden w tle).
Wszystkie liczby powyżej pochodzą z tych uruchomień.

Uczciwe uwagi:

1. `run-demo.sh` jako całość **nie został odpalony** (kroki wykonano ręcznie) i `10-cleanup.sql` też nie
   (kontener usunięto w całości).
2. Czasy wahają się między przebiegami (np. Q1 columnstore 27–30 ms); logical reads są
   deterministyczne. Test na jednym kontenerze, `MAXDOP 1`, pojedyncze pomiary — to
   ilustracja rzędów wielkości, nie benchmark. Wyniki bez `MAXDOP 1` (równoległe) nie były mierzone.
3. Deadlock jest wywołany sztucznie (`WAITFOR DELAY`), żeby był powtarzalny; w
   produkcji okno wyścigu jest wąskie i deadlock pojawia się „losowo".
4. **Niezweryfikowane:** graficzny widok grafu w SSMS, zachowanie kolejności blokad
   przy większej liczbie wierszy w naprawie z `UPDLOCK`, koszt RCSI (wersjonowanie),
   przyczyna row mode dla skanu indeksu pokrywającego, poziom zgodności bazy
   (nie sprawdzany jawnie), nonclustered columnstore, aktualizacje/delete w columnstore.
5. Deadlock graph w artykule jest **skrócony** (usunięte `<stackFrames>` i część atrybutów).

---

<div align="center">

[← wróć do wydania #4 (wszystkie rubryki)](../README.md) · [spis wydań](../../README.md)

</div>
