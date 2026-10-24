-- Wydanie #23: partycjonowanie tabeli z indeksem HNSW + max_scan_tuples
-- Dane SYNTETYCZNE i deterministyczne (setseed): 50 klastrow w 64 wymiarach + szum.
-- Tworzy dwie tabele z IDENTYCZNYMI danymi:
--   items_m  - monolit (jedna tabela, jeden indeks HNSW)
--   items_p  - PARTITION BY LIST (tenant), 8 partycji, indeks HNSW na rodzicu (powstaje 8 indeksow)

CREATE EXTENSION IF NOT EXISTS vector;
SELECT setseed(0.42);

DROP TABLE IF EXISTS items_p, items_m, centers, queries CASCADE;

-- 50 srodkow klastrow
CREATE TABLE centers AS
SELECT c AS cid,
       (SELECT array_agg(random() * 2 - 1 + (c + d) * 0) FROM generate_series(1, 64) d) AS v
FROM generate_series(0, 49) c;

-- monolit: 20 000 wierszy; tenant = 8 wartosci (rowny rozklad), tier = 20 wartosci (5% wierszy kazdy, bez indeksu)
CREATE TABLE items_m (
    id        int PRIMARY KEY,
    tenant    int NOT NULL,
    tier      int NOT NULL,
    embedding vector(64) NOT NULL
);

INSERT INTO items_m
SELECT g,
       g % 8,
       (g / 8) % 20,
       (SELECT array_agg(c.v[d] + (random() - 0.5) * 0.6 ORDER BY d)
          FROM centers c, generate_series(1, 64) d
         WHERE c.cid = g % 50)::vector(64)
FROM generate_series(1, 20000) g;

-- partycjonowana kopia tych samych danych (PK musi zawierac klucz partycji)
CREATE TABLE items_p (
    id        int NOT NULL,
    tenant    int NOT NULL,
    tier      int NOT NULL,
    embedding vector(64) NOT NULL,
    PRIMARY KEY (tenant, id)
) PARTITION BY LIST (tenant);

DO $$
BEGIN
    FOR t IN 0..7 LOOP
        EXECUTE format('CREATE TABLE items_p_t%s PARTITION OF items_p FOR VALUES IN (%s)', t, t);
    END LOOP;
END $$;

INSERT INTO items_p SELECT id, tenant, tier, embedding FROM items_m;

-- 20 wektorow zapytan (te same klastry, ale NIE wiersze z tabeli)
CREATE TABLE queries AS
SELECT q,
       (SELECT array_agg(c.v[d] + (random() - 0.5) * 0.6 ORDER BY d)
          FROM centers c, generate_series(1, 64) d
         WHERE c.cid = (q * 7) % 50)::vector(64) AS v
FROM generate_series(1, 20) q;

-- indeksy: monolit i partycjonowana (CREATE INDEX na rodzicu tworzy indeks na kazdej partycji)
\timing on
CREATE INDEX ix_m_hnsw ON items_m USING hnsw (embedding vector_cosine_ops) WITH (m = 16, ef_construction = 64);
CREATE INDEX ix_p_hnsw ON items_p USING hnsw (embedding vector_cosine_ops) WITH (m = 16, ef_construction = 64);
\timing off

ANALYZE items_m;
ANALYZE items_p;

SELECT 'monolit'  AS tabela, pg_size_pretty(pg_relation_size('ix_m_hnsw')) AS rozmiar_indeksu
UNION ALL
SELECT 'partycje (suma)', pg_size_pretty(sum(pg_relation_size(indexrelid))::bigint)
  FROM pg_index WHERE indrelid IN (SELECT inhrelid FROM pg_inherits WHERE inhparent = 'items_p'::regclass)
   AND indexrelid::regclass::text LIKE '%embedding%';

SELECT tenant, count(*) FROM items_p GROUP BY tenant ORDER BY tenant;
