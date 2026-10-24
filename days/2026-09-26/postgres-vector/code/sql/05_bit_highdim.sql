-- 05_bit_highdim.sql: dlaczego binary quantization dla 128 wymiarow wyszla slabo?
-- Sprawdzamy na 1024 wymiarach (20 000 wierszy, 50 zapytan) - osobne tabele hd_*.
-- Nadal dane syntetyczne (centroidy + szum), wiec to test MECHANIKI (dlugosc kodu vs recall),
-- nie prognoza dla prawdziwych embeddingow.
\pset pager off
SET maintenance_work_mem = '512MB';
SET max_parallel_workers_per_gather = 0;
SET hnsw.iterative_scan = off;
DROP TABLE IF EXISTS hd_items, hd_queries, hd_centroids CASCADE;
SELECT setseed(0.7);

CREATE TABLE hd_centroids AS
SELECT c, array_agg(random() * 2 - 1 ORDER BY d) AS v
FROM generate_series(1, 30) c, generate_series(1, 1024) d GROUP BY c;

CREATE TABLE hd_items (id int PRIMARY KEY, emb vector(1024));
INSERT INTO hd_items
SELECT g.i, (SELECT array_agg(ce.v[d] + (random() - 0.5) * 0.6 ORDER BY d)
             FROM generate_series(1, 1024) d)::vector(1024)
FROM (SELECT i, 1 + (random() * 29)::int AS cl FROM generate_series(1, 20000) i) g
JOIN hd_centroids ce ON ce.c = g.cl;

CREATE TABLE hd_queries (qid int PRIMARY KEY, emb vector(1024), truth int[]);
INSERT INTO hd_queries
SELECT g.i, (SELECT array_agg(ce.v[d] + (random() - 0.5) * 0.6 ORDER BY d)
             FROM generate_series(1, 1024) d)::vector(1024)
FROM (SELECT i, 1 + (random() * 29)::int AS cl FROM generate_series(1, 50) i) g
JOIN hd_centroids ce ON ce.c = g.cl;
ANALYZE hd_items;

UPDATE hd_queries q SET truth =
  (SELECT array_agg(id) FROM (SELECT id FROM hd_items ORDER BY emb <=> q.emb LIMIT 10) s);

CREATE OR REPLACE FUNCTION bench_hd(sql text)
RETURNS TABLE(recall numeric, sr_ms numeric) AS $$
DECLARE q record; got int[]; t0 timestamptz; tot double precision := 0; rec double precision := 0;
BEGIN
  FOR q IN SELECT * FROM hd_queries LOOP
    EXECUTE 'SELECT array_agg(id) FROM (' || sql || ') s' INTO got USING q.emb;   -- rozgrzewka
    t0 := clock_timestamp();
    EXECUTE 'SELECT array_agg(id) FROM (' || sql || ') s' INTO got USING q.emb;
    tot := tot + extract(epoch FROM clock_timestamp() - t0) * 1000;
    rec := rec + cardinality(ARRAY(SELECT unnest(got) INTERSECT SELECT unnest(q.truth)))::double precision / 10;
  END LOOP;
  RETURN QUERY SELECT round((rec / 50)::numeric, 3), round((tot / 50)::numeric, 2);
END $$ LANGUAGE plpgsql;

CREATE INDEX hd_hnsw32 ON hd_items USING hnsw (emb vector_cosine_ops);
CREATE INDEX hd_hnsw_bit ON hd_items USING hnsw ((binary_quantize(emb)::bit(1024)) bit_hamming_ops);
SELECT pg_size_pretty(pg_relation_size('hd_items')) AS tabela,
       pg_size_pretty(pg_relation_size('hd_hnsw32')) AS hnsw_fp32,
       pg_size_pretty(pg_relation_size('hd_hnsw_bit')) AS hnsw_bit;

SET hnsw.ef_search = 40;
SELECT 'fp32 vector (1024D)' AS wariant, * FROM bench_hd('SELECT id FROM hd_items ORDER BY emb <=> $1 LIMIT 10');
SET hnsw.ef_search = 200;
SELECT 'bit + rerank 50' AS wariant, * FROM bench_hd(
  'SELECT id FROM (SELECT id, emb FROM hd_items ORDER BY binary_quantize(emb)::bit(1024) <~> binary_quantize($1)::bit(1024) LIMIT 50) c ORDER BY emb <=> $1 LIMIT 10');
SELECT 'bit + rerank 200' AS wariant, * FROM bench_hd(
  'SELECT id FROM (SELECT id, emb FROM hd_items ORDER BY binary_quantize(emb)::bit(1024) <~> binary_quantize($1)::bit(1024) LIMIT 200) c ORDER BY emb <=> $1 LIMIT 10');
