# Kod do wydania #23 — spill do tempdb, memory grant feedback, sync vs async statystyki

Pełny artykuł: [`../ARTICLE.md`](../ARTICLE.md). Poniżej ten sam kod + jak go odpalić.

Wymagania: **Docker** (obraz `mcr.microsoft.com/mssql/server:2022-latest`). Lokalny `sqlcmd`
niepotrzebny — używamy `sqlcmd` z kontenera przez `docker exec`. Całość trwa kilka minut.

## Fragment prasówki, którego dotyczy ten kod

> **Spill leczy się sam.** Po dosypaniu 600 000 wierszy z nową wartością (`Status = 7`)
> przy `AUTO_UPDATE_STATISTICS OFF` estymata to 1 264,91, grant 1 440 KB i 3 980 stron
> spillu do tempdb. Drugie wywołanie tego samego planu: grant 62 832 KB, spill 0 — to
> memory grant feedback, estymata dalej zła. Eksperyment OFF/ON na
> `ROW_MODE_MEMORY_GRANT_FEEDBACK`: bez feedbacku spill ~4 250 stron w każdym z 5 wywołań,
> z feedbackiem 0 od drugiego. Czas jednak nie spadł (ok. 1 730–2 000 vs 1 470–1 600 ms).
>
> **Sync vs async.** Sync: kompilacja 460 ms, estymata 604 027, bez spilla. Async:
> kompilacja 3 ms, pierwsze wywołanie na starej estymacie (1 264,91, spill 3 964), drugie
> już na nowej (604 027).

## Pliki

| Plik | Co robi |
|---|---|
| `01-lab.sql` | Baza `StatLab`, `dbo.Orders` 1 mln + 600 000 wierszy `Status = 7`, procedura `dbo.Mediana`; wywołanie 1, pauza 10 s, wywołanie 2, `UPDATE STATISTICS … FULLSCAN`, wywołanie 3. Zmienne: `UPD`, `ASYNC`. |
| `02-raport.sql` | Dołączany przez `:r` — grant, spille, czas, DOP i estymata z planu w cache. |
| `03-mgf.sql` | Wymaga `StatLab` z `01`. Dwie procedury (`Med9`, `Med10`), pięć wywołań z feedbackiem `OFF` i `ON`. |
| `04-cleanup.sql` | Usuwa bazę `StatLab`. |

## Jak odpalić

Uruchom z katalogu `code/`:

```bash
docker run -d --name prasowka23-sqlserver \
  -e ACCEPT_EULA=Y -e 'MSSQL_SA_PASSWORD=Prasowka_Demo_123!' --cpus 2 \
  mcr.microsoft.com/mssql/server:2022-latest

docker exec prasowka23-sqlserver mkdir -p /tmp/code
docker cp . prasowka23-sqlserver:/tmp/code/

# poczekaj kilkanaście sekund na start serwera
SQLCMD="docker exec prasowka23-sqlserver /opt/mssql-tools18/bin/sqlcmd -S localhost -U sa -P Prasowka_Demo_123! -C -I -W -b"

# trzy tryby statystyk (każde uruchomienie buduje bazę od zera)
$SQLCMD -v UPD=OFF ASYNC=OFF -i /tmp/code/01-lab.sql
$SQLCMD -v UPD=ON  ASYNC=OFF -i /tmp/code/01-lab.sql
$SQLCMD -v UPD=ON  ASYNC=ON  -i /tmp/code/01-lab.sql

# memory grant feedback OFF vs ON (na świeżej bazie z trybu OFF/OFF)
$SQLCMD -v UPD=OFF ASYNC=OFF -i /tmp/code/01-lab.sql
$SQLCMD -i /tmp/code/03-mgf.sql

$SQLCMD -i /tmp/code/04-cleanup.sql
docker rm -f -v prasowka23-sqlserver
```

Skrypt `01` wywołuje `DBCC FREEPROCCACHE` — **tylko na instancji testowej**.
`03` nie jest idempotentny (dosypuje wiersze) — przed powtórką uruchom ponownie `01`.

## Prawdziwy output (SQL Server 2022 RTM-CU27, 16.0.4295.3) — skrót

```
01 UPD=OFF ASYNC=OFF: wywolanie 1: grant 1440 KB, spille 3980, czas 1346 ms, estymata 1264.91
                      wywolanie 2: wykonan 2, grant 62832 KB (uzyty 34312), spille 0, 1719 ms, estymata 1264.91
                      po FULLSCAN: wykonan 1, grant 66920 KB, spille 0, estymata 600000
01 UPD=ON  ASYNC=OFF: kompilacja 460 ms, estymata 604027, spille 0; stat rows 1600000 rows_sampled 304593
01 UPD=ON  ASYNC=ON : kompilacja 3 ms, wywolanie 1: estymata 1264.91, spille 3964, 1560 ms
                      po 10 s: stat rows 1600000, modification_counter 0
                      wywolanie 2: nowy plan (wykonan 1), estymata 604027, spille 0

03 (spille_stron / grant_kb):
A (feedback OFF): 4250/1504, 4250/1504, 4250/1504, 4242/1504, 4246/1504
B (feedback ON) : 4275/1504, 0/61600, 0/61600, 0/61600, 0/61600
```

## Status weryfikacji

**Zweryfikowane realnie:** `01` we wszystkich trzech trybach i `03`, ręcznie przez
`docker exec … sqlcmd`, każde co najmniej dwa razy na świeżej bazie, z tymi samymi wzorcami.

**Nie zweryfikowane:** cały zestaw jako jeden skrypt `.sh` (nie powstał); wewnętrzny
mechanizm MGF (wnioskujemy z OFF/ON); feedback w dół i oscylacje; współbieżność; async na
wielu sesjach; faktyczny koszt spilla na wolnym dysku.
