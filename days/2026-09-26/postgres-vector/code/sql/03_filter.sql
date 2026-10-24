-- 03_filter.sql: problem post-filtrowania w HNSW, iterative scan, B-tree, partial index.
\timing off
\pset pager off
SET maintenance_work_mem = '256MB';
SET max_parallel_workers_per_gather = 0;   -- jeden rdzen: powtarzalne porownanie

\echo '=== A. Budowa HNSW (m=16, ef_construction=64) ==='
\timing on
CREATE INDEX items_hnsw ON items USING hnsw (emb vector_cosine_ops) WITH (m = 16, ef_construction = 64);
\timing off
SELECT pg_size_pretty(pg_relation_size('items_hnsw')) AS rozmiar_hnsw;

\echo '=== B. Bez filtra: recall@10 (ef_search=40) ==='
SET hnsw.ef_search = 40;
SELECT * FROM bench('all', 'SELECT id FROM items ORDER BY emb <=> $1 LIMIT 10');

\echo '=== C. Z filtrem tenant_id (ok. 0,5% wierszy), ef_search=40, BEZ iterative scan ==='
SET hnsw.iterative_scan = off;
SELECT * FROM bench('tenant', 'SELECT id FROM items WHERE tenant_id = $2 ORDER BY emb <=> $1 LIMIT 10');

\echo '--- EXPLAIN ANALYZE jednego zapytania z filtrem (tenant 7) ---'
EXPLAIN (ANALYZE, COSTS OFF, TIMING OFF, SUMMARY OFF)
SELECT id FROM items WHERE tenant_id = 7
ORDER BY emb <=> (SELECT emb FROM queries WHERE qid = 1) LIMIT 10;

\echo '=== D. Zwiekszenie ef_search (40 -> 200 -> 1000) - bez iterative scan ==='
SET hnsw.ef_search = 200;
SELECT * FROM bench('tenant', 'SELECT id FROM items WHERE tenant_id = $2 ORDER BY emb <=> $1 LIMIT 10');
SET hnsw.ef_search = 1000;
SELECT * FROM bench('tenant', 'SELECT id FROM items WHERE tenant_id = $2 ORDER BY emb <=> $1 LIMIT 10');

\echo '=== E. hnsw.iterative_scan (pgvector 0.8.0+), ef_search=40 ==='
SET hnsw.ef_search = 40;
SET hnsw.iterative_scan = strict_order;
SELECT 'strict_order' AS tryb, * FROM bench('tenant', 'SELECT id FROM items WHERE tenant_id = $2 ORDER BY emb <=> $1 LIMIT 10');
SET hnsw.iterative_scan = relaxed_order;
SELECT 'relaxed_order' AS tryb, * FROM bench('tenant', 'SELECT id FROM items WHERE tenant_id = $2 ORDER BY emb <=> $1 LIMIT 10');

\echo '--- max_scan_tuples: bezpiecznik (domyslnie 20000) ---'
SHOW hnsw.max_scan_tuples;
SET hnsw.max_scan_tuples = 2000;
SELECT 'relaxed, max_scan_tuples=2000' AS tryb, * FROM bench('tenant', 'SELECT id FROM items WHERE tenant_id = $2 ORDER BY emb <=> $1 LIMIT 10');
RESET hnsw.max_scan_tuples;

\echo '--- EXPLAIN ANALYZE z iterative_scan = relaxed_order ---'
EXPLAIN (ANALYZE, COSTS OFF, TIMING OFF, SUMMARY OFF)
SELECT id FROM items WHERE tenant_id = 7
ORDER BY emb <=> (SELECT emb FROM queries WHERE qid = 1) LIMIT 10;

\echo '=== F. B-tree na tenant_id: planner moze wybrac dokladny plan (ok. 500 wierszy + sort) ==='
SET hnsw.iterative_scan = off;
CREATE INDEX items_tenant_btree ON items (tenant_id);
ANALYZE items;
EXPLAIN (ANALYZE, COSTS OFF, TIMING OFF, SUMMARY OFF)
SELECT id FROM items WHERE tenant_id = 7
ORDER BY emb <=> (SELECT emb FROM queries WHERE qid = 1) LIMIT 10;
SELECT 'btree+sort (dokladny)' AS plan, * FROM bench('tenant', 'SELECT id FROM items WHERE tenant_id = $2 ORDER BY emb <=> $1 LIMIT 10');
DROP INDEX items_tenant_btree;
ANALYZE items;

\echo '=== G. Partial index HNSW tylko dla "gorącego" tenanta 7 ==='
CREATE INDEX items_hnsw_t7 ON items USING hnsw (emb vector_cosine_ops) WHERE tenant_id = 7;
SELECT pg_size_pretty(pg_relation_size('items_hnsw_t7')) AS rozmiar_partial_t7;
-- indeks globalny items_hnsw nadal istnieje - planner wybiera partial, bo WHERE pasuje do jego predykatu
EXPLAIN (ANALYZE, COSTS OFF, TIMING OFF, SUMMARY OFF)
SELECT id FROM items WHERE tenant_id = 7
ORDER BY emb <=> (SELECT emb FROM queries WHERE qid = 1) LIMIT 10;
DROP INDEX items_hnsw_t7;
