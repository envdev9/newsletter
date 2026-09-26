-- 02_bench_fn.sql: prawda (dokladni sasiedzi, Seq Scan - jeszcze nie ma zadnego indeksu)
-- oraz funkcja bench(), ktora mierzy recall@10 i czas wybranego zapytania.
-- Zapytanie przekazujemy jako tekst z parametrami: $1 = wektor zapytania, $2 = tenant_id.
DROP TABLE IF EXISTS truth;
CREATE TABLE truth (scn text, qid int, ids int[], PRIMARY KEY (scn, qid));

-- prawda bez filtra
INSERT INTO truth
SELECT 'all', q.qid,
       (SELECT array_agg(id) FROM (SELECT id FROM items ORDER BY emb <=> q.emb LIMIT 10) s)
FROM queries q;

-- prawda z filtrem tenant_id = tenant zapytania
INSERT INTO truth
SELECT 'tenant', q.qid,
       (SELECT array_agg(id) FROM (SELECT id FROM items WHERE tenant_id = q.tenant_id
                                   ORDER BY emb <=> q.emb LIMIT 10) s)
FROM queries q;

-- mala prawda dla wariantu quantization nie jest potrzebna: uzywa scenariusza 'all'.

CREATE OR REPLACE FUNCTION bench(scn text, sql text)
RETURNS TABLE(recall numeric, sr_wierszy numeric, sr_ms numeric, p95_ms numeric) AS $$
DECLARE
  q record; got int[]; want int[]; t0 timestamptz; ms double precision[] := '{}';
  rec double precision[] := '{}'; cnt double precision[] := '{}';
BEGIN
  FOR q IN SELECT * FROM queries ORDER BY qid LOOP
    SELECT ids INTO want FROM truth WHERE truth.scn = bench.scn AND qid = q.qid;
    -- przebieg rozgrzewkowy (cache), potem mierzony
    EXECUTE 'SELECT array_agg(id) FROM (' || sql || ') s' INTO got USING q.emb, q.tenant_id;
    t0 := clock_timestamp();
    EXECUTE 'SELECT array_agg(id) FROM (' || sql || ') s' INTO got USING q.emb, q.tenant_id;
    ms := ms || (extract(epoch FROM clock_timestamp() - t0) * 1000);
    cnt := cnt || coalesce(cardinality(got), 0);
    rec := rec || (CASE WHEN want IS NULL THEN 1.0 ELSE
             cardinality(ARRAY(SELECT unnest(coalesce(got, '{}')) INTERSECT SELECT unnest(want)))::double precision
             / cardinality(want) END);
  END LOOP;
  RETURN QUERY SELECT
    round((SELECT avg(x) FROM unnest(rec) x)::numeric, 3),
    round((SELECT avg(x) FROM unnest(cnt) x)::numeric, 1),
    round((SELECT avg(x) FROM unnest(ms) x)::numeric, 2),
    round((SELECT percentile_cont(0.95) WITHIN GROUP (ORDER BY x) FROM unnest(ms) x)::numeric, 2);
END $$ LANGUAGE plpgsql;

SELECT scn, count(*) AS zapytan, round(avg(cardinality(ids)), 1) AS sr_dlugosc_prawdy
FROM truth GROUP BY scn;
