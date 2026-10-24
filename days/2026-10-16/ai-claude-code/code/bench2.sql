-- Czesc 2: budowa GIN vs insert po insercie, fastupdate=off, ILIKE / lower() / citext.
-- Wymaga bench.sql uruchomionego wczesniej (korzysta z tabel w bazie prasowka_ai_1016).
\set QUIET on
\pset pager off
\c prasowka_ai_1016

\echo '=== F. Budowa indeksu na gotowej tabeli (CREATE INDEX) vs insert do pustej tabeli z indeksem ==='
\timing on
DROP INDEX ix_gin;
CREATE INDEX ix_gin ON t_gin USING gin (email gin_trgm_ops);
DROP INDEX ix_btree;
CREATE INDEX ix_btree ON t_btree (email);
\timing off
SELECT 'ix_gin po CREATE INDEX' AS obiekt, pg_size_pretty(pg_relation_size('ix_gin')) AS rozmiar
UNION ALL SELECT 'ix_btree po CREATE INDEX', pg_size_pretty(pg_relation_size('ix_btree'))
UNION ALL SELECT 'heap t_gin', pg_size_pretty(pg_relation_size('t_gin'));

\echo '=== G. Insert 20 000 do t_gin: fastupdate on (domyslnie) vs off ==='
CREATE TABLE extra2 AS
SELECT 300000 + g AS id, 'user' || (300000 + g) || '.' || substr(md5((300000 + g)::text), 1, 12) || '@corp.example' AS email
FROM generate_series(1, 20000) g;
\echo '-- fastupdate = on'
EXPLAIN (ANALYZE, COSTS OFF, TIMING OFF) INSERT INTO t_gin SELECT id, email FROM extra2;
SELECT n_pending_pages, n_pending_tuples FROM gin_metapage_info(get_raw_page('ix_gin', 0));
ALTER INDEX ix_gin SET (fastupdate = off);
CREATE TABLE extra3 AS
SELECT 400000 + g AS id, 'user' || (400000 + g) || '.' || substr(md5((400000 + g)::text), 1, 12) || '@corp.example' AS email
FROM generate_series(1, 20000) g;
\echo '-- fastupdate = off'
EXPLAIN (ANALYZE, COSTS OFF, TIMING OFF) INSERT INTO t_gin SELECT id, email FROM extra3;
SELECT n_pending_pages, n_pending_tuples FROM gin_metapage_info(get_raw_page('ix_gin', 0));
\echo '-- koszt odroczony: pierwszy SELECT po insercie z fastupdate=on czyta pending list (vacuum/gin_clean_pending_list)'
ALTER INDEX ix_gin SET (fastupdate = on);
SELECT gin_clean_pending_list('ix_gin') AS wyczyszczone_strony;
ANALYZE t_gin;

\echo '=== H. ILIKE / lower() / citext ==='
SELECT email AS e FROM src WHERE id = 77777 \gset
SELECT upper(:'e') AS e_upper \gset
\echo 'szukany adres:' :'e'
\echo 'wersja WIELKIMI:' :'e_upper'

CREATE TABLE t_lower (id int, email varchar(100));
INSERT INTO t_lower SELECT id, email FROM src;
CREATE INDEX ix_lower ON t_lower (lower(email));
CREATE TABLE t_ci (id int, email citext);
INSERT INTO t_ci SELECT id, email FROM src;
CREATE INDEX ix_ci ON t_ci (email);
ANALYZE t_lower; ANALYZE t_ci;

\echo '-- H1. varchar + btree(email), WHERE lower(email) = lower(:e_upper)  [to robi ToLower() w LINQ]'
EXPLAIN (ANALYZE, BUFFERS, COSTS OFF, TIMING OFF) SELECT id FROM t_btree WHERE lower(email) = lower(:'e_upper');
\echo '-- H2. varchar + btree(lower(email)), to samo zapytanie'
EXPLAIN (ANALYZE, BUFFERS, COSTS OFF, TIMING OFF) SELECT id FROM t_lower WHERE lower(email) = lower(:'e_upper');
\echo '-- H3. citext + btree(email), WHERE email = :e_upper'
EXPLAIN (ANALYZE, BUFFERS, COSTS OFF, TIMING OFF) SELECT id FROM t_ci WHERE email = :'e_upper';
\echo '-- H4. varchar + GIN trgm, WHERE email ILIKE ...'
EXPLAIN (ANALYZE, BUFFERS, COSTS OFF, TIMING OFF) SELECT id FROM t_gin WHERE email ILIKE '%' || :'e_upper' || '%';
\echo '-- H5. varchar + GIN trgm, WHERE email ILIKE :e_upper (bez %) = rownosc bez wzgledu na wielkosc'
EXPLAIN (ANALYZE, BUFFERS, COSTS OFF, TIMING OFF) SELECT id FROM t_gin WHERE email ILIKE :'e_upper';
\echo '-- H6. varchar + btree(varchar_pattern_ops), WHERE email ILIKE prefix%'
EXPLAIN (ANALYZE, BUFFERS, COSTS OFF, TIMING OFF) SELECT id FROM t_pat WHERE email ILIKE 'USER77777.%';
\echo '-- H7. varchar + btree(lower(email)) bez pattern_ops, WHERE lower(email) LIKE prefix%'
EXPLAIN (ANALYZE, BUFFERS, COSTS OFF, TIMING OFF) SELECT id FROM t_lower WHERE lower(email) LIKE 'user77777.%';
\echo '-- H8. citext + btree, WHERE email LIKE prefix% (citext: LIKE jest case-insensitive)'
EXPLAIN (ANALYZE, BUFFERS, COSTS OFF, TIMING OFF) SELECT id FROM t_ci WHERE email LIKE 'USER77777.%';
\echo '-- H9. czy citext ma klase operatorow gin_trgm_ops?'
\set ON_ERROR_STOP off
CREATE INDEX ix_ci_gin ON t_ci USING gin (email gin_trgm_ops);
\echo '-- H10. citext z rzutowaniem na text w wyrazeniu indeksu'
CREATE INDEX ix_ci_gin2 ON t_ci USING gin ((email::text) gin_trgm_ops);
\set ON_ERROR_STOP on
\echo '-- H11. citext + GIN(email::text), ILIKE na tym samym wyrazeniu'
EXPLAIN (ANALYZE, BUFFERS, COSTS OFF, TIMING OFF) SELECT id FROM t_ci WHERE email::text ILIKE '%' || :'e_upper' || '%';

\echo '-- H12. citext + GIN(email gin_trgm_ops) bezposrednio: indeks istnieje (H9 sie powiodlo), ale czy LIKE na citext go uzywa?'
EXPLAIN (ANALYZE, BUFFERS, COSTS OFF, TIMING OFF) SELECT id FROM t_ci WHERE email LIKE '%USER77777.22A4D9B04FE9%';

\echo '=== I. Rozmiary: lower(email) btree, citext btree ==='
SELECT 'ix_lower (btree lower)' AS obiekt, pg_size_pretty(pg_relation_size('ix_lower')) AS rozmiar
UNION ALL SELECT 'ix_ci (btree citext)', pg_size_pretty(pg_relation_size('ix_ci'));
