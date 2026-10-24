# Kod do wydania #2 — Statystyki, Key Lookup, covering index, parameter sniffing

Pełny artykuł: [`../ARTICLE.md`](../ARTICLE.md). Poniżej ten sam kod + jak go odpalić.

Wymagania: **Docker** (obraz `mcr.microsoft.com/mssql/server:2022-latest`, ok. 2-3 GB
po rozpakowaniu). Lokalny `sqlcmd` nie jest potrzebny — używamy `sqlcmd` z wnętrza
kontenera przez `docker exec`.

## Fragment prasówki, którego dotyczy ten kod

> Optymalizator szacuje liczbę wierszy ze **statystyk** (histogram do 200 kroków).
> Indeks nieklastrowy bez wszystkich potrzebnych kolumn wymusza **Key Lookup** — po
> jednym skoku do tabeli na każdy trafiony wiersz. Dla 6 wierszy to 21 odczytów stron,
> dla 200 000 wierszy wymuszony plan z lookupami kosztuje 612 884 odczytów (skan
> całej tabeli: 2 486). Plan kompilowany jest raz i trzymany w **plan cache**;
> **parameter sniffing** sprawia, że plan skompilowany pod pierwszą wartość
> parametru obsługuje wszystkie kolejne: procedura skompilowana dla klienta rzadkiego
> a wywołana dla hurtownika czyta 600 350 stron zamiast 2 486 (241×), a w odwrotnej
> kolejności klient rzadki płaci 2 486 zamiast 21 (118×). Lekarstwa: `OPTION
> (RECOMPILE)` albo **covering index** (`INCLUDE`), który usuwa Key Lookup i przy
> okazji problem sniffingu (648 / 3 odczyty niezależnie od kolejności).

## Pliki

| Plik | Co robi |
|---|---|
| `01-create-table-and-data.sql` | Baza `PrasowkaStats`, tabela `dbo.Orders` (500 000 wierszy, skośna: klient 1 = 200 000 zamówień), wąski indeks `IX_Orders_CustomerId`. Dane deterministyczne. |
| `02-statistics.sql` | `DBCC SHOW_STATISTICS` (nagłówek + histogram), `sys.dm_db_stats_properties`, szacunek vs rzeczywistość w planie. |
| `03-key-lookup.sql` | Ten sam SELECT dla klienta rzadkiego i hurtownika + wymuszony plan z 200 000 Key Lookupów. `STATISTICS IO` + `PROFILE`. |
| `04-parameter-sniffing.sql` | Procedury `usp_CustomerSummary` i `_Recompile`, dwie kolejności wywołań po `CLEAR PROCEDURE_CACHE`, podgląd plan cache (`sys.dm_exec_procedure_stats`, `ParameterCompiledValue`), naprawa `OPTION (RECOMPILE)`. |
| `05-covering-index.sql` | Zamiana wąskiego indeksu na `IX_Orders_CustomerId_Cov ... INCLUDE (OrderDate, Amount)`, rozmiary indeksów, plany bez Key Lookup, sniffing po naprawie. |
| `06-cleanup.sql` | Opcjonalne usunięcie bazy `PrasowkaStats`. |
| `run-demo.sh` | Stawia kontener, czeka na SQL Server, uruchamia `01`→`05`, usuwa kontener. |

## Jak odpalić od zera

```bash
cd days/2026-09-25/sqlserver/code
bash run-demo.sh
```

Ręcznie, krok po kroku (dokładnie tak zostało zweryfikowane):

```bash
docker run -d --rm --name sqlserver-prasowka-stats \
  -e ACCEPT_EULA=Y -e 'MSSQL_SA_PASSWORD=Prasowka#2026!' \
  mcr.microsoft.com/mssql/server:2022-latest

# poczekaj, aż SQL Server przyjmie połączenia:
docker exec sqlserver-prasowka-stats /opt/mssql-tools18/bin/sqlcmd \
  -S localhost -U sa -P 'Prasowka#2026!' -C -Q "SELECT @@VERSION"

# skrypty po kolei (-I = QUOTED_IDENTIFIER ON, wymagane przez zapytanie XML w 04):
for f in 01-create-table-and-data.sql 02-statistics.sql 03-key-lookup.sql \
         04-parameter-sniffing.sql 05-covering-index.sql; do
  docker exec -i sqlserver-prasowka-stats /opt/mssql-tools18/bin/sqlcmd \
    -S localhost -U sa -P 'Prasowka#2026!' -C -b -I -y 40 -i /dev/stdin < "$f"
done

# sprzątanie:
docker rm -f sqlserver-prasowka-stats
```

## Prawdziwy output (skrót, SQL Server 2022 RTM-CU27, 16.0.4295.3)

```
IX_Orders_CustomerId  866 stron | tabela 2476 stron | IX_Orders_CustomerId_Cov 1609 stron

Klient 1: EQ_ROWS 200000, EstimateRows 200000, Rows 200000
Klient 4242: EstimateRows 6, Rows 6

03: (a) 4242, Seek + Key Lookup ............ logical reads 21
    (b) klient 1, wybor optymalizatora ..... Clustered Index Scan, logical reads 2486
    (c) klient 1, wymuszony indeks ......... Seek + 200000 Key Lookup, logical reads 612884

04: A1 (4242 pierwszy) 21   -> A2 (klient 1, reuzycie planu) 600350
    B1 (klient 1 pierwszy) 2486 -> B2 (4242, reuzycie skanu) 2486
    RECOMPILE: klient 1 = 2486, klient 4242 = 21
    ParameterCompiledValue = (4242), execution_count = 2

05: covering: 4242 = 3 odczyty, klient 1 = 648; procedura w obu kolejnosciach: 648/4 oraz 3/648
```

## Status weryfikacji

**Zweryfikowane realnie:** skrypty `01`–`05` uruchomione na kontenerze
`mcr.microsoft.com/mssql/server:2022-latest`, liczby wyżej i w artykule pochodzą z tego
uruchomienia. Kontener został usunięty po testach (obraz `mssql/server:2022-latest`
został w lokalnym cache Dockera).

**Nie zweryfikowane:** sam skrypt `run-demo.sh` nie został odpalony jako całość
(środowisko agenta zablokowało jego uruchomienie i `chmod +x`); wykonano ręcznie te
same polecenia `docker run` / `docker exec ... sqlcmd`, które on zawiera. Skrypt
uruchamiaj przez `bash run-demo.sh`. Skrypt `06-cleanup.sql` też nie był uruchamiany
(kontener usunięto całkowicie).
