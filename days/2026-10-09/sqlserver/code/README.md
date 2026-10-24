# Kod do wydania #16 — PSP z wieloma predykatami, hint wariantu vs rodzica, nieaktualne statystyki (NCCI)

Pełny artykuł: [`../ARTICLE.md`](../ARTICLE.md). Poniżej ten sam kod + jak go odpalić.

Wymagania: **Docker** (obraz `mcr.microsoft.com/mssql/server:2022-latest`). Lokalny `sqlcmd`
niepotrzebny — używamy `sqlcmd` z kontenera przez `docker exec`. Całość trwa kilka minut.
Skrypt `06` robi `DBCC FREEPROCCACHE` — **tylko na instancji testowej**.

## Fragment prasówki, którego dotyczy ten kod

> **PSP chroni jeden predykat.** `dbo.Ev` ma dwie skośne kolumny (`TenantId` 190 000:1,
> `Region` 179 999:1). W wariantach PSP (`predicate_range`) jest tylko `TenantId`, więc
> gigant-tenant + `Region = 2` robi 5 737 reads, a z `RECOMPILE` — 5. Test na czterech
> tabelach z różnymi rozkładami: PSP wybiera predykat o większym ilorazie max:min, nie
> pierwszy w `WHERE`; remis rozstrzygnął się na korzyść `Region` (reguła nieznana).
>
> **Hint wariantu wygrywa z rodzicem.** Sprzeczne `USE HINT` (`FORCE_LEGACY_…` vs
> `FORCE_DEFAULT_CARDINALITY_ESTIMATION`): wariant z własnym hintem dostaje swoją wersję CE
> (70 lub 160), wariant bez hintu dziedziczy rodzica. Efekt widać w planie w plan cache
> (`CardinalityEstimationModelVersion`, `QueryStoreStatementHintText`), nie w `sys.query_store_plan`.
>
> **`AUTO_UPDATE_STATISTICS OFF` + nowa wartość.** 1 000 000 wierszy + 600 000 z `Status = 7`:
> estymata 1 264,91 zamiast 600 000, plan szeregowy, 1 651 ms. Po `UPDATE STATISTICS … FULLSCAN`:
> estymata 600 000, DOP 2, 701 ms (2,3×).

## Pliki

| Plik | Co robi |
|---|---|
| `01-setup.sql` | Baza `PspMulti` (Query Store ON), `dbo.Ev` (200 000 wierszy; `TenantId`, `Region` skośne, `Kind` równomierna) + 3 indeksy. |
| `02-psp-multi.sql` | Sesja XE `psp_multi`, procedura `dbo.Szukaj`, cztery wywołania z `STATISTICS IO`, XE i `predicate_range` z plan cache. |
| `03-warianty.sql` | Warianty PSP w Query Store (`query_store_query_variant`). |
| `04-ktory-predykat.sql` | Tabele `EvC`–`EvF` (różne rozkłady i kolejności w `WHERE`): który predykat wchodzi do wariantów. |
| `05-skosnosc-i-cena.sql` | `max_skewness` z XE dla `EvC`–`EvF` + cena niechronionego predykatu na `Ev` (PSP vs `RECOMPILE`). |
| `06-hint-wariant-vs-rodzic.sql` | Scenariusze S0–S4: `USE HINT` na rodzicu / wariancie, odczyt z planu w plan cache. |
| `07-stale-setup.sql` | Baza `StaleLab` z `AUTO_UPDATE_STATISTICS OFF`, `Orders` 1 mln + NCCI, dosypanie 600 000 z `Status = 7`, `Customers`. |
| `08-stale-pomiar.sql` | Pomiar (`-v ETAP=…`): estymaty operatorów, grant, spille, DOP, czas. |
| `09-update-stats.sql` | `UPDATE STATISTICS … WITH FULLSCAN`. |
| `10-cleanup.sql` | Usuwa bazy demo i sesję XE. |
| `run-demo.sh` | Całość w jednym skrypcie (jako plik **niezweryfikowany**). |

## Jak odpalić (tak zostało zweryfikowane — ręcznie, krok po kroku)

Uruchom z katalogu `code/`:

```bash
docker run -d --rm --name prasowka16-sqlserver \
  -e ACCEPT_EULA=Y -e 'MSSQL_SA_PASSWORD=Prasowka_Demo_123!' \
  mcr.microsoft.com/mssql/server:2022-latest

docker exec prasowka16-sqlserver mkdir -p /tmp/code
docker cp . prasowka16-sqlserver:/tmp/code/

# poczekaj kilkanaście sekund na start serwera; -I (QUOTED_IDENTIFIER ON) potrzebne do XQuery .value()
SQLCMD="docker exec prasowka16-sqlserver /opt/mssql-tools18/bin/sqlcmd -S localhost -U sa -P Prasowka_Demo_123! -C -I -W -b"

for f in 01-setup 02-psp-multi 03-warianty 04-ktory-predykat 05-skosnosc-i-cena 06-hint-wariant-vs-rodzic; do
  $SQLCMD -i /tmp/code/$f.sql
done

$SQLCMD -i /tmp/code/07-stale-setup.sql
$SQLCMD -v ETAP=nieaktualne -i /tmp/code/08-stale-pomiar.sql
$SQLCMD -i /tmp/code/09-update-stats.sql
$SQLCMD -v ETAP=swieze -i /tmp/code/08-stale-pomiar.sql

$SQLCMD -i /tmp/code/10-cleanup.sql
docker rm -f -v prasowka16-sqlserver
```

Uwagi: `02` musi być przed `03` i `05` (sesja XE `psp_multi`, procedura `Szukaj`); `05` wymaga `04`.
Wywołań procedur z PSP nie owijaj w `INSERT … EXEC` (fałszywy negatyw, patrz #14).

## Prawdziwy output (SQL Server 2022 RTM-CU27, 16.0.4295.3) — skrót

```
01: Region 1 -> 179999, Region 2 -> 1; TenantId 1 -> 190000, TenantId 2 -> 1; compat 160

02: (1,1,5) reads 5737 | (2,2,5) reads 5 | (2,1,5) reads 5 | (1,2,5) reads 5737
    XE: query_with_parameter_sensitivity max_skewness 190000
    plan cache: QueryVariantID = 1 i 3, oba z predicate_range([..].[Ev].[TenantId] = @TenantId, 100.0, 100000.0)

04: EvC (T 150000:1, R 199999:1; WHERE T,R)  -> predicate_range ... [EvC].[Region]
    EvD (T 190000:1, R 190000:1; WHERE T,R)  -> ... [EvD].[Region]
    EvE (T 150000:1, R 199999:1; WHERE R,T)  -> ... [EvE].[Region]
    EvF (T 190000:1, R 179999:1; WHERE R,T)  -> ... [EvF].[TenantId]

05: max_skewness (EvC, EvD, EvE, EvF) = 199999, 190000, 199999, 190000
    Ev (1,2,5) przez procedure z PSP: 5737 reads; z OPTION (RECOMPILE): 5 reads

06: S0 bez hintow          : wariant 1 -> 160, wariant 3 -> 160
    S1 LEGACY na rodzicu   : 70, 70 (hint_z_planu LEGACY, zrodlo User)
    S2 rodzic LEGACY + w3 DEFAULT: w1 70, w3 160
    S3 rodzic DEFAULT + w3 LEGACY: w1 160, w3 70
    S4 tylko w3 LEGACY     : w1 160 (bez hintu), w3 70; pozostale_hinty 0

07: AUTO_UPDATE_STATISTICS OFF; stat Status/CustomerId: rows 1000000, modification_counter 600000; tabela 1600000, status7 600000
08 nieaktualne: estymata Index Scan 1264.91, Adaptive Join (Row), DOP 1, grant 245040 KB (uzyto 82952), spille 0, 1651 ms (powtorka 1643 ms)
09:             stat rows 1600000 / rows_sampled 1600000, modification_counter 0
08 swieze:      estymata Index Scan 600000, Adaptive Join (Batch), DOP 2, grant 435416 KB (uzyto 200704), spille 0, 701 ms (pierwszy kontener: 727 ms)
```

## Status weryfikacji

**Zweryfikowane realnie:** skrypty `01`–`10` wykonane ręcznie przez `docker exec … sqlcmd`,
dwa razy od zera (dwa kontenery) z tymi samymi liczbami (czasy: 1664/1651 ms vs 727/701 ms).

**Nie zweryfikowane:**
- `run-demo.sh` jako całość — uruchomienie pliku `.sh` odrzucone przez uprawnienia sandboksa.
- PSP z dwoma predykatami w jednym wariancie; reguła rozstrzygania remisu (`EvD`); hipoteza „wygrywa większy iloraz" z 4–5 tabel.
- Pierwszeństwo hintu wariantu przy odwrotnej kolejności ustawiania; inne hinty niż `USE HINT` (CE).
- Spill z powodu zaniżonego grantu (w naszym zapytaniu nie wystąpił); udział samej równoległości w zysku 2,3×.
- Mechanizm czyszczenia `TOMBSTONE`; dokładny próg skośności PSP (95 000–100 000).
