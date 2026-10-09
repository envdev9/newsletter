# Kod do wydania #9 - `HalfVector` w .NET i `iterative_scan` z pulą połączeń (pgvector)

Pełny artykuł: [`../ARTICLE.md`](../ARTICLE.md).

> ✅ **Status:** `dotnet build` (0 warnings, 0 errors) oraz `dotnet run -- load | halfvec | pool` uruchomione naprawdę
> na .NET SDK **10.0.400** (net10.0), `Npgsql` **10.0.3**, `Pgvector` **0.3.2**, przeciw kontenerowi
> `pgvector/pgvector:pg16`. `dims.sql` uruchomiony przez `docker exec psql`. Output poniżej jest prawdziwy.
> Dane: **syntetyczne, deterministyczne** (`Random(42)`, 50 klastrów + szum), bez modelu embeddingowego i kluczy.
> Nie powstał żaden plik `run-demo.sh` - wszystkie komendy poniżej są jednolinijkowe i były wykonane ręcznie.

## Fragment prasówki, którego dotyczy ten kod

> `HalfVector` z `Pgvector` 0.3.2 mapuje się na `halfvec(N)` (po 2 bajty na wymiar) i działa z binary COPY
> tak samo jak `Vector`. Dla 64 wymiarów indeks HNSW jest mniejszy tylko o ~24% (8,7 vs 11,4 MB), ale przy 1536
> wymiarach dokładnie 2,00x (12,3 vs 24,6 MB), a przede wszystkim: HNSW na `vector` kończy się na 2000 wymiarach
> (`column cannot have more than 2000 dimensions for hnsw index`), na `halfvec` na 4000 - czyli embeddingi 3072-wymiarowe
> da się indeksować tylko przez `halfvec` (np. indeks na rzutowaniu `(e::halfvec(3072))`). `hnsw.iterative_scan`
> jest ustawieniem SESJI Postgresa, a sesja to fizyczne połączenie z puli Npgsql: plain `SET` wycieka do kolejnego
> żądania, gdy pula nie resetuje połączeń (`No Reset On Close=true`) - w teście 16 zadań na puli 4 zadania, które
> nic nie ustawiały, widziały `relaxed_order` w 398 z 400 zapytań. `set_config('hnsw.iterative_scan', ..., true)`
> w transakcji (odpowiednik `SET LOCAL`): 0 z 400. Filtr po kolumnie bez indeksu (5% wierszy) bez `iterative_scan`
> zwracał 39 z 200 oczekiwanych wierszy (recall 0,195); `strict_order` i `relaxed_order`: 200/200, recall 1,000.

## Struktura

```
code/
├── HalfVectorPool.csproj   # net10.0; Npgsql 10.0.3, Pgvector 0.3.2 (bez EF Core)
├── Program.cs              # dotnet run -- load | halfvec | pool
└── dims.sql                # limity wymiarow HNSW (2000/4000) i rozmiar indeksu przy 1536 wymiarach (psql)
```

## Jak uruchomić od zera

Wymagania: Docker (obraz `pgvector/pgvector:pg16`), .NET SDK 10.

```bash
cd days/2026-10-09/postgres-vector/code

# 1. Kontener
docker run -d --name pgvector-prasowka-d9 -e POSTGRES_PASSWORD=demo -e POSTGRES_DB=demo -p 54351:5432 pgvector/pgvector:pg16
docker exec pgvector-prasowka-d9 pg_isready -U postgres

# 2. Dane: 20 000 wierszy, kolumny vector(64) i halfvec(64), dwa indeksy HNSW (domyslny connection string: localhost:54351)
dotnet run -- load

# 3. Czesc A: halfvec
dotnet run -- halfvec

# 4. Czesc B: iterative_scan a pula polaczen
dotnet run -- pool

# 5. Limity wymiarow (3072 / 4001 / 1536)
docker cp dims.sql pgvector-prasowka-d9:/tmp/dims.sql
docker exec pgvector-prasowka-d9 psql -U postgres -d demo -f /tmp/dims.sql

# 6. Sprzatanie
docker rm -f pgvector-prasowka-d9
```

Inny serwer: zmienna `PG_CONN` (pełny connection string Npgsql).

## Output z uruchomienia (prawdziwy)

### `dotnet run -- load`

```
COPY 20000 wierszy (vector + halfvec) w 1635 ms
HNSW na vector  : 5433 ms
HNSW na halfvec : 7280 ms
```

(Pierwszy przebieg: 1490 ms / 8189 ms / 7767 ms - czasy budowy HNSW się wahają, nie wyciągam z nich wniosków.)

### `dotnet run -- halfvec`

```
== Rozmiary ==
pg_column_size(vector(64))  : 264
pg_column_size(halfvec(64)) : 136
indeks HNSW vector  (bajty) : 11403264
indeks HNSW halfvec (bajty) : 8699904
tabela (heap, bajty)        : 9306112

== Round-trip id=1, pierwsze 3 wymiary ==
  float32=0.330712  half=0.33081055  blad=9.86E-005
  float32=0.018242326  half=0.018249512  blad=7.19E-006
  float32=-0.043990403  half=-0.04397583  blad=1.46E-005

== recall@10 (20 zapytan, ef_search=40) ==
  vector  : recall 0.995, sr. 3.14 ms
  halfvec : recall 1.000, sr. 2.98 ms
```

Uwaga: w pierwszym przebiegu (osobna budowa indeksów) było `vector` 0,955 vs `halfvec` 1,000 - różnica to
niedeterministyczna budowa grafu HNSW, nie zaleta `halfvec`.

Plany: `Index Scan using ix_items_half` dla kolumny `halfvec`; `Index Scan using ix_items_cast` dla
`ORDER BY embedding::halfvec(64) <=> $1` na kolumnie `vector` z indeksem na rzutowaniu; `ix_items_vec` dla
`ORDER BY embedding <=> $1`.

### `dotnet run -- pool`

```
== 1a. Co planner robi z filtrem po tenant (~0,5% wierszy, jest B-tree)? ==
  WHERE tenant = 5:   Bitmap Heap Scan + Bitmap Index Scan on ix_items_tenant, Sort   (HNSW nieuzyty)
  WHERE tier = 5:     Index Scan using ix_items_vec ... Filter: (tier = 5)

== 1b. Filtr tier (5% wierszy = ~1000 z 20 000), 20 zapytan, LIMIT 10 ==
  iterative_scan=off            wierszy zwroconych:  39/200  recall: 0.195  sr. 3.28 ms
  iterative_scan=strict_order   wierszy zwroconych: 200/200  recall: 1.000  sr. 4.47 ms
  iterative_scan=relaxed_order  wierszy zwroconych: 200/200  recall: 1.000  sr. 8.11 ms

== 2a. SHOW hnsw.iterative_scan na SWIEZYM backendzie (biblioteka vector jeszcze nie zaladowana) ==
  SHOW -> 42704: unrecognized configuration parameter "hnsw.iterative_scan"
  current_setting(..., true) -> NULL
  po pierwszym uzyciu typu vector: SHOW -> off

== 2. Czy SET przezywa zwrot polaczenia do puli? ==
  No Reset On Close=False  backend pid TEN SAM  SHOW przed zwrotem: relaxed_order  po ponownym otwarciu: (pusty)
  No Reset On Close=True   backend pid TEN SAM  SHOW przed zwrotem: relaxed_order  po ponownym otwarciu: relaxed_order

== 3. Options=-c hnsw.iterative_scan=relaxed_order w connection stringu ==
  swieze polaczenie : iterative_scan=relaxed_order, max_scan_tuples=5000
  po SET ... 'off'  : iterative_scan=off
  po zwrocie do puli (reset): iterative_scan=relaxed_order

== 4. SET LOCAL w transakcji (No Reset On Close=true, czyli BEZ ratunku od Npgsql) ==
  w transakcji      : relaxed_order
  po COMMIT/zwrocie : (pusty)

== 5a. Pula 4 (No Reset On Close=true), 16 zadan x 50 zapytan, parzyste: SET sesyjny, nieparzyste: nic nie ustawiaja ==
  zadania nieparzyste (nic nie ustawialy) zobaczyly relaxed_order w 398 z 400 zapytan

== 5b. ... parzyste: set_config(..., true) w transakcji, nieparzyste: nic nie ustawiaja ==
  zadania nieparzyste (nic nie ustawialy) zobaczyly relaxed_order w 0 z 400 zapytan
```

(Sekcja 1a w pliku wypisuje pełne linie `EXPLAIN`, tu skrócone.)

### `dims.sql` (3000 losowych wierszy, `vector(3072)` i `vector(1536)`)

```
=== 3072 wymiary: HNSW na vector(3072) ===
ERROR:  column cannot have more than 2000 dimensions for hnsw index
=== 3072 wymiary: HNSW na rzutowaniu e3072::halfvec(3072) ===
CREATE INDEX      (rozmiar: 24584192 B)
=== 4001 wymiary: HNSW na halfvec(4001) ===
ERROR:  column cannot have more than 4000 dimensions for hnsw index
=== 1536 wymiary: rozmiary indeksow ===
 bytes_vec | bytes_half | ratio
  24584192 |   12296192 |  2.00
 vec_1536_col | half_1536_col
         6148 |          3080
```

## Pułapki napotkane naprawdę

| Pułapka | Realny objaw |
|---|---|
| `CREATE EXTENSION vector` na połączeniu, które już załadowało katalog typów Npgsql | `InvalidCastException: Writing values of 'Pgvector.Vector' is not supported ... Cannot resolve 'vector' to a fully qualified datatype name` - naprawa: `await conn.ReloadTypesAsync()` po `CREATE EXTENSION` (albo osobne połączenie bootstrapowe przed zbudowaniem `NpgsqlDataSource`) |
| `SHOW hnsw.iterative_scan` na świeżym backendzie | `42704: unrecognized configuration parameter` - GUC rejestruje się dopiero po załadowaniu biblioteki `vector` w tym backendzie; użyj `current_setting('hnsw.iterative_scan', true)` (NULL zamiast błędu) |
| Filtr po kolumnie z B-tree o selektywności ~0,5% | planner w ogóle nie używa HNSW (Bitmap Scan + Sort) - problem post-filtrowania nie występuje; demo wymaga kolumny bez indeksu / mniej selektywnego filtra |

## Znane ograniczenia tego wydania

- Dane syntetyczne; wymiar 64 (przy 1536 mierzone tylko rozmiary na losowych wektorach, bez recall).
- Wyniki `halfvec` vs `vector` dla recall to jeden zestaw 20 zapytań i jedna budowa grafu - różnice rzędu 0,01-0,05 to szum.
- Nie testowano: partycjonowanie z HNSW, `max_scan_tuples` w działaniu (poza ustawieniem przez `Options`), EF Core z `HalfVector`.
- Pusty string w `SHOW` po resecie: nie zbadałem, jak zachowuje się planner/wyszukiwanie przy takiej wartości (zaobserwowano
  tylko wynik `SHOW`; hipoteza: placeholder GUC sprzed załadowania biblioteki).
- Kod z wydania #2 (prawdziwe embeddingi `fastembed`) - nadal niezweryfikowany.
