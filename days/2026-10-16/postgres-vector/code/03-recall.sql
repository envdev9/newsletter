-- Recall@10 i liczba zwroconych wierszy: monolit vs tabela partycjonowana, oraz max_scan_tuples.
-- Prawda: dokladny kNN (enable_indexscan=off => Seq Scan + Sort). Uruchamiac po 01-setup.sql.
SET max_parallel_workers_per_gather = 0;

CREATE OR REPLACE FUNCTION bench(tbl text, filt text, OUT recall numeric, OUT rows_per_query numeric)
LANGUAGE plpgsql AS $$
DECLARE
    qv vector; exact int[]; approx int[]; hits int := 0; total int := 0; got int := 0; n int := 0;
BEGIN
    FOR qv IN SELECT v FROM queries ORDER BY q LOOP
        PERFORM set_config('enable_indexscan', 'off', true);
        PERFORM set_config('enable_bitmapscan', 'off', true);
        EXECUTE format('SELECT array_agg(id) FROM (SELECT id FROM %I WHERE %s ORDER BY embedding <=> $1 LIMIT 10) s', tbl, filt)
            INTO exact USING qv;
        PERFORM set_config('enable_indexscan', 'on', true);
        PERFORM set_config('enable_bitmapscan', 'on', true);
        EXECUTE format('SELECT array_agg(id) FROM (SELECT id FROM %I WHERE %s ORDER BY embedding <=> $1 LIMIT 10) s', tbl, filt)
            INTO approx USING qv;
        approx := COALESCE(approx, '{}');
        hits  := hits  + (SELECT count(*) FROM unnest(approx) a WHERE a = ANY (exact));
        total := total + cardinality(exact);
        got   := got   + cardinality(approx);
        n := n + 1;
    END LOOP;
    recall := round(hits::numeric / total, 3);
    rows_per_query := round(got::numeric / n, 1);
END $$;

\echo '=== 1. Bez filtra, ef_search = 10 (domyslne 40 pomijamy: tu widac roznice) ==='
SET hnsw.ef_search = 10;
SELECT 'monolit' AS tabela, * FROM bench('items_m', 'true')
UNION ALL
SELECT 'partycje x8', * FROM bench('items_p', 'true');

\echo '=== 2. Bez filtra, ef_search = 40 ==='
SET hnsw.ef_search = 40;
SELECT 'monolit' AS tabela, * FROM bench('items_m', 'true')
UNION ALL
SELECT 'partycje x8', * FROM bench('items_p', 'true');

\echo '=== 3. Filtr tenant = 3 (12,5% wierszy, klucz partycji), ef_search = 40, iterative_scan = off ==='
SET hnsw.iterative_scan = off;
SELECT 'monolit (post-filter)' AS tabela, * FROM bench('items_m', 'tenant = 3')
UNION ALL
SELECT 'partycje (pruning)', * FROM bench('items_p', 'tenant = 3');

\echo '=== 3b. Jak 3, ale ef_search = 100 ==='
SET hnsw.ef_search = 100;
SELECT 'monolit (post-filter)' AS tabela, * FROM bench('items_m', 'tenant = 3')
UNION ALL
SELECT 'partycje (pruning)', * FROM bench('items_p', 'tenant = 3');
SET hnsw.ef_search = 40;

\echo '=== 4. Filtr tier = 5 (5%, NIE klucz partycji) na monolicie, relaxed_order, rozne max_scan_tuples ==='
SET hnsw.iterative_scan = off;
SELECT 'iterative_scan=off' AS ustawienie, * FROM bench('items_m', 'tier = 5');
SET hnsw.iterative_scan = relaxed_order;
SET hnsw.max_scan_tuples = 100;
SELECT 'relaxed, max_scan_tuples=100' AS ustawienie, * FROM bench('items_m', 'tier = 5');
SET hnsw.max_scan_tuples = 500;
SELECT 'relaxed, max_scan_tuples=500' AS ustawienie, * FROM bench('items_m', 'tier = 5');
SET hnsw.max_scan_tuples = 2000;
SELECT 'relaxed, max_scan_tuples=2000' AS ustawienie, * FROM bench('items_m', 'tier = 5');
SET hnsw.max_scan_tuples = 20000;
SELECT 'relaxed, max_scan_tuples=20000 (domyslne)' AS ustawienie, * FROM bench('items_m', 'tier = 5');
