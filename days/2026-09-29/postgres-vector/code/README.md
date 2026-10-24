# Kod do wydania #7 - pgvector przez migracje EF Core (`dotnet ef`, indeks HNSW)

Pełny artykuł: [`../ARTICLE.md`](../ARTICLE.md).

> ✅ **Status:** `dotnet build` (0 warnings, 0 errors), `dotnet tool install dotnet-ef` (lokalnie),
> `dotnet ef migrations add` (x2), `dotnet ef database update` (od pustej bazy i z rollbackiem) i `dotnet run`
> uruchomione naprawdę na .NET SDK **10.0.400** (net10.0) przeciw kontenerowi `pgvector/pgvector:pg16`
> (pgvector **0.8.6**, PostgreSQL 16.15). Output w tym pliku jest prawdziwy. `run-demo.sh` jako **pojedynczy plik**
> nie był odpalony (środowisko agenta blokuje uruchamianie `.sh` jako pliku wykonywalnego) - te same kroki
> wykonano ręcznie, komenda po komendzie, identycznie jak w skrypcie. Dane: **syntetyczne, deterministyczne**
> (`Random(42)`), bez modelu embeddingowego i kluczy.

## Fragment prasówki, którego dotyczy ten kod

> EF wie, jak z `HasPostgresExtension("vector")` + `HasColumnType("vector(64)")` +
> `.HasMethod("hnsw").HasStorageParameter("m", 16).HasStorageParameter("ef_construction", 64)` złożyć kompletną
> migrację - włącznie z `CREATE EXTENSION IF NOT EXISTS vector`. `dotnet ef database update` na pustej bazie
> tworzy rozszerzenie, tabelę i indeks HNSW w jednym przebiegu, bez ręcznego SQL-a. Zmiana parametrów `m`/
> `ef_construction` w modelu generuje **drugą** migrację, która robi `DROP INDEX` + `CREATE INDEX` - nie ma
> odpowiednika `ALTER INDEX ... SET` dla parametrów budowy HNSW, więc EF (słusznie) rebuduje indeks od zera.
> Na 20 000 wierszach ten rebuild zajął realnie ~19,4 s.

## Struktura

```
code/
├── PgVectorEfMigrations.csproj   # net10.0; Npgsql 10.0.3, Pgvector 0.3.2, Pgvector.EntityFrameworkCore 0.3.0,
│                                 # Microsoft.EntityFrameworkCore.Design 9.0.0 (dla `dotnet ef`)
├── AppDbContext.cs               # Item, AppDbContext (OnModelCreating: kolumna vector(64) + indeks HNSW),
│                                 # AppDbContextFactory (IDesignTimeDbContextFactory - potrzebna dla `dotnet ef`)
├── Program.cs                    # dane (binary COPY), EF LINQ (CosineDistance), EXPLAIN, recall@10
├── Migrations/
│   ├── 20260929024044_InitialCreate.cs      # CREATE EXTENSION + tabela + indeks HNSW (m=16, ef_construction=64)
│   ├── 20260929024044_InitialCreate.Designer.cs
│   ├── 20260929024410_BumpHnswParams.cs     # DROP INDEX + CREATE INDEX (m=24, ef_construction=128)
│   ├── 20260929024410_BumpHnswParams.Designer.cs
│   └── AppDbContextModelSnapshot.cs
├── initial-migration.sql         # `dotnet ef migrations script` dla InitialCreate (referencyjny, wygenerowany)
├── bump-migration.sql            # `dotnet ef migrations script InitialCreate BumpHnswParams` (referencyjny)
├── dotnet-tools.json             # manifest lokalnego narzędzia dotnet-ef (`dotnet tool install dotnet-ef`)
└── run-demo.sh                   # kontener -> dotnet tool restore -> ef database update -> dotnet run -> sprzątanie
```

## Jak uruchomić od zera

Wymagania: Docker (obraz `pgvector/pgvector:pg16`), .NET SDK 10.

### Automatycznie

```bash
cd days/2026-09-29/postgres-vector/code
bash run-demo.sh
```

### Ręcznie (dokładnie te same kroki, którymi to zweryfikowano)

```bash
cd days/2026-09-29/postgres-vector/code

# 1. Kontener Postgres + pgvector
docker run -d --name pgvector-prasowka-d7 \
  -e POSTGRES_PASSWORD=demo -e POSTGRES_DB=demo \
  -p 54340:5432 pgvector/pgvector:pg16

# poczekaj, aż przyjmuje połączenia:
docker exec pgvector-prasowka-d7 pg_isready -U postgres

# 2. Lokalne narzędzie dotnet-ef (manifest już jest w repo - `dotnet-tools.json`)
dotnet tool restore

# 3. Migracje - OD PUSTEJ BAZY, bez ręcznego CREATE EXTENSION
export PG_CONN="Host=localhost;Port=54340;Username=postgres;Password=demo;Database=demo;Command Timeout=120;Timeout=30"
dotnet tool run dotnet-ef database update

# 4. Dane + zapytania przez EF Core
dotnet run

# 5. Sprzątanie
docker rm -f pgvector-prasowka-d7
```

Własny serwer: ustaw `PG_CONN` (domyślnie w kodzie: `Host=localhost;Port=54340;Username=postgres;Password=demo;Database=demo;Command Timeout=120;Timeout=30`).
`Command Timeout=120` jest ważne - przy `m=24`/`ef_construction=128` (po drugiej migracji) binary COPY 20 000
wierszy z domyślnym timeoutem 30 s realnie wywalał się `TimeoutException` (patrz artykuł, pkt 7).

### Praca z migracjami (co dokładnie odpaliłem)

```bash
# nowa migracja po zmianie OnModelCreating (np. innych parametrów HNSW):
dotnet tool run dotnet-ef migrations add BumpHnswParams

# podgląd wygenerowanego SQL bez aplikowania:
dotnet tool run dotnet-ef migrations script -o ./initial-migration.sql
dotnet tool run dotnet-ef migrations script InitialCreate BumpHnswParams -o ./bump-migration.sql

# lista migracji i ich stan:
dotnet tool run dotnet-ef migrations list

# rollback do konkretnej migracji (przetestowane - cofa też indeks):
dotnet tool run dotnet-ef database update InitialCreate

# powrót do najnowszej:
dotnet tool run dotnet-ef database update
```

## Output z uruchomienia (prawdziwy)

### `dotnet ef migrations add InitialCreate`

```
Build started...
Build succeeded.
Done. To undo this action, use 'ef migrations remove'
```

### `dotnet ef database update` (od pustej bazy, pierwsza migracja)

```
Acquiring an exclusive lock for migration application. See https://aka.ms/efcore-docs-migrations-lock for more information if this takes too long.
Applying migration '20260929024044_InitialCreate'.
Done.
```

Zweryfikowane bezpośrednio w bazie:

```
$ docker exec pgvector-prasowka-d7 psql -U postgres -d demo -c "\d items"
                        Table "public.items"
  Column   |         Type          | Nullable
-----------+-----------------------+----------
 Id        | integer               | not null
 Category  | character varying(64) | not null
 Embedding | vector(64)            |
Indexes:
    "PK_items" PRIMARY KEY, btree ("Id")
    "ix_items_embedding_hnsw" hnsw ("Embedding" vector_cosine_ops) WITH (ef_construction='64', m='16')

$ docker exec pgvector-prasowka-d7 psql -U postgres -d demo -c "SELECT extname, extversion FROM pg_extension WHERE extname='vector';"
 extname | extversion
---------+------------
 vector  | 0.8.6
```

### `dotnet ef migrations add BumpHnswParams` (po zmianie `m: 16→24`, `ef_construction: 64→128`)

Wygenerowany diff (`Migrations/20260929024410_BumpHnswParams.cs`):

```csharp
protected override void Up(MigrationBuilder migrationBuilder)
{
    migrationBuilder.DropIndex(name: "ix_items_embedding_hnsw", table: "items");

    migrationBuilder.CreateIndex(
        name: "ix_items_embedding_hnsw", table: "items", column: "Embedding")
        .Annotation("Npgsql:IndexMethod", "hnsw")
        .Annotation("Npgsql:IndexOperators", new[] { "vector_cosine_ops" })
        .Annotation("Npgsql:StorageParameter:ef_construction", 128)
        .Annotation("Npgsql:StorageParameter:m", 24);
}
```

`dotnet ef database update` (druga migracja, tabela ma już 20 000 wierszy z poprzedniego przebiegu `dotnet run`):

```
Applying migration '20260929024410_BumpHnswParams'.
Done.

real    0m19.372s
user    0m7.966s
sys     0m1.097s
```

`pg_indexes` po aplikacji:

```
ix_items_embedding_hnsw | CREATE INDEX ix_items_embedding_hnsw ON public.items USING hnsw ("Embedding" vector_cosine_ops) WITH (ef_construction='128', m='24')
```

Rollback (`dotnet ef database update InitialCreate`):

```
Reverting migration '20260929024410_BumpHnswParams'.
Done.
```

`pg_indexes` po rollbacku wraca do `ef_construction='64', m='16'` - potwierdzone. Migracja odtworzona z powrotem
(`dotnet ef database update` bez argumentu) przed dalszymi testami.

### `dotnet run` (pełny przebieg od pustej bazy, migracje = `InitialCreate` + `BumpHnswParams`, czyli `m=24`/`ef_construction=128`)

```
=== 0. Polaczenie ===
PG_CONN = Host=localhost;Port=54340;Username=postgres;Password=demo;Database=demo;Command Timeout=120;Timeout=30
Migracje zaaplikowane (brak pending) - OK.

=== 1. Czyszczenie tabeli items (TRUNCATE) ===

=== 2. Generowanie danych (deterministyczne, Random(42)) ===
Wygenerowano 20000 wektorow, 50 klastrow, dim=64

=== 3. Ladowanie: binary COPY (kolumna vector z Pgvector.Vector) ===
Zaladowano 20000 wierszy w 49174 ms

=== 4. Indeks z migracji - co widzi pg_indexes ===
  CREATE UNIQUE INDEX "PK_items" ON public.items USING btree ("Id")
  CREATE INDEX ix_items_embedding_hnsw ON public.items USING hnsw ("Embedding" vector_cosine_ops) WITH (ef_construction='128', m='24')

=== 5. kNN przez EF Core (CosineDistance) - 'prawda' bez indeksu vs z indeksem ===
Top 5 (LINQ, CosineDistance, indeks HNSW z migracji):
  id=  2801  cosine_dist=0.0000  (cluster-07)
  id=  2825  cosine_dist=0.0136  (cluster-07)
  id=  3009  cosine_dist=0.0143  (cluster-07)
  id=  2933  cosine_dist=0.0147  (cluster-07)
  id=  2887  cosine_dist=0.0162  (cluster-07)

SQL wygenerowany przez EF Core (ToQueryString):
  -- @__qParam_0='[...64 floaty...]' (DbType = Object)
  -- @__p_1='5'
  SELECT i."Id", i."Category", i."Embedding" <=> @__qParam_0 AS "Dist"
  FROM items AS i
  ORDER BY i."Embedding" <=> @__qParam_0
  LIMIT @__p_1

=== 6. EXPLAIN - czy planner faktycznie uzywa indeksu z migracji? ===
  Limit  (cost=186.05..187.77 rows=5 width=12)
    ->  Index Scan using ix_items_embedding_hnsw on items  (cost=186.05..10394.32 rows=29716 width=12)
          Order By: ("Embedding" <=> '[...64 floaty...]'::vector)

=== 7. Recall@10 z indeksem z migracji (HNSW ef_search domyslne) ===
recall@10 = 0.980  (44 ms / 50 zapytan = 0.88 ms/zapytanie)

=== Koniec ===
```

Drugi, niezależny przebieg (inny stan bazy, druga migracja aplikowana osobno na już załadowanych danych zamiast
od zera) dał `recall@10 = 1.000` - różnica mieści się w znanej niedeterministyczności budowy grafu HNSW (patrz
wydanie #4, tam też recall wahał się 0,956-0,994 między przebiegami przy tych samych danych).

## Pułapki napotkane naprawdę (nie teoretyczne)

| Pułapka | Realny komunikat / objaw |
|---|---|
| `EXPLAIN SELECT id FROM items ...` (małe litery) | `42703: column "id" does not exist` - kolumna nazywa się `"Id"` (EF nadaje PascalCase, Postgres jest wrażliwy na wielkość liter w cudzysłowie) |
| `new NpgsqlConnection(connStr)` bez `dsb.UseVector()` przy binary COPY | `InvalidCastException: Writing values of 'Pgvector.Vector' is not supported for parameters having no NpgsqlDbType or DataTypeName` |
| Binary COPY 20k wierszy przy `m=24, ef_construction=128` z domyślnym timeoutem | `TimeoutException: Timeout during reading attempt` w `NpgsqlBinaryImporter.Complete()` - podniesiony `Command Timeout=120` w connection stringu naprawił problem |
| Liczenie recall z ID 0-based (lista C#) vs 1-based (baza, bo COPY pisze `i+1`) | Pierwszy pomiar recall wyszedł ~0,02 zamiast ~0,98 - błąd był w kodzie weryfikującym (przesunięcie indeksu), nie w indeksie HNSW |

## Znane ograniczenia tego wydania

- `run-demo.sh` nie był odpalony jako pojedynczy plik `.sh` (blokada środowiska agenta) - wszystkie kroki
  wykonano ręcznie, tymi samymi komendami.
- `CREATE INDEX CONCURRENTLY` w migracji (żeby uniknąć blokady zapisów przy rebuildzie na produkcyjnej tabeli)
  nie było sprawdzane - EF domyślnie generuje zwykły `CREATE INDEX`.
- `HalfVector` w .NET, `hnsw.iterative_scan` z pulą połączeń, partycjonowanie z HNSW - nadal niezweryfikowane
  (patrz `STATE.md`).
- Kod z wydania #2 (prawdziwe embeddingi `fastembed`) - nadal niezweryfikowany.
