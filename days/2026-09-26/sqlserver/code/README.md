# Kod do wydania #3 — RECOMPILE, OPTIMIZE FOR, Query Store, filtered index

Pełny artykuł: [`../ARTICLE.md`](../ARTICLE.md). Poniżej ten sam kod + jak go odpalić.

Wymagania: **Docker** (obraz `mcr.microsoft.com/mssql/server:2022-latest`). Lokalny
`sqlcmd` niepotrzebny — używamy `sqlcmd` z kontenera przez `docker exec`.

## Fragment prasówki, którego dotyczy ten kod

> Parameter sniffing z #2 (21 vs 600 350 odczytów) da się leczyć na cztery sposoby.
> `OPTION (RECOMPILE)` daje idealny plan za każdym razem (21 / 2 486), ale kosztuje
> kompilację (2000 wywołań: 574 ms vs 5 414 ms). `OPTIMIZE FOR UNKNOWN` to pułapka:
> plan pod średnią (szacunek 10 wierszy) nadal daje hurtownikowi 600 350 odczytów.
> `OPTIMIZE FOR (@p = 1)` to świadomy kompromis (2 486 dla wszystkich). **Query Store**
> zapisuje plany trwale: to samo `query_id` miało dwa plany (średnio 400 240 vs 2 486
> odczytów, 560 ms vs 69 ms), a `sp_query_store_force_plan` przypiął dobry plan bez
> zmiany kodu — hurtownik dostał 2 486 zamiast 600 350. **Filtered index**
> (`WHERE Status = 0`) dla 500 z 500 000 zadań ma 2 strony zamiast 1 051 — ale pomijany
> jest przy zapytaniu z parametrem, chyba że dodasz `OPTION (RECOMPILE)`.

## Pliki

| Plik | Co robi |
|---|---|
| `01-create-data.sql` | Baza `PrasowkaQS`: `dbo.Orders` (500 000 wierszy, skośna, wąski indeks) i `dbo.Tasks` (500 000 zadań, 500 oczekujących). |
| `02-recompile-optimize-for.sql` | Cztery procedury (`usp_Plain`, `_Recompile`, `_OptForUnknown`, `_OptForWhale`), `STATISTICS IO`, plan z `EstimateRows`, pomiar kosztu kompilacji. |
| `03-query-store.sql` | Włączenie Query Store, dwa plany dla jednego zapytania, zapytanie po `sys.query_store_*`. |
| `04-force-plan.sql` | `sp_query_store_force_plan`, test po wymuszeniu, `unforce`. Wymaga `03`. |
| `05-filtered-index.sql` | Brak indeksu vs zwykły vs filtered; rozmiary; pułapka z parametrem. |
| `06-cleanup.sql` | Opcjonalne usunięcie bazy. |
| `run-demo.sh` | Stawia kontener, uruchamia `01`→`05`, usuwa kontener. |

## Jak odpalić

```bash
bash run-demo.sh
```

Ręcznie (tak zostało zweryfikowane):

```bash
docker run -d --name sqlserver-prasowka-qs \
  -e ACCEPT_EULA=Y -e 'MSSQL_SA_PASSWORD=Prasowka#2026!' \
  mcr.microsoft.com/mssql/server:2022-latest

docker cp . sqlserver-prasowka-qs:/tmp/code

# skrypty po kolei (-I = QUOTED_IDENTIFIER ON, wymagane dla filtered index):
docker exec sqlserver-prasowka-qs /opt/mssql-tools18/bin/sqlcmd \
  -S localhost -U sa -P 'Prasowka#2026!' -C -b -I -y 40 -i /tmp/code/01-create-data.sql
# ... analogicznie 02, 03, 04, 05

docker rm -f sqlserver-prasowka-qs
```

## Prawdziwy output (skrót, SQL Server 2022 RTM-CU27, 16.0.4295.3)

```
02: usp_Plain          4242 -> 21    hurtownik -> 600350
    usp_Recompile      4242 -> 21    hurtownik -> 2486
    usp_OptForUnknown  4242 -> 21    hurtownik -> 600350   (EstimateRows = 10.0)
    usp_OptForWhale    4242 -> 2486  hurtownik -> 2486
    2000 wywolan (4242): Plain 574 ms, Recompile 5414 ms

03: query_id plan_id Wykonan AvgLogicalReads AvgDurationMs RodzajPlanu
           2       2       3          400240         560.1 Seek + Key Lookup
           2       3       3            2486          69.2 Clustered Index Scan

04: force query_id=2, plan_id=3
    po force (rzadki pierwszy): 4242 -> 2486, hurtownik -> 2486 (bez force: 600350)

05: (a) bez indeksu ........ logical reads 6846 (skan rownolegly)
    (b) (Status, CreatedAt)  logical reads 3, indeks 1051 stron / 500000 wierszy
    (c) filtered ........... logical reads 2, indeks 2 strony / 500 wierszy
    (d) @s parametr ........ 6846 (filtered index pominiety)
    (e) + RECOMPILE ........ 2
```

## Status weryfikacji

**Zweryfikowane realnie:** skrypty `01`–`05` na kontenerze
`mcr.microsoft.com/mssql/server:2022-latest`; liczby powyżej pochodzą z tego uruchomienia.
Czasy w ms różnią się między przebiegami (np. 199 vs 574 ms dla Plain), logical reads są
deterministyczne.

**Nie zweryfikowane:** `run-demo.sh` jako całość (kroki wykonano ręcznie), `06-cleanup.sql`
(kontener usunięty w całości), zachowanie wymuszonego planu po zniknięciu indeksu, Query
Store hints.
