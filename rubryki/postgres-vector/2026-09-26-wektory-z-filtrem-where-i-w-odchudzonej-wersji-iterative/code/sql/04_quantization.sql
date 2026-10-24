-- 04_quantization.sql: halfvec (float16) i binary quantization (bit) + rerank. Rozmiar i recall@10.
\pset pager off
SET maintenance_work_mem = '256MB';
SET max_parallel_workers_per_gather = 0;
SET hnsw.iterative_scan = off;
SET hnsw.ef_search = 40;

\echo '=== Rozmiary: tabela i indeks float32 (wersja bazowa z pliku 03) ==='
SELECT pg_size_pretty(pg_relation_size('items')) AS tabela,
       pg_size_pretty(pg_relation_size('items_hnsw')) AS hnsw_vector_fp32;

\echo '=== halfvec: indeks wyrazeniowy na rzutowaniu (kolumna zostaje vector) ==='
\timing on
CREATE INDEX items_hnsw_half ON items USING hnsw ((emb::halfvec(128)) halfvec_cosine_ops) WITH (m = 16, ef_construction = 64);
\timing off
SELECT pg_size_pretty(pg_relation_size('items_hnsw_half')) AS hnsw_halfvec_fp16;

\echo '=== binary quantization: 1 bit na wymiar, Hamming ==='
\timing on
CREATE INDEX items_hnsw_bit ON items USING hnsw ((binary_quantize(emb)::bit(128)) bit_hamming_ops) WITH (m = 16, ef_construction = 64);
\timing off
SELECT pg_size_pretty(pg_relation_size('items_hnsw_bit')) AS hnsw_bit_1bit;

\echo '=== Planer: ktory indeks jest uzyty (wymaga dokladnie tego samego wyrazenia) ==='
-- Zeby wymusic konkretny indeks, na czas testu wylaczamy pozostale (DROP w transakcji + ROLLBACK).
BEGIN;
DROP INDEX items_hnsw;
DROP INDEX items_hnsw_bit;
EXPLAIN (COSTS OFF)
SELECT id FROM items ORDER BY emb::halfvec(128) <=> (SELECT emb::halfvec(128) FROM queries WHERE qid = 1) LIMIT 10;
ROLLBACK;

BEGIN;
DROP INDEX items_hnsw;
DROP INDEX items_hnsw_half;
EXPLAIN (COSTS OFF)
SELECT id FROM items ORDER BY binary_quantize(emb)::bit(128) <~> (SELECT binary_quantize(emb)::bit(128) FROM queries WHERE qid = 1) LIMIT 10;
ROLLBACK;

\echo '=== Recall@10 i czas (ef_search=40, prawda = dokladne float32) ==='
\echo '--- fp32 vector ---'
SELECT 'fp32 vector' AS wariant, * FROM bench('all',
  'SELECT id FROM items ORDER BY emb <=> $1 LIMIT 10');
\echo '--- halfvec ---'
SELECT 'halfvec' AS wariant, * FROM bench('all',
  'SELECT id FROM items ORDER BY emb::halfvec(128) <=> $1::halfvec(128) LIMIT 10');
\echo '--- bit, BEZ rerank (top 10 po Hammingu) ---'
SELECT 'bit bez rerank' AS wariant, * FROM bench('all',
  'SELECT id FROM items ORDER BY binary_quantize(emb)::bit(128) <~> binary_quantize($1)::bit(128) LIMIT 10');
\echo '--- bit + rerank: 40 / 100 / 400 kandydatow, potem dokladne <=> na fp32 ---'
SET hnsw.ef_search = 400;   -- ef_search musi byc >= liczby kandydatow
SELECT 'bit + rerank 40' AS wariant, * FROM bench('all',
  'SELECT id FROM (SELECT id, emb FROM items ORDER BY binary_quantize(emb)::bit(128) <~> binary_quantize($1)::bit(128) LIMIT 40) c ORDER BY emb <=> $1 LIMIT 10');
SELECT 'bit + rerank 100' AS wariant, * FROM bench('all',
  'SELECT id FROM (SELECT id, emb FROM items ORDER BY binary_quantize(emb)::bit(128) <~> binary_quantize($1)::bit(128) LIMIT 100) c ORDER BY emb <=> $1 LIMIT 10');
SELECT 'bit + rerank 400' AS wariant, * FROM bench('all',
  'SELECT id FROM (SELECT id, emb FROM items ORDER BY binary_quantize(emb)::bit(128) <~> binary_quantize($1)::bit(128) LIMIT 400) c ORDER BY emb <=> $1 LIMIT 10');

\echo '=== Podsumowanie rozmiarow ==='
SELECT indexname, pg_size_pretty(pg_relation_size(indexname::regclass)) AS rozmiar
FROM pg_indexes WHERE tablename = 'items' AND indexname LIKE 'items_hnsw%' ORDER BY 1;
