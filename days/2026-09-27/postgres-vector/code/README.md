# Kod do wydania #4 - pgvector z .NET: Npgsql + Pgvector + EF Core

Pełny artykuł: [`../ARTICLE.md`](../ARTICLE.md).

> ✅ **Status:** `dotnet build` (0 warnings, 0 errors) i `dotnet run --project` uruchomione naprawdę na .NET SDK
> 10.0.400 (net10.0) przeciw kontenerowi `pgvector/pgvector:pg16` (pgvector **0.8.6**, PostgreSQL 16.15).
> Output poniżej jest prawdziwy. `run-demo.sh` jako całość **nie był** odpalony - kontener uruchomiono i posprzątano
> ręcznie tymi samymi komendami, a `dotnet run` przeciw niemu. Dane: **syntetyczne, deterministyczne**
> (`Random(42)`), bez modelu embeddingowego i kluczy.

## Fragment prasówki, którego dotyczy ten kod

> Npgsql nie zna typu `vector` sam z siebie. Pakiet NuGet `Pgvector` dodaje typ `Vector` oraz
> `NpgsqlDataSourceBuilder.UseVector()`; parametr kNN przekazujesz jako `new Vector(float[])`, a nie jako `float[]`
> (to dałoby `operator does not exist: vector <=> real[]`). Dane ładujesz binary COPY, `hnsw.ef_search` ustawiasz
> przez `SET LOCAL` w transakcji (bezpieczne przy puli połączeń). W EF Core (`Pgvector.EntityFrameworkCore`)
> kolumna to `HasColumnType("vector(64)")`, indeks HNSW opisujesz w `OnModelCreating`
> (`HasMethod("hnsw").HasOperators("vector_cosine_ops")`), a zapytanie to
> `OrderBy(x => x.Embedding.CosineDistance(q)).Take(k)`.

## Struktura

```
code/
├── PgVectorDotnet.csproj   # net10.0; Npgsql 10.0.3, Pgvector 0.3.2, Pgvector.EntityFrameworkCore 0.3.0
├── Program.cs              # cały demo: dane, COPY, kNN, HNSW+recall, EXPLAIN, pułapki, EF Core
└── run-demo.sh             # kontener -> dotnet run -> sprzątanie (trap EXIT)
```

## Jak uruchomić

Wymagania: Docker (obraz `pgvector/pgvector:pg16`), .NET SDK 10.

```bash
cd days/2026-09-27/postgres-vector/code
bash run-demo.sh
```

Albo ręcznie:

```bash
docker run -d --name pgvector-prasowka-d4 -e POSTGRES_PASSWORD=demo -e POSTGRES_DB=demo -p 54329:5432 pgvector/pgvector:pg16
dotnet run --project PgVectorDotnet.csproj
docker rm -f pgvector-prasowka-d4
```

Własny serwer: ustaw zmienną `PG_CONN` (domyślnie `Host=localhost;Port=54329;Username=postgres;Password=demo;Database=demo`).
Program sam tworzy tabele `docs` i `items` (kasuje je, jeśli istnieją - używaj pustej bazy demo).

## Output z uruchomienia (prawdziwy, ostatni z 3 przebiegów)

```
=== 1. Wersje ===
PostgreSQL: PostgreSQL 16.15 (Debian 16.15-1.pgdg12+2) on x86_64-pc-linux-gnu | pgvector: 0.8.6

=== 2. Ladowanie: binary COPY z typem Vector ===
Zaladowano 20000 wierszy w 825 ms

=== 3. kNN z parametrem wektorowym (bez indeksu = dokladny Seq Scan) ===
  id=  7664  cosine_dist=0.0461  (klaster 14)
  id= 15514  cosine_dist=0.1759  (klaster 14)
  id=  8064  cosine_dist=0.1959  (klaster 14)
  id=  3864  cosine_dist=0.1992  (klaster 14)
  id=  3964  cosine_dist=0.2075  (klaster 14)
Dokladnie (Seq Scan): 22.13 ms/zapytanie

=== 4. Indeks HNSW + recall@10 w zaleznosci od hnsw.ef_search ===
CREATE INDEX HNSW: 6.9 s
  ef_search= 10: recall@10=0.972  1.47 ms/zapytanie
  ef_search= 40: recall@10=1.000  1.82 ms/zapytanie
  ef_search=200: recall@10=1.000  2.54 ms/zapytanie

=== 5. Plan zapytania z parametrem (czy indeks jest uzywany?) ===
  Limit  (cost=167.17..171.63 rows=10 width=12)
    ->  Index Scan using docs_hnsw on docs  (cost=167.17..9092.00 rows=20000 width=12)
          Order By: (emb <=> '[...64 floaty...]'::vector)

=== 6. Pulapki: float[] zamiast Vector, zla wymiarowosc ===
  float[]: 42883 operator does not exist: vector <=> real[]
  3D vs vector(64): 22000 different vector dimensions 3 and 64

=== 7. EF Core: HasColumnType + HNSW w modelu + CosineDistance ===
SQL wygenerowany przez EF Core:
-- @__q_0='[...64 floaty...]' (DbType = Object)
-- @__p_1='5'
SELECT i."Id", i."Category", i."Embedding" <=> @__q_0 AS "Dist"
FROM items AS i
ORDER BY i."Embedding" <=> @__q_0
LIMIT @__p_1
Wynik (top 5 z pierwszych 2000 wierszy):
  id=  664  cosine_dist=0.2183  (klaster 14)
  ...
Indeks z modelu (pg_indexes):
  CREATE INDEX ix_items_embedding ON public.items USING hnsw ("Embedding" vector_cosine_ops) WITH (ef_construction='64', m='16')
```

(W wycinku pominięto sekcję 0 i pozostałe 4 wiersze EF Core; pełny output daje `dotnet run`.)

Uwaga o powtarzalności: dane i zapytania są deterministyczne, ale **budowa grafu HNSW nie** - recall przy
`ef_search=10` w trzech kolejnych przebiegach wyniósł 0,956 / 0,994 / 0,972. Czasy zależą od sprzętu (jeden proces,
Docker na tej samej maszynie, pomiar `Stopwatch` po stronie klienta - zawiera round-trip).
