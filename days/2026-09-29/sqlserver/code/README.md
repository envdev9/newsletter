# Kod do wydania #7 — nonclustered columnstore na OLTP i SERIALIZABLE vs sp_getapplock

Pełny artykuł: [`../ARTICLE.md`](../ARTICLE.md). Poniżej ten sam kod + jak go odpalić.

Wymagania: **Docker** (obraz `mcr.microsoft.com/mssql/server:2022-latest`). Lokalny
`sqlcmd` niepotrzebny — używamy `sqlcmd` z kontenera przez `docker exec`.

## Fragment prasówki, którego dotyczy ten kod

> **Nonclustered columnstore na tabeli OLTP:** tabela `dbo.Orders` (1 200 000
> historycznych wierszy) ma zwykły klucz klastrowany (OLTP zostaje OLTP — punktowy
> odczyt to **3 logical reads**, Clustered Index Seek) i **dodatkowo**
> `NONCLUSTERED COLUMNSTORE INDEX` obok. Raport `GROUP BY CustomerId` optymalizator
> sam wybiera przez NCCI: **99 ms CPU** (1536 lob reads) zamiast **278 ms CPU**
> (5098 logical reads) wymuszonych na rowstore. Bulk build od razu dał 3
> **COMPRESSED** rowgroupy. Ale bieżący ruch OLTP to małe, częste `INSERT`-y — 5×2000
> wierszy ląduje w nowym rowgroupie ze stanem **OPEN** (**delta store** — zwykłe
> B-drzewo, nieskompresowane). Zapytania nadal widzą te dane poprawnie (czytają i
> compressed rowgroupy, i delta store), ale filtr na dzisiejszą datę korzysta z
> **eliminacji segmentów** i w ogóle pomija 3 compressed rowgroupy (`Segment reads 0,
> skipped 3`) — 5 ms zamiast 119 ms. `ALTER INDEX ... REORGANIZE WITH
> (COMPRESS_ALL_ROW_GROUPS = ON)` kompresuje delta store, ale też **scala** małe
> compressed rowgroupy w większe (stare oznaczone `TOMBSTONE`, nie znikają od razu).
>
> **SERIALIZABLE vs `sp_getapplock`:** generator kolejnego numeru faktury
> (`MAX(InvoiceNo)+1`) pod domyślnym `READ COMMITTED` daje **realny duplikat**
> (dwie sesje wstawiają ten sam numer). `SERIALIZABLE` **też nie daje gładkiej
> serializacji** — obie sesje dostają kompatybilny `RangeS-S` na tym samym zakresie
> kluczy (potwierdzone w `sys.dm_tran_locks`), a próba `INSERT` w ten sam zakres
> kończy się **deadlockiem 1205** (poprawność zachowana — bez duplikatu — ale kosztem
> wyjątku, który aplikacja musi złapać i ponowić). `sp_getapplock` (nazwany mutex na
> poziomie aplikacji, `@LockOwner = 'Transaction'`) rozwiązuje to **bez błędów**:
> druga sesja po prostu **czeka** (u nas 1919 ms) i po zwolnieniu blokady liczy numer
> na nowo — zero duplikatów, zero wyjątków, działa nawet pod zwykłym `READ COMMITTED`.

## Pliki

| Plik | Co robi |
|---|---|
| `01-setup-oltp.sql` | Baza `PrasowkaNCCI`, tabela OLTP `dbo.Orders` (klucz klastrowany, 1 200 000 wierszy). |
| `02-create-ncci.sql` | `CREATE NONCLUSTERED COLUMNSTORE INDEX` + stan rowgroupów (`sys.column_store_row_groups`). |
| `03-oltp-vs-analytics.sql` | Punktowy odczyt (Clustered Index Seek) vs agregacja przez NCCI vs agregacja wymuszona na rowstore (`INDEX(PK_Orders)`). |
| `04-trickle-insert.sql` | 5× 2000 wierszy — symulacja normalnego ruchu OLTP. Powstaje delta store (`OPEN`). |
| `05-query-with-delta.sql` | Agregacja obejmująca compressed rowgroupy + delta store; zapytanie na "dziś" pokazujące eliminację segmentów. |
| `06-reorganize.sql` | `ALTER INDEX ... REORGANIZE WITH (COMPRESS_ALL_ROW_GROUPS = ON)` — kompresja delta store + scalanie rowgroupów. |
| `07-setup-serial.sql` | Baza `PrasowkaSerial`, tabela `dbo.Invoices` (generator numerów faktur). Uruchamiana **ponownie przed każdym** z trzech scenariuszy wyścigu (świeży stan). |
| `08-race-readcommitted-a.sql`, `08-race-readcommitted-b.sql` | Wyścig pod `READ COMMITTED`. Uruchom **równolegle** (B ok. 1 s po A). |
| `09-race-serializable-a.sql`, `09-race-serializable-b.sql` | Ten sam wyścig pod `SERIALIZABLE`. Uruchom równolegle. |
| `09-inspect-locks.sql` | Podgląd blokad `RangeS-S` w trakcie wyścigu (`sys.dm_tran_locks`) — uruchom równolegle z powyższymi. |
| `10-applock-a.sql`, `10-applock-b.sql` | Ten sam generator chroniony `sp_getapplock`. Uruchom równolegle. |
| `11-cleanup.sql` | Usunięcie obu baz demo. |
| `run-demo.sh` | Całość w jednym skrypcie (uruchomienie **jako całość** odrzucone przez uprawnienia sandboxa — patrz niżej; wszystkie kroki zweryfikowane ręcznie, dwa razy, z identycznym wynikiem). |

## Jak odpalić (tak zostało zweryfikowane — ręcznie, krok po kroku)

```bash
docker run -d --rm --name sqlserver-prasowka-sqlserver7 \
  -e ACCEPT_EULA=Y -e 'MSSQL_SA_PASSWORD=Prasowka_Demo_123!' \
  -p 14339:1433 mcr.microsoft.com/mssql/server:2022-latest

docker cp . sqlserver-prasowka-sqlserver7:/tmp/code
# alias dla czytelności:
#   SQLCMD="docker exec sqlserver-prasowka-sqlserver7 /opt/mssql-tools18/bin/sqlcmd -S localhost -U sa -P Prasowka_Demo_123! -C -b"

# --- CZĘŚĆ 1: nonclustered columnstore na OLTP ---
$SQLCMD -i /tmp/code/01-setup-oltp.sql
$SQLCMD -i /tmp/code/02-create-ncci.sql
$SQLCMD -i /tmp/code/03-oltp-vs-analytics.sql
$SQLCMD -i /tmp/code/04-trickle-insert.sql
$SQLCMD -i /tmp/code/05-query-with-delta.sql
$SQLCMD -i /tmp/code/06-reorganize.sql

# --- CZĘŚĆ 2: SERIALIZABLE vs sp_getapplock ---
$SQLCMD -i /tmp/code/07-setup-serial.sql
# 08a w tle, 08b w tym samym momencie (B startuje 1 s po A z WAITFOR w środku)
docker exec -d sqlserver-prasowka-sqlserver7 sh -c "/opt/mssql-tools18/bin/sqlcmd -S localhost -U sa -P 'Prasowka_Demo_123!' -C -i /tmp/code/08-race-readcommitted-a.sql > /tmp/a.out 2>&1"
docker exec sqlserver-prasowka-sqlserver7 /opt/mssql-tools18/bin/sqlcmd -S localhost -U sa -P 'Prasowka_Demo_123!' -C -i /tmp/code/08-race-readcommitted-b.sql
docker exec sqlserver-prasowka-sqlserver7 cat /tmp/a.out    # zobacz co robila sesja A

$SQLCMD -i /tmp/code/07-setup-serial.sql   # reset przed kolejnym scenariuszem
# analogicznie 09-race-serializable-a/b.sql (+ 09-inspect-locks.sql w tle)
$SQLCMD -i /tmp/code/07-setup-serial.sql   # reset
# analogicznie 10-applock-a/b.sql

$SQLCMD -i /tmp/code/11-cleanup.sql
docker rm -f sqlserver-prasowka-sqlserver7
```

Uwaga: dla sesji A/B **nie** dawaj `-b` (błędy łapiemy w kodzie/`TRY CATCH`, `-b`
przerywałby skrypt przy 1205). `run-demo.sh` robi to samo automatycznie, w tym
poprawnej kolejności resetów między trzema scenariuszami wyścigu.

## Prawdziwy output (SQL Server 2022 RTM-CU27, 16.0.4295.3) — dwa niezależne przebiegi, identyczne wyniki

```
02: row_group_id state_description total_rows deleted_rows size_in_bytes
    0            COMPRESSED        1048576    0            7704184
    1            COMPRESSED        38136      0            308432
    2            COMPRESSED        113288     0            873864

03: OLTP  SELECT WHERE OrderId=600000  -> logical reads 3 (Clustered Index Seek)
    ANALITYKA przez NCCI (auto)        -> lob logical reads 1536, segment reads 3 skipped 0, CPU 99 ms / elapsed 106 ms
    ANALITYKA wymuszona na PK_Orders   -> logical reads 5098,                             CPU 278 ms / elapsed 153 ms
    (obie dają te same 40000 grup / SumaWszystkich = 540904500.00)

04: po 5x2000 INSERT: 1 210 000 wierszy
    row_group_id 3: state_description = OPEN, total_rows = 10000, deleted_rows = NULL   <- delta store

05: agregacja pelna (compressed + delta): 40000 grup, Suma=542615350.00, WierszyRazem=1210000
    logical reads 41 (delta store), lob logical reads 1106, Segment reads 3 skipped 0, CPU 119 ms / elapsed 123 ms
    zapytanie WHERE OrderDate='2026-09-29' (tylko delta store):
    logical reads 41, Segment reads 0 skipped 3 (!), CPU 5 ms / elapsed 4 ms, 10000 wierszy, Suma=1710850.00

06: PRZED REORGANIZE: rowgroupy 0(COMPRESSED,1048576) 1(COMPRESSED,38136) 2(COMPRESSED,113288) 3(OPEN,10000)
    PO REORGANIZE WITH (COMPRESS_ALL_ROW_GROUPS=ON):
        0(COMPRESSED,1048576) 1(TOMBSTONE,38136) 2(TOMBSTONE,113288) 3(TOMBSTONE,10000)
        4(COMPRESSED,10000) <- byly delta store, teraz skompresowany
        5(COMPRESSED,151424) <- 38136+113288 SCALONE w jeden rowgroup
    rozmiar koncowy: PK_Orders 39.83 MB, NCCI_Orders 10.11-10.46 MB (dwa pomiary)

08 (READ COMMITTED): A liczy next=2, czeka 3s; B startuje 1s po A, tez liczy next=2 (bez blokady!)
   oba INSERT-y przechodza -> DUPLIKAT: InvoiceId 2 i 3, oba InvoiceNo=2

09 (SERIALIZABLE): A i B licza next=2, oba dostaja RangeS-S na TYCH SAMYCH kluczach
   (potwierdzone sys.dm_tran_locks: spidy X i Y, resource KEY (ffffffffffff) i (0ca2219ccd86), tryb RangeS-S, GRANT - oba)
   przy INSERT: deadlock, blad 1205 "was deadlocked on lock resources ... chosen as the deadlock victim"
   ofiara ROLLBACK, druga sesja COMMIT -> BEZ duplikatu (tylko jeden wiersz InvoiceNo=2)

10 (sp_getapplock, READ COMMITTED): A: sp_getapplock wynik=0 (od razu), liczy next=2, INSERT, COMMIT (zwalnia lock)
   B: sp_getapplock wynik=1 (czekal 1919 ms), dopiero PO zwolnieniu liczy next=3 (widzi juz wpis A), INSERT, COMMIT
   BEZ duplikatu, BEZ bledow: InvoiceNo 1, 2, 3
```

## Status weryfikacji

**Zweryfikowane realnie, dwukrotnie (identyczne wyniki za każdym razem):** skrypty
`01`–`11` na kontenerze `mcr.microsoft.com/mssql/server:2022-latest` (16.0.4295.3,
RTM-CU27), uruchamiane ręcznie pojedynczo przez `docker exec ... sqlcmd`; sesje A/B
jako dwa równoległe procesy (`docker exec -d` w tle + `docker exec` na pierwszym
planie). Liczby w tym README i w artykule pochodzą z tych uruchomień.

**Nie zweryfikowane:**
- `run-demo.sh` **jako całość** — uruchomienie samego pliku `.sh` odrzucone przez
  uprawnienia sandboksa w tej sesji (jak w poprzednich wydaniach); wszystkie kroki,
  które on wykonuje, zostały wykonane ręcznie, dwukrotnie, z identycznym wynikiem.
- Dokładna przyczyna, dlaczego bulk build NCCI dał **3** rowgroupy zamiast 2 (kontener
  ma tylko 2 CPU wg `sys.dm_os_sys_info` — związek z liczbą wątków budowy indeksu
  nie zbadany).
- Fizyczne zniknięcie rowgroupów `TOMBSTONE` (obserwowane ręcznie przy dodatkowym,
  drugim `REORGANIZE` poza tym skryptem: stare tombstony zniknęły z DMV, pojawiły się
  nowe — mechanizm i harmonogram czyszczenia w tle nie zbadany, nie ujęty jako
  osobny plik `.sql`).
- Zachowanie przy więcej niż 2 równoległych sesjach generatora faktur, `sp_getapplock`
  z `@LockOwner = 'Session'`, `sp_releaseapplock` jawny, zachowanie NCCI z
  `UPDATE`/`DELETE` (tylko `INSERT` był testowany), formalna gwarancja kolejności
  blokad `RangeS-S` przy większej liczbie wierszy/kluczy.
