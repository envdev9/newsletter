-- 01_data.sql: deterministyczny zbiór 100 000 wektorów (128 wymiarów) + 100 zapytań.
-- To NIE są embeddingi prawdziwego modelu: 50 losowych centroidów + szum (setseed => powtarzalne).
-- Struktura klastrowa naśladuje "tematy" w korpusie; tenant_id jest LOSOWY i niezależny od
-- podobieństwa (to typowy przypadek: filtr biznesowy nie ma nic wspólnego z geometrią).
CREATE EXTENSION IF NOT EXISTS vector;
SELECT extversion AS wersja_pgvector FROM pg_extension WHERE extname = 'vector';

DROP TABLE IF EXISTS items, queries, truth, centroids CASCADE;
SELECT setseed(0.42);

CREATE TABLE centroids AS
SELECT c, array_agg(random() * 2 - 1 ORDER BY d) AS v
FROM generate_series(1, 50) c, generate_series(1, 128) d
GROUP BY c;

CREATE TABLE items (
  id        int PRIMARY KEY,
  tenant_id int NOT NULL,          -- 200 tenantów => filtr zostawia ok. 0,5% wierszy
  emb       vector(128) NOT NULL
);

-- wektor = centroid klastra + szum; podzapytanie skorelowane (ce.v) => liczone osobno dla wiersza
INSERT INTO items
SELECT g.i, g.tenant,
       (SELECT array_agg(ce.v[d] + (random() - 0.5) * 0.6 ORDER BY d)
        FROM generate_series(1, 128) d)::vector(128)
FROM (SELECT i, 1 + (random() * 49)::int AS cl, 1 + (random() * 199)::int AS tenant
      FROM generate_series(1, 100000) i) g
JOIN centroids ce ON ce.c = g.cl;

CREATE TABLE queries (
  qid       int PRIMARY KEY,
  tenant_id int NOT NULL,
  emb       vector(128) NOT NULL
);

INSERT INTO queries
SELECT g.i, g.tenant,
       (SELECT array_agg(ce.v[d] + (random() - 0.5) * 0.6 ORDER BY d)
        FROM generate_series(1, 128) d)::vector(128)
FROM (SELECT i, 1 + (random() * 49)::int AS cl, 1 + (random() * 199)::int AS tenant
      FROM generate_series(1, 100) i) g
JOIN centroids ce ON ce.c = g.cl;

ANALYZE items;
ANALYZE queries;

SELECT count(*) AS wierszy,
       count(DISTINCT tenant_id) AS tenantow,
       round(avg(c), 1) AS sr_wierszy_na_tenanta,
       pg_size_pretty(pg_relation_size('items')) AS rozmiar_tabeli
FROM (SELECT tenant_id, count(*) OVER (PARTITION BY tenant_id) AS c FROM items) s;
