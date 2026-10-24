# Kod do wydania #14 — dlaczego PSP nie ruszał, hinty Query Store na PSP, columnstore: TOMBSTONE i statystyki

Pełny artykuł: [`../ARTICLE.md`](../ARTICLE.md). Poniżej ten sam kod + jak go odpalić.

Wymagania: **Docker** (obraz `mcr.microsoft.com/mssql/server:2022-latest`). Lokalny
`sqlcmd` niepotrzebny — używamy `sqlcmd` z kontenera przez `docker exec`. Pełny przebieg
trwa ok. 10 minut (5 minut to obserwacja `TOMBSTONE` w pliku `17`).

## Fragment prasówki, którego dotyczy ten kod

> **PSP „nie działa", bo dane nie są dość skośne.** Przyczyna z #3/#8 znaleziona przez
> Extended Event `parameter_sensitive_plan_optimization_skipped_reason`:
> `SkewnessThresholdNotMet`. Tabela 200 000 wierszy, gigant 190 000, reszta po 100 (iloraz
> 1 900) — brak PSP, mały tenant dostaje cudzy plan: 5 166 reads. Bisekcja: PSP rusza
> dopiero przy ilorazie max/min w histogramie ≥ 100 000 (95 000 jeszcze nie; wniosek z
> eksperymentu, nie z dokumentacji). Po spełnieniu progu: mały tenant 5 166 → **5** reads.
>
> **Query Store hint na zapytaniu z PSP:** hint jest przypięty do `query_id`. `OPTIMIZE FOR
> UNKNOWN` tylko na wariancie dużego tenanta: 5 161 → **582 215** reads (mały bez zmian);
> ten sam hint na rodzicu dziedziczą warianty. `OPTION(RECOMPILE)` na rodzicu wyłącza PSP
> (`WithRecompileFlag`). `TABLE HINT` i `OPTIMIZE FOR (@p=…)` — błąd 12455.
>
> **Columnstore po `REORGANIZE`/`REBUILD`:** rowgroupy `TOMBSTONE` znikają same po ok.
> 3,5–4 min (2 pomiary), `REBUILD` czyści od razu. Auto-update statystyk po `DELETE` 300 000
> zadziałał przy następnym zapytaniu (`rows` 1 200 000 → 900 000, estymata 948,683), ale
> `REORGANIZE`/`REBUILD` statystyk **nie odświeżają**: po `DELETE TOP (20000)` + `REBUILD`
> statystyka dalej mówi `rows = 900000` (tabela: 880 000) do czasu `UPDATE STATISTICS`.

## Pliki

| Plik | Co robi |
|---|---|
| `01-setup-psp.sql` | Baza `PspLab`, `dbo.Events` (200 000 wierszy, `TenantId=1` ma 190 000), wersja, compat level, `PARAMETER_SENSITIVE_PLAN_OPTIMIZATION`. |
| `02-psp-baseline.sql` | Query Store ON, procedura z #8: duży tenant, potem mały — ten sam plan, brak PSP. |
| `03-psp-diagnoza.sql` | Słownik powodów pominięcia PSP + sesja XE `psp_diag` (ring_buffer) → `SkewnessThresholdNotMet`. |
| `04-psp-rozklady.sql` | Trzy rozkłady danych (A: nasz, B/C: z wartościami unikalnymi) — który jest kandydatem PSP. |
| `05-psp-prog-skosnosci.sql` | Gigant 190 000, mali po k = 1, 2, 3, 5, 10, 100 wierszy. |
| `06-psp-prog-ratio.sql` | Pary (g, k): iloraz vs „k = 1" jako hipotezy progu. |
| `07-psp-dziala.sql` | Ta sama procedura na `Ev_k2` (bez PSP) i `Ev_k1` (z PSP): logical reads + warianty w plan cache. |
| `08-psp-query-store-hints.sql` | `query_store_query_variant`; hint na wariancie, na rodzicu, `RECOMPILE` na rodzicu. |
| `10-setup-ncci.sql` | Baza `NcciClean`, `dbo.Orders` 1 200 000 wierszy + NCCI. |
| `11-stats-snapshot.sql` | Statystyki, rowgroupy, zapytanie kontrolne (`/*kontrola*/`) i estymata z planu (`-v ETAP=...`). |
| `12-delete.sql` | `DELETE … WHERE Status = 3` (300 000). |
| `13-reorganize.sql` / `14-rebuild.sql` | `ALTER INDEX NCCI_Orders … REORGANIZE (COMPRESS_ALL_ROW_GROUPS=ON)` / `REBUILD`. |
| `15-small-delete.sql` | `DELETE TOP (20000) … Status = 2` — poniżej progu auto-update. |
| `16-stats-only.sql` | Statystyki + rowgroupy, bez zapytania kontrolnego (nie wywołuje auto-update). |
| `17-tombstone-watch.sql` | Co 15 s przez 5 min liczy rowgroupy `TOMBSTONE`. |
| `18-update-statistics.sql` | `UPDATE STATISTICS … WITH FULLSCAN` po REBUILD. |
| `19-cleanup.sql` | Usuwa bazy demo i sesję XE. |
| `run-demo.sh` | Całość w jednym skrypcie (jako całość **niezweryfikowany** — patrz niżej). |

## Jak odpalić (tak zostało zweryfikowane — ręcznie, krok po kroku)

Uruchom wszystko z katalogu `code/`:

```bash
docker run -d --rm --name prasowka14-sqlserver \
  -e ACCEPT_EULA=Y -e 'MSSQL_SA_PASSWORD=Prasowka_Demo_123!' \
  mcr.microsoft.com/mssql/server:2022-latest

docker exec prasowka14-sqlserver mkdir -p /tmp/code
docker cp . prasowka14-sqlserver:/tmp/code/

# -I (QUOTED_IDENTIFIER ON) jest wymagane przez XQuery .value(); -W obcina padding kolumn
SQLCMD="docker exec prasowka14-sqlserver /opt/mssql-tools18/bin/sqlcmd -S localhost -U sa -P Prasowka_Demo_123! -C -I -W -b"

# --- CZĘŚĆ 1: PSP ---
for f in 01-setup-psp 02-psp-baseline 03-psp-diagnoza 04-psp-rozklady 05-psp-prog-skosnosci \
         06-psp-prog-ratio 07-psp-dziala 08-psp-query-store-hints; do
  $SQLCMD -i /tmp/code/$f.sql
done

# --- CZĘŚĆ 2: columnstore ---
$SQLCMD -i /tmp/code/10-setup-ncci.sql
$SQLCMD -v "ETAP=po buildzie"        -i /tmp/code/11-stats-snapshot.sql
$SQLCMD -i /tmp/code/12-delete.sql
$SQLCMD -v "ETAP=po DELETE 300000"   -i /tmp/code/11-stats-snapshot.sql
$SQLCMD -i /tmp/code/13-reorganize.sql
$SQLCMD -v "ETAP=po REORGANIZE"      -i /tmp/code/16-stats-only.sql
$SQLCMD -i /tmp/code/17-tombstone-watch.sql          # 5 minut
$SQLCMD -i /tmp/code/14-rebuild.sql
$SQLCMD -v "ETAP=po REBUILD"         -i /tmp/code/16-stats-only.sql
$SQLCMD -i /tmp/code/15-small-delete.sql
$SQLCMD -v "ETAP=po malym DELETE"    -i /tmp/code/16-stats-only.sql
$SQLCMD -i /tmp/code/14-rebuild.sql
$SQLCMD -v "ETAP=po drugim REBUILD"  -i /tmp/code/16-stats-only.sql
$SQLCMD -i /tmp/code/18-update-statistics.sql

$SQLCMD -i /tmp/code/19-cleanup.sql
docker rm -f -v prasowka14-sqlserver
```

Uwagi: `08` korzysta ze stanu Query Store z `07` (uruchamiaj po kolei); `03` tworzy sesję XE
używaną przez `04`–`06` i `08`. Przy `sqlcmd -v` nie wkładaj do wartości nawiasów ani `=`
(próba z `-v OPERACJA="REORGANIZE WITH (…)"` zepsuła składnię — stąd osobne pliki 13 i 14).

## Prawdziwy output (SQL Server 2022 RTM-CU27, 16.0.4295.3)

```
01: compat 160, PARAMETER_SENSITIVE_PLAN_OPTIMIZATION = 1; TenantId 1 -> 190000, 2 -> 100, 3 -> 100

02: EXEC @TenantId=1: Table 'Events' logical reads 5427; EXEC @TenantId=2: logical reads 5427
    psp_w_planie: NIE - zwykly plan, execution_count 2

03: XE: parameter_sensitive_plan_optimization_skipped_reason = SkewnessThresholdNotMet
    (oraz UnsupportedStatementType dla zewnetrznego INSERT..EXEC)
    slownik psp_skipped_reason_enum: 40 wartosci (0 None ... 39 FmtOnly), m.in. 30 SkewnessThresholdNotMet,
    6 WithRecompileFlag, 33 UnsupportedStatementType

04 (kolejnosc zdarzen = kolejnosc tabel A, B, C):
    SkewnessThresholdNotMet
    query_with_parameter_sensitivity: interesting=1, max_skewness=100000, supported=true
    query_with_parameter_sensitivity: interesting=1, max_skewness=190000, supported=true

05 (gigant 190000, k = rowow na malego tenanta):
    k=1   -> query_with_parameter_sensitivity, max_skewness 190000
    k=2,3,5,10,100 -> SkewnessThresholdNotMet

06: g=1000/10000/50000 przy k=1, g=100000 przy k=2 -> SkewnessThresholdNotMet

07: Ev_k2 (bez PSP): duzy 5166 reads, maly 5166 reads
    Ev_k1 (z PSP):   duzy 5161 reads, maly 5 reads
    plan cache: 2 x "wariant" Ev_k1 (QueryVariantID = 1 i 3), Ev_k2: zwykly plan, 2 wykonania

08: query_store_query_variant: parent_query_id 2 -> warianty 3 (QueryVariantID = 3), 4 (QueryVariantID = 1)
    krok 1 bez hintow:                     duzy 5161, maly 5
    krok 2 OPTIMIZE FOR UNKNOWN na wariancie 3: duzy 582215, maly 5; query_store_query_hints: query_id 3
    krok 3 ten sam hint na rodzicu:        duzy 582215, maly 6;      query_store_query_hints: query_id 2
    krok 4 RECOMPILE na rodzicu:           duzy 5161, maly 5;        XE: WithRecompileFlag 6
    proby: TABLE HINT / OPTIMIZE FOR (@p=1) -> Msg 12455 "... in Query Store is not supported"

10: Status 0/1/2/3 -> po 300000 wierszy

11 po buildzie:       _WA_Sys_..._Status rows 1200000, zmian 0; rowgroupy 1048576/85519/65905 (kolejnosc id moze sie zmieniac)
                      count_faktyczny 300000; estymata Index Scan 299297 (1. przebieg) / 299321 (2. przebieg)
12:                   skasowano 300000
11 po DELETE:         PRZED zapytaniem: rows 1200000, zmian 300000, deleted_rows 0/0/0
                      count_faktyczny 0; PO zapytaniu: rows 900000, zmian 0, last_updated przesuniete; estymata 948.683
13+16 po REORGANIZE:  0 COMPRESSED 1048576 deleted 262144 | 1 TOMBSTONE 85519/21380 | 2 TOMBSTONE 65905/16476
                      | 3 COMPRESSED 113568/0; statystyka bez zmian (rows 900000, zmian 0)
17 (przebieg 1):      TOMBSTONE=2 do t+225s, 1 przy t+240s, 0 od t+255s
17 (przebieg 2):      TOMBSTONE=2 do t+195s, 0 od t+210s; zostaje rg 0 (deleted 262144) + rg 3 (113568)
14+16 po REBUILD:     1 rowgroup COMPRESSED 900000/0; statystyka: rows 900000, zmian 0, last_updated bez zmian
15:                   skasowano 20000
16 po malym DELETE:   statystyka: rows 900000, zmian 20000, last_updated bez zmian
14+16 po 2. REBUILD:  1 rowgroup 880000/0; statystyka: rows 900000, zmian 20000 (BEZ ZMIAN)
18 UPDATE STATISTICS: PK_Orders rows 880000/880000, _WA_Sys_..._Status rows 880000/880000, zmian 0
```

## Status weryfikacji

**Zweryfikowane realnie:** skrypty `01`–`19` wykonane ręcznie przez `docker exec ... sqlcmd`,
**dwa razy od zera** (drugi raz na nowym kontenerze) z tymi samymi liczbami; różnice:
estymata po buildzie (299 297 vs 299 321) i moment zniknięcia `TOMBSTONE` (patrz wyżej).

**Nie zweryfikowane:**
- `run-demo.sh` jako całość — uruchomienie pliku `.sh` odrzucone przez uprawnienia sandboksa;
  kroki wykonano ręcznie w tej samej kolejności.
- Wzór i dokładny próg skośności PSP (hipoteza z 6 punktów; nic między 95 000 a 100 000).
- Pierwszeństwo hintu wariantu nad hintem rodzica; inne hinty QS niż `OPTIMIZE FOR UNKNOWN`/`RECOMPILE`.
- Mechanizm w tle usuwający `TOMBSTONE` (mierzony tylko czas, 2 razy, co 15 s).
- Próg auto-update statystyk (`SQRT(1000·N)`) — z dokumentacji, nie zmierzony.
- Wpływ nieaktualnych statystyk po `REBUILD` na plan/czas (przy 2% nieaktualności pominięty).
