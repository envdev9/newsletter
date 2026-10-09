-- Limity wymiarow HNSW: vector <= 2000, halfvec <= 4000. Rozmiar indeksu przy 1536 wymiarach.
-- Uruchomienie: docker exec -i <kontener> psql -U postgres -d demo -f - < dims.sql
\set ON_ERROR_STOP off
\timing off

DROP TABLE IF EXISTS big;
CREATE TABLE big (id int PRIMARY KEY, e3072 vector(3072), e1536 vector(1536));

-- losowe wektory (nie sa embeddingami - tu mierzymy tylko rozmiary i limity); 3000 wierszy
INSERT INTO big
SELECT g,
       (SELECT array_agg(random()::float4) FROM generate_series(1, 3072) k WHERE g IS NOT NULL)::vector(3072),
       (SELECT array_agg(random()::float4) FROM generate_series(1, 1536) k WHERE g IS NOT NULL)::vector(1536)
FROM generate_series(1, 3000) g;

\echo === 3072 wymiary: HNSW na vector(3072) ===
CREATE INDEX ON big USING hnsw (e3072 vector_cosine_ops);

\echo === 3072 wymiary: HNSW na rzutowaniu e3072::halfvec(3072) ===
CREATE INDEX ix_big_3072_half ON big USING hnsw ((e3072::halfvec(3072)) halfvec_cosine_ops);
SELECT pg_relation_size('ix_big_3072_half') AS bytes_3072_half;

\echo === 4001 wymiary: HNSW na halfvec(4001) ===
CREATE TABLE toobig (e halfvec(4001));
CREATE INDEX ON toobig USING hnsw (e halfvec_cosine_ops);

\echo === 1536 wymiary: rozmiary indeksow ===
CREATE INDEX ix_big_1536_vec  ON big USING hnsw (e1536 vector_cosine_ops);
CREATE INDEX ix_big_1536_half ON big USING hnsw ((e1536::halfvec(1536)) halfvec_cosine_ops);
SELECT pg_relation_size('ix_big_1536_vec')  AS bytes_vec,
       pg_relation_size('ix_big_1536_half') AS bytes_half,
       round(pg_relation_size('ix_big_1536_vec')::numeric / pg_relation_size('ix_big_1536_half'), 2) AS ratio;
SELECT pg_column_size(e1536) AS vec_1536_col, pg_column_size(e1536::halfvec(1536)) AS half_1536_col FROM big WHERE id = 1;

DROP TABLE toobig;
