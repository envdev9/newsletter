# Kod do wydania #8 — UPDATE/DELETE na NCCI i Query Store hints (sp_query_store_set_hints)

Pełny artykuł: [`../ARTICLE.md`](../ARTICLE.md). Poniżej ten sam kod + jak go odpalić.

Wymagania: **Docker** (obraz `mcr.microsoft.com/mssql/server:2022-latest`). Lokalny
`sqlcmd` niepotrzebny — używamy `sqlcmd` z kontenera przez `docker exec`.

## Fragment prasówki, którego dotyczy ten kod

> **DELETE na NCCI:** tabela `dbo.Orders` (1 200 000 wierszy, `NCCI_Orders` obok
> klucza klastrowanego) dostaje realny `DELETE FROM dbo.Orders WHERE Status = 3`
> (300 000 wierszy). Zapytanie przez NCCI natychmiast zwraca poprawne 900 000
> wierszy — ale `sys.column_store_row_groups.deleted_rows` pokazuje **0** we
> wszystkich rowgroupach, nawet po `CHECKPOINT` i 15 s oczekiwania. `UPDATE` 15 000
> wierszy dowodzi mechanizmu DELETE+INSERT: nowy rowgroup `OPEN` pojawia się
> natychmiast z `total_rows` dokładnie równym liczbie zaktualizowanych wierszy, a
> stare wersje nadal nie są widoczne w `deleted_rows`. Dopiero `ALTER INDEX ...
> REORGANIZE` **ujawnia** prawdziwą liczbę martwych wierszy (275 610 w największym
> rowgroupie — 26,3%!) i scala małe rowgroupy, kompaktując je — ale NIE dotyka
> dużego, już pełnego rowgroupu. Rozmiar indeksu: 17,58 MB → 13,80 MB po
> REORGANIZE → **6,63 MB** po `REBUILD` (jedyna operacja, która daje pełny reclaim).
>
> **`sp_query_store_set_hints`:** zweryfikowane, że istnieje w SQL Server 2022
> RTM-CU27. Na tabeli `dbo.Events` (200 000 wierszy, `TenantId=1` ma 95% danych)
> procedura `dbo.GetEventsByTenant` dostaje zły, reużywany plan: 3141 logical
> reads dla obu tenantów (1 i 2), mimo że tenant 2 ma tylko 100 wierszy.
> `EXEC sys.sp_query_store_set_hints @query_id=6, @query_hints=N'OPTION(RECOMPILE)'`
> + `sp_recompile` — i bez zmiany ani linii kodu procedury: tenant 2 dostaje WŁASNY
> plan, **318** logical reads (10x mniej). Query Store pokazuje dwa różne `plan_id`
> dla jednego `query_id` po hincie.

## Pliki

| Plik | Co robi |
|---|---|
| `01-setup-ncci.sql` | Baza `PrasowkaNcciDml`, tabela OLTP `dbo.Orders` (klucz klastrowany, 1 200 000 wierszy, 300 000 ze `Status=3`). |
| `02-create-ncci.sql` | `CREATE NONCLUSTERED COLUMNSTORE INDEX` + stan rowgroupów. |
| `03-analytics-baseline.sql` | Baseline kosztu agregacji `GROUP BY CustomerId` PRZED jakimkolwiek DELETE/UPDATE. |
| `04-delete-large-chunk.sql` | `DELETE FROM dbo.Orders WHERE Status=3` (300 000 wierszy) + stan rowgroupów przed/po + `COUNT(*)` vs `SUM(total_rows/deleted_rows)`. |
| `05-analytics-after-delete.sql` | Ten sam raport co w `03`, teraz po DELETE. |
| `06-update-rows.sql` | `UPDATE` 15 000 wierszy (`Status 0→1`, `CustomerId 1..2000`) + stan rowgroupów przed/po (dowód DELETE+INSERT). |
| `07-reorganize.sql` | Rozmiar indeksu przed/po `ALTER INDEX ... REORGANIZE WITH (COMPRESS_ALL_ROW_GROUPS=ON)` + stan rowgroupów (ujawnienie `deleted_rows`, scalenie małych rowgroupów). |
| `08-analytics-after-reorganize.sql` | Ten sam raport co w `03/05`, teraz po REORGANIZE. |
| `09-rebuild.sql` | `ALTER INDEX ... REBUILD` + stan rowgroupów/rozmiar PO (pełny reclaim). |
| `10-analytics-after-rebuild.sql` | Ten sam raport co w `03/05/08`, teraz po REBUILD. |
| `11-setup-queryhints.sql` | Baza `PrasowkaQueryHints`, tabela `dbo.Events` (skośny rozkład, Query Store ON od razu), procedura `dbo.GetEventsByTenant`. |
| `12-prime-bad-plan.sql` | Zatruwanie plan cache: `EXEC` z tenantem 1 (190 000 wierszy), potem tenant 2 (100 wierszy) — reuse złego planu. |
| `13-apply-query-store-hint.sql` | Znalezienie `query_id`, `sp_query_store_set_hints` (`OPTION(RECOMPILE)`), `sp_recompile`. |
| `14-verify-after-hint.sql` | Weryfikacja: każde wywołanie dostaje własny plan; `sys.query_store_plan` pokazuje dwa `plan_id` dla jednego `query_id`. |
| `15-cleanup.sql` | Usunięcie obu baz demo. |
| `run-demo.sh` | Całość w jednym skrypcie (uruchomienie **jako całość** odrzucone przez uprawnienia sandboksa w tej sesji — patrz niżej; wszystkie kroki zweryfikowane ręcznie). |

## Jak odpalić (tak zostało zweryfikowane — ręcznie, krok po kroku)

```bash
docker run -d --rm --name sqlserver-prasowka-sqlserver8 \
  -e ACCEPT_EULA=Y -e 'MSSQL_SA_PASSWORD=Prasowka_Demo_123!' \
  -p 14344:1433 mcr.microsoft.com/mssql/server:2022-latest

docker cp . sqlserver-prasowka-sqlserver8:/tmp/code

SQLCMD="docker exec sqlserver-prasowka-sqlserver8 /opt/mssql-tools18/bin/sqlcmd -S localhost -U sa -P Prasowka_Demo_123! -C -b"

# --- CZĘŚĆ 1: UPDATE/DELETE na NCCI ---
$SQLCMD -i /tmp/code/01-setup-ncci.sql
$SQLCMD -i /tmp/code/02-create-ncci.sql
$SQLCMD -i /tmp/code/03-analytics-baseline.sql
$SQLCMD -i /tmp/code/04-delete-large-chunk.sql
$SQLCMD -i /tmp/code/05-analytics-after-delete.sql
$SQLCMD -i /tmp/code/06-update-rows.sql
$SQLCMD -i /tmp/code/07-reorganize.sql
$SQLCMD -i /tmp/code/08-analytics-after-reorganize.sql
$SQLCMD -i /tmp/code/09-rebuild.sql
$SQLCMD -i /tmp/code/10-analytics-after-rebuild.sql

# --- CZĘŚĆ 2: Query Store hints ---
$SQLCMD -i /tmp/code/11-setup-queryhints.sql
$SQLCMD -i /tmp/code/12-prime-bad-plan.sql
$SQLCMD -i /tmp/code/13-apply-query-store-hint.sql
$SQLCMD -i /tmp/code/14-verify-after-hint.sql

$SQLCMD -i /tmp/code/15-cleanup.sql
docker rm -f sqlserver-prasowka-sqlserver8
```

Uwaga: `query_id = 6` w `13-apply-query-store-hint.sql` zostało ustalone empirycznie
na tym konkretnym przebiegu (pierwsze "użytkowe" zapytanie zarejestrowane w Query
Store dla tej bazy). Jeśli odpalasz od zera i numeracja wypadnie inaczej, podstaw
`query_id` znaleziony przez pierwszy `SELECT` w tym samym skrypcie (filtr po
`q.object_id = OBJECT_ID('dbo.GetEventsByTenant')`).

## Prawdziwy output (SQL Server 2022 RTM-CU27, 16.0.4295.3)

```
02: row_group_id state_description total_rows deleted_rows size_in_bytes
    0            COMPRESSED        1048576    0            7704184
    1            COMPRESSED        38136      0            308432
    2            COMPRESSED        113288     0            873864

03 (baseline): 40000 grup, Suma=540904500.00, WierszyRazem=1200000
    lob logical reads 1536, Segment reads 3 skipped 0, CPU 115-120 ms / elapsed 128-133 ms

04 (DELETE Status=3, 300000 wierszy): logical reads 906055 (clustered scan), CPU ~3000 ms
    PO DELETE: rowgroupy BEZ ZMIAN (0/0/0 deleted_rows, total_rows identyczne jak przed)
    COUNT(*) FROM dbo.Orders = 900000 (poprawne!), SUM(total_rows)=1200000, SUM(deleted_rows)=0

05 (raport po delete): 30000 grup, Suma=405679800.00, WierszyRazem=900000 (poprawne)
    lob logical reads 1106 (vs 1536 baseline), Segment reads 3 skipped 0, CPU 233-235 ms / elapsed 239-242 ms

06 (UPDATE 15000 wierszy Status 0->1, CustomerId 1..2000): logical reads 50302, CPU 530-536 ms
    PO UPDATE: nowy rowgroup 3 OPEN, total_rows=15000, deleted_rows=NULL (delta store)
    rowgroupy 0/1/2: BEZ ZMIAN, deleted_rows wciaz 0/0/0

07 (REORGANIZE WITH COMPRESS_ALL_ROW_GROUPS=ON):
    Rozmiar PRZED: NCCI_Orders 17.578125 MB used / 17.773437 MB reserved; PK_Orders 39.5 MB
    PO REORGANIZE:
        0  COMPRESSED  total=1048576  deleted=275610   <- UJAWNIONE, nie scalone/skompaktowane
        1  TOMBSTONE   total=38136    deleted=9568
        2  TOMBSTONE   total=113288   deleted=29822
        3  TOMBSTONE   total=15000    deleted=NULL
        4  COMPRESSED  total=15000    deleted=0         <- byl delta store, teraz skompresowany
        5  COMPRESSED  total=112034   deleted=0         <- SCALENIE 1+2 BEZ martwych wierszy: (38136-9568)+(113288-29822)=112034
    Rozmiar PO: NCCI_Orders 13.804687 MB used / 14.085937 MB reserved; PK_Orders 39.5 MB (bez zmian)

08 (raport po reorganize): 30000 grup, Suma=405679800.00, WierszyRazem=900000
    lob logical reads 1251, Segment reads 3 skipped 0, CPU 89 ms / elapsed 92 ms

09 (REBUILD): jeden rowgroup COMPRESSED, total_rows=900000, deleted_rows=0, size=6633496 bytes
    Rozmiar PO: NCCI_Orders 6.632812 MB used / 6.757812 MB reserved; PK_Orders 39.5 MB (bez zmian)

10 (raport po rebuild): 30000 grup, Suma=405679800.00, WierszyRazem=900000
    lob logical reads 1704 (physical reads 2 - cold cache), Segment reads 1 skipped 0, CPU 78 ms / elapsed 88-89 ms

11: TenantId=1 -> 190000 wierszy, TenantId=2 -> 100 wierszy, WierszyRazem=200000

12 (PRZED hintem):
    EXEC @TenantId=1: Table 'Events'. logical reads 3141 (kompiluje plan)
    EXEC @TenantId=2: Table 'Events'. logical reads 3141  <- IDENTYCZNE, zly reuzyty plan

13 (sp_query_store_set_hints):
    query_id=6 znaleziony dla dbo.GetEventsByTenant
    EXEC sys.sp_query_store_set_hints @query_id=6, @query_hints=N'OPTION(RECOMPILE)' -> sukces
    sys.query_store_query_hints: query_hint_text='OPTION(RECOMPILE)', source_desc='User',
        last_query_hint_failure_reason_desc='NONE'
    sp_recompile 'dbo.GetEventsByTenant' -> "successfully marked for recompilation"

14 (PO hincie):
    EXEC @TenantId=1: Table 'Events'. logical reads 3141 (ten sam, wlasciwy plan dla 95% selektywnosci)
    EXEC @TenantId=2: Table 'Events'. logical reads 318   <- NOWY plan, 10x mniej reads!
    sys.query_store_plan dla query_id=6: plan_id=6 (3 wykonania, stary/wspolny plan),
                                          plan_id=15 (1 wykonanie, NOWY plan dla tenanta 2)
```

## Status weryfikacji

**Zweryfikowane realnie:** skrypty `01`–`15` na kontenerze
`mcr.microsoft.com/mssql/server:2022-latest` (16.0.4295.3, RTM-CU27), uruchamiane
ręcznie przez `docker exec ... sqlcmd -i`. Sekwencja `01`→`10` (NCCI) przepuszczona
**dwa razy od zera** z identycznym wynikiem; kluczowe zjawisko ("`deleted_rows`
zostaje na zero po realnym DELETE") dodatkowo potwierdzone **osobno**, na
niezależnej minimalnej tabeli (5000 wierszy / 500 skasowanych), z `CHECKPOINT` i
15-sekundowym oczekiwaniem między pomiarami — żeby wykluczyć, że to tylko
cache/timing jednego przebiegu. Sekwencja `11`→`14` (Query Store hints)
przepuszczona raz w pełni, z potwierdzeniem w `sys.query_store_query_hints` i
`sys.query_store_plan`.

**Nie zweryfikowane:**
- `run-demo.sh` **jako całość** — `chmod +x`/uruchomienie samego pliku `.sh`
  odrzucone przez uprawnienia sandboksa w tej sesji (znany problem z poprzednich
  wydań); wszystkie kroki, które on wykonuje, zweryfikowane ręcznie.
- Dokładny mechanizm/harmonogram odświeżania `deleted_rows` w tle — sprawdziliśmy,
  że `CHECKPOINT` + 15 s + pełne skany NIE go odświeżają, a `REORGANIZE`/`REBUILD`
  TAK, ale nie wiemy, czy istnieje inny, wolniejszy mechanizm w tle (np. jakiś
  interwał Tuple Movera), którego po prostu nie było czasu przetestować dłużej.
- Ghost cleanup wierszy usuniętych z `PK_Orders` (rowstore) — rozmiar pozostał
  39,5 MB przez cały przebieg, nie sprawdzono, kiedy/czy proces w tle go posprząta.
- `sp_query_store_clear_hints` (istnienie potwierdzone, działanie nie przetestowane),
  interakcja hintu z `sp_query_store_force_plan` na tym samym `query_id`, zachowanie
  przy więcej niż dwóch różnych "kształtach" parametru wywołania.
- Parameter Sensitive Plan (PSP): `compatibility_level=160` i
  `PARAMETER_SENSITIVE_PLAN_OPTIMIZATION=1` potwierdzone realnie (oba warunki
  spełnione), ale nowe repro scenariusza z #3 nie zostało wykonane w tym wydaniu.
