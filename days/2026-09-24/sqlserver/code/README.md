# Kod do wydania #1 — Indeks: B-drzewo, plan wykonania, `logical reads`

Pełny artykuł: [`../ARTICLE.md`](../ARTICLE.md). Poniżej ten sam kod + jak go odpalić.

Wymagania: **Docker** (obraz `mcr.microsoft.com/mssql/server:2022-latest`,
ok. 2-3 GB po rozpakowaniu, potrzebuje kilku GB wolnego miejsca na dysku). Nie
jest wymagany lokalny `sqlcmd` — skrypt uruchomieniowy używa `sqlcmd` z wnętrza
kontenera przez `docker exec`.

## Fragment prasówki, którego dotyczy ten kod

> Indeks nieklastrowany (`NONCLUSTERED INDEX`) to osobna struktura danych trzymana
> obok tabeli — B-drzewo (B-tree). Węzły liścia trzymają posortowane wartości
> indeksowanej kolumny razem ze wskaźnikiem do właściwego wiersza. Znalezienie
> konkretnej wartości to `log(N)` porównań zamiast N — przy 500 000 wierszy to
> kilkanaście "skoków" zamiast pół miliona sprawdzeń.
>
> Bez indeksu SQL Server robi **Clustered Index Scan** (skanuje całą tabelę),
> z indeksem robi **Index Seek** + **Key Lookup**. Indeks przyspiesza `SELECT`,
> ale spowalnia `INSERT`/`UPDATE`/`DELETE` — bo każda zmiana zaindeksowanej
> kolumny musi zaktualizować i tabelę, i B-drzewo indeksu (czasem kosztowny
> `page split`).

## Pliki

| Plik | Co robi |
|---|---|
| `01-create-table-and-data.sql` | Tworzy bazę `PrasowkaDemo` + tabelę `dbo.Orders`, wypełnia 500 000 wierszy (generator przez `ROW_NUMBER()`/`CROSS JOIN`, bez pętli, bez tabeli pomocniczej). |
| `02-query-no-index.sql` | `SELECT ... WHERE CustomerId = 1` **przed** utworzeniem indeksu, z `SET STATISTICS IO/TIME/PROFILE ON`. |
| `03-create-index.sql` | `CREATE NONCLUSTERED INDEX IX_Orders_CustomerId ON dbo.Orders (CustomerId)`. |
| `04-query-with-index.sql` | To samo zapytanie co w 02, **po** utworzeniu indeksu — porównanie 1:1. |
| `05-insert-cost-comparison.sql` | Koszt zapisu: 20 000 nowych wierszy wstawianych do tabeli bez i z indeksem, z `SET STATISTICS TIME ON`. |
| `06-cleanup.sql` | Opcjonalne usunięcie bazy `PrasowkaDemo` na koniec. |
| `run-demo.sh` | Odpala wszystko od zera: stawia kontener, czeka aż SQL Server przyjmie połączenia, uruchamia skrypty 01→05 przez `sqlcmd` w kontenerze, na końcu usuwa kontener. |

## Jak odpalić od zera

```bash
cd days/2026-09-24/sqlserver/code
./run-demo.sh
```

Skrypt sam: stawia kontener `mcr.microsoft.com/mssql/server:2022-latest`
(`ACCEPT_EULA=Y`, hasło SA ustawione w skrypcie), czeka aż SQL Server odpowiada na
`SELECT 1`, odpala kolejno `01`→`05` przez
`docker exec ... /opt/mssql-tools18/bin/sqlcmd -S localhost -U sa -P ... -C`,
i na końcu robi `docker rm -f` na kontenerze (kontener jest też postawiony z
`--rm`, więc nie zostaje żadnych śladów na dysku).

Ręcznie, krok po kroku (jeśli wolisz kontrolować każdy krok osobno):

```bash
docker run -d --rm --name sqlserver-prasowka-demo \
  -e "ACCEPT_EULA=Y" -e "MSSQL_SA_PASSWORD=Prasowka#2026!" \
  -p 14333:1433 mcr.microsoft.com/mssql/server:2022-latest

# poczekaj, aż kontener przyjmuje połączenia:
docker exec sqlserver-prasowka-demo /opt/mssql-tools18/bin/sqlcmd \
  -S localhost -U sa -P 'Prasowka#2026!' -C -Q "SELECT 1"

# odpal skrypty w kolejności:
for f in 01-create-table-and-data.sql 02-query-no-index.sql \
         03-create-index.sql 04-query-with-index.sql \
         05-insert-cost-comparison.sql; do
  docker exec -i sqlserver-prasowka-demo /opt/mssql-tools18/bin/sqlcmd \
    -S localhost -U sa -P 'Prasowka#2026!' -C -b -i /dev/stdin < "$f"
done

# posprzątaj na końcu:
docker rm -f sqlserver-prasowka-demo
```

## Status weryfikacji — ZWERYFIKOWANE (2026-09-29)

Uruchomione realnie na SQL Server 2022 (obraz `mcr.microsoft.com/mssql/server:2022-latest`)
w Dockerze, ręcznie przez `docker exec ... sqlcmd` (skrypty 01→05, kolejno).
`run-demo.sh` samo w sobie nie zostało odpalone (Bash w trybie "don't ask" blokuje
wykonanie pliku `.sh` — te same komendy odpalone ręcznie, krok po kroku, zadziałały).

### Wyniki

**Krok 02 — `SELECT ... WHERE CustomerId = 1` BEZ indeksu:**
```
Table 'Orders'. Scan count 1, logical reads 2495, ...
SQL Server Execution Times: CPU time = 49 ms, elapsed time = 48 ms.
```
Plan: `Clustered Index Scan` (skan całej tabeli, 500 000 wierszy).

**Krok 03 — `CREATE NONCLUSTERED INDEX IX_Orders_CustomerId`:**
```
IndexName             IndexType     Strony8KB  RozmiarMB
IX_Orders_CustomerId  NONCLUSTERED  866        6.765625   (poziom liści)
IX_Orders_CustomerId  NONCLUSTERED  2          .015625    (poziom pośredni)
IX_Orders_CustomerId  NONCLUSTERED  1          .007812    (root)
```

**Krok 04 — to samo zapytanie, PO utworzeniu indeksu:**
```
Table 'Orders'. Scan count 1, logical reads 30, ...
SQL Server Execution Times: CPU time = 2 ms, elapsed time = 2 ms.
```
Plan: `Index Seek` na `IX_Orders_CustomerId` + `Clustered Index Seek ... LOOKUP`
(Key Lookup) na `PK__Orders__...`. **2495 → 30 logical reads (83× mniej)**,
49 ms → 2 ms.

**Krok 05 — koszt zapisu, INSERT 20 000 wierszy:**
```
--- BEZ indeksu na CustomerId ---
SQL Server Execution Times: CPU time = 179 ms, elapsed time = 186 ms.
--- Z indeksem na CustomerId ---
SQL Server Execution Times: CPU time = 464 ms, elapsed time = 477 ms.
```
**2,6× wolniej** przy tym samym batchu, bo każdy wstawiany wiersz musi
dodatkowo zaktualizować B-drzewo indeksu.

### Błąd znaleziony i naprawiony przy weryfikacji

`03-create-index.sql` **nie miał** `USE PrasowkaDemo;` na początku. Każdy plik
odpalany przez osobne `docker exec -i ... sqlcmd -i /dev/stdin < plik.sql` to
**nowa sesja** — kontekst bazy ustawiony w poprzednim pliku (`02-...`) się nie
przenosi. Bez tej linii `CREATE INDEX` kończył się błędem:
```
Msg 1088, ... Cannot find the object "dbo.Orders" because it does not exist
or you do not have permissions.
```
Plik w tym katalogu jest już poprawiony (`USE PrasowkaDemo; GO` dodane na
początku) — kod w repo jest teraz w pełni zgodny z powyższym outputem.

Środowisko po weryfikacji: kontener usunięty (`docker rm -f`), zero śladów na
dysku (obraz `mcr.microsoft.com/mssql/server:2022-latest` zostaje w lokalnym
cache Dockera — nie w repo — kolejne wydania nie muszą go pobierać ponownie).
