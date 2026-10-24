# Kod do wydania #23 - partycjonowanie z indeksem HNSW i `max_scan_tuples` (pgvector)

Pełny artykuł: [`../ARTICLE.md`](../ARTICLE.md).

> ✅ **Status:** wszystkie cztery skrypty `.sql` uruchomione naprawdę przez `docker exec ... psql` na
> `pgvector/pgvector:pg16` (PostgreSQL **16.15**, pgvector **0.8.6**). Dane **syntetyczne, deterministyczne**
> (`setseed(0.42)`), bez modelu i kluczy. Brak części .NET - temat to schemat i planer. Brak `run-demo.sh`; kroki
> są ręczne, jednolinijkowe.

## Fragment prasówki, którego dotyczy ten kod

> `PARTITION BY LIST (tenant)` + `CREATE INDEX ... USING hnsw` na rodzicu daje osobny graf HNSW w każdej partycji.
> Filtr po kluczu partycji przycina planer do jednej partycji (także z parametrem: `Subplans Removed: 7`), a recall
> z filtrem `tenant = 3` wynosi 0,87 (`ef_search=40`) i 1,00 (`ef_search=100`) i zawsze 10 wierszy - na monolicie
> 0,445-0,500 i 4,5-5,0 wiersza z 10 (post-filtrowanie). Filtr po kolumnie spoza klucza partycji nie przycina nic.
> `hnsw.max_scan_tuples` to limit skanu iteracyjnego: przy filtrze 5% wartość 100 zwraca 8,0 wiersza z 10,
> 500 i więcej - 10. `CREATE INDEX CONCURRENTLY` wprost na tabeli partycjonowanej nie działa (PG16); wzorzec to
> `ON ONLY` + `CONCURRENTLY` per partycja + `ALTER INDEX ... ATTACH PARTITION`.

## Struktura

```
code/
├── 01-setup.sql        # dane, items_m (monolit) i items_p (8 partycji), indeksy HNSW, rozmiary
├── 02-plans.sql        # EXPLAIN: pruning stały/parametr, Merge Append, brak pruningu po tier
├── 03-recall.sql       # recall@10 i liczba wierszy: monolit vs partycje, max_scan_tuples
└── 04-maintenance.sql  # REINDEX partycji, ON ONLY + CONCURRENTLY + ATTACH, nowa partycja, DETACH/DROP
```

## Jak uruchomić od zera

Wymagania: Docker (obraz `pgvector/pgvector:pg16`). Z katalogu `days/2026-10-16/postgres-vector/code`:

```bash
docker run -d --name pgvector-prasowka-d23 -e POSTGRES_PASSWORD=demo -e POSTGRES_DB=demo pgvector/pgvector:pg16
docker exec pgvector-prasowka-d23 pg_isready -U postgres

docker cp 01-setup.sql pgvector-prasowka-d23:/tmp/01-setup.sql
docker cp 02-plans.sql pgvector-prasowka-d23:/tmp/02-plans.sql
docker cp 03-recall.sql pgvector-prasowka-d23:/tmp/03-recall.sql
docker cp 04-maintenance.sql pgvector-prasowka-d23:/tmp/04-maintenance.sql

docker exec pgvector-prasowka-d23 psql -U postgres -d demo -v ON_ERROR_STOP=1 -f /tmp/01-setup.sql
docker exec pgvector-prasowka-d23 psql -U postgres -d demo -v ON_ERROR_STOP=1 -f /tmp/02-plans.sql
docker exec pgvector-prasowka-d23 psql -U postgres -d demo -v ON_ERROR_STOP=1 -f /tmp/03-recall.sql
# 04 celowo zawiera jedno polecenie konczace sie bledem - bez ON_ERROR_STOP:
docker exec pgvector-prasowka-d23 psql -U postgres -d demo -f /tmp/04-maintenance.sql

docker rm -f pgvector-prasowka-d23
```

Skrypty `02`-`04` zakładają stan po `01` (uruchamiaj w tej kolejności; `04` modyfikuje partycje, więc `03` przed nim).
W pierwszym uruchomieniu `psql` w kontenerze może wymagać chwili po `pg_isready`.

## Output z uruchomienia (prawdziwy)

### `01-setup.sql`

```
CREATE INDEX   Time: 6113.779 ms   (monolit)
CREATE INDEX   Time: 4402.300 ms   (8 partycji)
 monolit         | 11 MB
 partycje (suma) | 11 MB
 tenant | count : 0..7 po 2500
```

### `03-recall.sql` (dwa przebiegi dały identyczne liczby)

```
bez filtra, ef_search=10 : monolit 0.945 / 10.0   partycje 1.000 / 10.0
bez filtra, ef_search=40 : monolit 0.990 / 10.0   partycje 1.000 / 10.0
tenant=3, ef_search=40   : monolit 0.445 /  4.5   partycje 0.870 / 10.0
tenant=3, ef_search=100  : monolit 0.500 /  5.0   partycje 1.000 / 10.0
tier=5 iterative off     : 0.180 / 1.8
relaxed, max_scan_tuples=100   : 0.785 /  8.0
relaxed, max_scan_tuples=500   : 0.935 / 10.0
relaxed, max_scan_tuples=2000  : 0.940 / 10.0
relaxed, max_scan_tuples=20000 : 0.940 / 10.0
```

(format: recall / wierszy na zapytanie)

### `04-maintenance.sql` (skrót)

```
REINDEX INDEX items_p_t3_embedding_idx     Time: 667.276 ms
ERROR:  cannot create index on partitioned table "items_p" concurrently
ix_p_l2 | indisvalid f   (po ON ONLY, po 1..7 partycjach)
ix_p_l2 | indisvalid t   (po 8. partycji)
nowa partycja items_p_t8: items_p_t8_pkey, items_p_t8_embedding_idx, items_p_t8_embedding_idx1 - wszystkie valid
po DETACH + DROP: partycji = 8
```

## Znane ograniczenia

- Dane syntetyczne, 64 wymiary, 20 000 wierszy; jeden zestaw 20 zapytań i jedna budowa grafu.
- Nie mierzono czasów zapytań ani skalowania przy dziesiątkach/setkach partycji.
- `max_scan_tuples` sprawdzono tylko na monolicie z jednym filtrem (5%).
- Nie testowano `DETACH PARTITION CONCURRENTLY`, partycjonowania z poziomu EF Core ani `HalfVector` w EF Core.
- Kod z wydania #2 (fastembed) - nadal niezweryfikowany.
