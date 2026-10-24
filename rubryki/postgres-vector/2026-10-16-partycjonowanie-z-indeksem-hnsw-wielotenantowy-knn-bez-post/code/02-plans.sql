-- Plany zapytan kNN na tabeli partycjonowanej. Uruchamiac po 01-setup.sql.
-- Wektor zapytania jako podzapytanie (InitPlan) - dzieki temu plan nie jest zasypany 64 liczbami.
SET max_parallel_workers_per_gather = 0;

\echo '=== A. Filtr po kluczu partycji (stala): pruning przy planowaniu ==='
EXPLAIN (COSTS OFF)
SELECT id FROM items_p WHERE tenant = 3
 ORDER BY embedding <=> (SELECT v FROM queries WHERE q = 1) LIMIT 10;

\echo '=== B. Bez filtra: kazda z 8 partycji przeszukiwana osobno, wyniki scalane (Merge Append) ==='
EXPLAIN (COSTS OFF)
SELECT id FROM items_p
 ORDER BY embedding <=> (SELECT v FROM queries WHERE q = 1) LIMIT 10;

\echo '=== C. Filtr jako PARAMETR (prepared statement, generic plan): pruning w czasie wykonania ==='
\set QUIET on
SELECT v AS qv FROM queries WHERE q = 1 \gset
\set QUIET off
SET plan_cache_mode = force_generic_plan;
PREPARE kn(int, vector) AS
  SELECT id FROM items_p WHERE tenant = $1 ORDER BY embedding <=> $2 LIMIT 10;
EXPLAIN (COSTS OFF, ANALYZE, TIMING OFF, SUMMARY OFF)
EXECUTE kn(3, :'qv');
DEALLOCATE kn;
RESET plan_cache_mode;

\echo '=== D. Filtr po kolumnie spoza klucza partycji (tier=5): brak pruningu, wszystkie partycje ==='
EXPLAIN (COSTS OFF)
SELECT id FROM items_p WHERE tier = 5
 ORDER BY embedding <=> (SELECT v FROM queries WHERE q = 1) LIMIT 10;

\echo '=== E. To samo na monolicie: planner idzie po HNSW z Filter na koncu ==='
EXPLAIN (COSTS OFF)
SELECT id FROM items_m WHERE tier = 5
 ORDER BY embedding <=> (SELECT v FROM queries WHERE q = 1) LIMIT 10;
