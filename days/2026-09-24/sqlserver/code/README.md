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

## Status weryfikacji — ważne

**Nie udało się to realnie uruchomić w środowisku, w którym pisany był ten kod.**
Dysk hosta (40 GB) jest w praktyce pełny — w trakcie próby spadł z 845 MB do
231 MB wolnego miejsca (współdzielona maszyna, inne procesy zużywają miejsce
równolegle). `docker pull mcr.microsoft.com/mssql/server:2022-latest` zakończył
się błędem:

```
failed to extract layer (application/vnd.docker.image.rootfs.diff.tar.gzip
sha256:cb5e374be662a562b8271158639e918b9c634aa4dfdc8b3aa31ccfc99cf8c077) to
overlayfs as "extract-903847685-KScw ...": mount callback failed on
/var/lib/containerd/tmpmounts/containerd-mount2254423097: write
/var/lib/containerd/tmpmounts/containerd-mount2254423097/usr/lib/locale/C.utf8/LC_CTYPE:
no space left on device
```

Sprzątnięcie cudzych, nieużywanych obrazów Dockera na tej maszynie (`docker
system prune`) zostało celowo zablokowane przez system uprawnień, żeby nie
zepsuć pracy innych, równolegle działających zadań na tej samej maszynie —
słusznie, więc tego nie obchodzono. `docker image prune -f` (bezpieczny wariant,
tylko "dangling" warstwy) faktycznie się wykonał, ale odzyskał 0 B — nic do
odzyskania nie było.

**Efekt:** żadna liczba `logical reads`/czasu w `ARTICLE.md` ani tutaj **nie jest
zmyślona** — po prostu jej nie ma, zgodnie z zasadą "zero fikcji" tej prasówki.
Same skrypty `.sql` są kompletne i logicznie spójne (wzorce jak `ROW_NUMBER()`
row-generator, `SET STATISTICS IO/TIME/PROFILE`, `sys.dm_db_index_physical_stats`
to standardowe, udokumentowane konstrukcje T-SQL, ręcznie zweryfikowane pod
kątem składni) i gotowe do odpalenia przez `./run-demo.sh` w środowisku z wolnym
miejscem na dysku — wtedy `code/README.md` powinno zostać zaktualizowane o
prawdziwy output.
