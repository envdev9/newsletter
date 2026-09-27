# Kod do wydania #4 — deadlock, blokady, RCSI i columnstore

Pełny artykuł: [`../ARTICLE.md`](../ARTICLE.md). Poniżej ten sam kod + jak go odpalić.

Wymagania: **Docker** (obraz `mcr.microsoft.com/mssql/server:2022-latest`). Lokalny
`sqlcmd` niepotrzebny — używamy `sqlcmd` z kontenera przez `docker exec`.

## Fragment prasówki, którego dotyczy ten kod

> **Deadlock:** dwie sesje aktualizują konta w przeciwnej kolejności (A: 1→2, B: 2→1),
> powstaje cykl i SQL Server zabija jedną transakcję błędem **1205**. Deadlock graph
> odczytujemy z domyślnej sesji XE `system_health` (`xml_deadlock_report`):
> `victim-list` (ofiara), `process-list` (kto, na co czeka, jaki kod), `resource-list`
> (owner/waiter — cykl). Naprawa: spójna kolejność dostępu (`UPDLOCK` na obu wierszach
> rosnąco po kluczu) — obie transakcje przechodzą, druga po prostu czeka. Blokowanie
> czytelnika: `SELECT` czekał 4 762 ms na pisarza; z `READ_COMMITTED_SNAPSHOT ON` — 0 ms
> (i widział ostatnią zatwierdzoną wersję).
> **Columnstore:** 5 000 000 wierszy, agregacja `GROUP BY StoreId`: rowstore 892 ms
> (24 208 odczytów), rowstore bez batch mode 3 197 ms, rowstore + indeks pokrywający
> 2 118 ms (19 826), **columnstore 27 ms** (1 254 lob). Rozmiar: 189,1 MB vs 33,6 MB.
> Pułapki: punktowy odczyt (3 vs 1 373 odczytów) i eliminacja segmentów, która wymaga
> danych posortowanych po kolumnie filtra (`segment skipped 4` po przebudowie).

## Pliki

| Plik | Co robi |
|---|---|
| `01-setup-deadlock.sql` | Baza `PrasowkaLock`, tabela `dbo.Accounts` (2 konta). |
| `02-deadlock-a.sql`, `02-deadlock-b.sql` | Dwie sesje w odwrotnej kolejności blokowania → deadlock. Uruchom **równolegle**. |
| `03-read-deadlock-graph.sql` | Odczyt deadlock graph z `system_health` (XML + spłaszczona tabela). |
| `04-fixed-a.sql`, `04-fixed-b.sql` | Naprawa: `UPDLOCK` na obu wierszach w kolejności klucza. Uruchom równolegle. |
| `05-blocking-writer.sql`, `05-blocking-reader.sql`, `05-rcsi-on.sql` | Pisarz (6 s w transakcji) + czytelnik z pomiarem; włączenie RCSI. |
| `06-facts-setup.sql` | Baza `PrasowkaCS`, `FactSales_Row` (5 mln wierszy, rowstore). |
| `07-columnstore.sql` | `FactSales_RowIx` (indeks pokrywający), `FactSales_CCI` (columnstore), rozmiary, rowgroupy. |
| `08-compare.sql` | Q1/Q2/Q3 na trzech tabelach + tryb wykonania (Row/Batch) z cache planów. Uruchom 2×. |
| `09-segment-elimination.sql` | Columnstore posortowany po dacie → `segment skipped`. |
| `10-cleanup.sql` | Opcjonalne usunięcie baz. |
| `run-demo.sh` | Całość w jednym skrypcie (**niezweryfikowany jako całość**, patrz niżej). |

## Jak odpalić (tak zostało zweryfikowane — ręcznie)

```bash
docker run -d --name sqlserver-prasowka-d4 \
  -e ACCEPT_EULA=Y -e 'MSSQL_SA_PASSWORD=Prasowka_Demo_123!' \
  -p 14344:1433 mcr.microsoft.com/mssql/server:2022-latest

docker cp . sqlserver-prasowka-d4:/tmp/code
# alias dla czytelności:
#   SQLCMD="docker exec sqlserver-prasowka-d4 /opt/mssql-tools18/bin/sqlcmd -S localhost -U sa -P Prasowka_Demo_123! -C -I"

# --- deadlock ---
$SQLCMD -b -i /tmp/code/01-setup-deadlock.sql
docker exec -d sqlserver-prasowka-d4 sh -c "/opt/mssql-tools18/bin/sqlcmd -S localhost -U sa -P 'Prasowka_Demo_123!' -C -I -i /tmp/code/02-deadlock-a.sql > /tmp/a.out 2>&1"
$SQLCMD -i /tmp/code/02-deadlock-b.sql          # zaraz po A; B dostaje 1205
docker exec sqlserver-prasowka-d4 cat /tmp/a.out
$SQLCMD -y 120 -i /tmp/code/03-read-deadlock-graph.sql   # jak pusto - odczekaj kilkanascie sekund

# --- naprawa: analogicznie z 04-fixed-a.sql (w tle) i 04-fixed-b.sql ---

# --- blokowanie / RCSI ---
# writer w tle (05-blocking-writer.sql), od razu reader (05-blocking-reader.sql) -> ~4-5 s
# 05-rcsi-on.sql, powtorz writer + reader -> 0 ms

# --- columnstore ---
$SQLCMD -b -i /tmp/code/06-facts-setup.sql
$SQLCMD -b -i /tmp/code/07-columnstore.sql
$SQLCMD -b -y 40 -i /tmp/code/08-compare.sql
$SQLCMD -b -y 40 -i /tmp/code/09-segment-elimination.sql

docker rm -f sqlserver-prasowka-d4
```

Uwaga: dla sesji A/B **nie** dawaj `-b` (błąd 1205 łapiemy w `TRY/CATCH`, ale `-b` przerywałby
skrypt). Skrypty z filtrowanymi indeksami/XML wymagają `-I` (`QUOTED_IDENTIFIER ON`).
`05-rcsi-on.sql` zabija wszystkie otwarte transakcje w bazie (`ROLLBACK IMMEDIATE`) — uruchom po
zakończeniu pisarza.

## Prawdziwy output (skrót, SQL Server 2022 RTM-CU27, 16.0.4295.3)

```
02: B: BLAD 1205 - Transaction (Process ID 55) was deadlocked on lock resources with another process
    and has been chosen as the deadlock victim. Rerun the transaction.
    A: COMMIT - sesja A przezyla

03: spid  rola     czeka_na                                 tryb  izolacja
      55  OFIARA   KEY: 5:72057594045726720 (8194443284a0)  X    read committed (2)
      54  przezyl  KEY: 5:72057594045726720 (61a06abd401c)  X    read committed (2)

04: A: COMMIT ; B: COMMIT   (brak 1205; saldo koncowe 990.00 / 1010.00)

05: RCSI_on = 0 -> READER: SELECT trwal 4762 ms (saldo 992.00, po commit pisarza)
    RCSI_on = 1 -> READER: SELECT trwal 0 ms    (saldo 991.00, ostatnia zatwierdzona wersja)

07: FactSales_CCI 33.6 MB | FactSales_Row 189.1 MB | FactSales_RowIx 344.1 MB
    rowgroupy CCI: COMPRESSED, 6 rowgroupow, 5 000 000 wierszy, 32.7 MB

08 (drugi przebieg, MAXDOP 1):
    Q1 rowstore ............ reads 24208  CPU 892 ms   (batch mode)
    Q1 rowstore NOBATCH .... reads 24208  CPU 3197 ms  (DISALLOW_BATCH_MODE)
    Q1 rowstore+covering ... reads 19826  CPU 2118 ms  (row mode)
    Q1 columnstore ......... lob reads 1254  CPU 27 ms  (segment reads 6, skipped 0)
    Q2 rowstore 24208 / 605 ms | +covering 19826 / 689 ms | columnstore 2249 lob / 15 ms
    Q3 (SaleId = 2500000): rowstore 3 reads | columnstore 1373 lob reads (segment skipped 4)

09: rowgroupy po sortowaniu: data_id 738520-738749, 738749-738979, 738979-739208, 739208-739438, 739438-739614
    Q2 posortowany: lob reads 743, Segment reads 1, skipped 4, CPU 10 ms (vs 2249 / skipped 0 / 15 ms)
```

## Status weryfikacji

**Zweryfikowane realnie:** skrypty `01`–`09` na kontenerze `mcr.microsoft.com/mssql/server:2022-latest`
(uruchamiane ręcznie po jednym, sesje A/B równolegle); liczby powyżej pochodzą z tych uruchomień.
Czasy w ms wahają się między przebiegami, logical reads są deterministyczne. Pomiary pojedyncze,
`MAXDOP 1` — rzędy wielkości, nie benchmark.

**Nie zweryfikowane:** `run-demo.sh` jako całość, `10-cleanup.sql`, widok grafu w SSMS, kolejność
blokad z `UPDLOCK` przy wielu wierszach, koszt RCSI, wyniki bez `MAXDOP 1`, nonclustered columnstore,
aktualizacje/DELETE w columnstore, poziom zgodności bazy (nie sprawdzany jawnie).
