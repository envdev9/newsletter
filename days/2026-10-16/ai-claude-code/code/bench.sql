-- Koszt zapisu i rozmiar indeksu GIN gin_trgm_ops + ILIKE/citext w PostgreSQL 16.
-- Uruchomienie: psql -U postgres -v ON_ERROR_STOP=1 -f bench.sql
-- Wszystko dzieje sie w osobnej bazie prasowka_ai_1016 (tworzona i usuwana tu).
\set QUIET on
\pset pager off
\timing off
DROP DATABASE IF EXISTS prasowka_ai_1016;
CREATE DATABASE prasowka_ai_1016;
\c prasowka_ai_1016
CREATE EXTENSION pg_trgm;
CREATE EXTENSION citext;
CREATE EXTENSION pageinspect;

-- Dane: 200 000 adresow, setseed => powtarzalne. Co 3. adres ma wielkie litery w czesci lokalnej.
SELECT setseed(0.42);
CREATE TABLE src AS
SELECT g AS id,
       CASE WHEN g % 3 = 0 THEN 'User' ELSE 'user' END || g || '.' || substr(md5(g::text), 1, 12)
         || (ARRAY['@corp.example','@mail.example','@shop.example','@Test.Example'])[1 + g % 4] AS email
FROM generate_series(1, 200000) g;

-- Cztery warianty tabeli: bez indeksu, btree, btree pattern_ops, GIN trigram.
CREATE TABLE t_none   (id int, email varchar(100));
CREATE TABLE t_btree  (id int, email varchar(100));
CREATE TABLE t_pat    (id int, email varchar(100));
CREATE TABLE t_gin    (id int, email varchar(100));
CREATE INDEX ix_btree ON t_btree (email);
CREATE INDEX ix_pat   ON t_pat   (email varchar_pattern_ops);
CREATE INDEX ix_gin   ON t_gin   USING gin (email gin_trgm_ops);

\echo '=== A. INSERT 200 000 wierszy (EXPLAIN ANALYZE: Execution Time), indeksy puste na starcie ==='
\echo '-- t_none'
EXPLAIN (ANALYZE, COSTS OFF, TIMING OFF) INSERT INTO t_none  SELECT id, email FROM src;
\echo '-- t_btree'
EXPLAIN (ANALYZE, COSTS OFF, TIMING OFF) INSERT INTO t_btree SELECT id, email FROM src;
\echo '-- t_pat'
EXPLAIN (ANALYZE, COSTS OFF, TIMING OFF) INSERT INTO t_pat   SELECT id, email FROM src;
\echo '-- t_gin'
EXPLAIN (ANALYZE, COSTS OFF, TIMING OFF) INSERT INTO t_gin   SELECT id, email FROM src;

ANALYZE t_none; ANALYZE t_btree; ANALYZE t_pat; ANALYZE t_gin;

\echo '=== B. Rozmiar tabeli i indeksow po inserice ==='
SELECT 'tabela (heap)' AS obiekt, pg_size_pretty(pg_relation_size('t_none')) AS rozmiar
UNION ALL SELECT 'ix_btree',  pg_size_pretty(pg_relation_size('ix_btree'))
UNION ALL SELECT 'ix_pat',    pg_size_pretty(pg_relation_size('ix_pat'))
UNION ALL SELECT 'ix_gin',    pg_size_pretty(pg_relation_size('ix_gin'));

\echo '=== C. Dokladanie 20 000 wierszy do JUZ zaindeksowanej tabeli (insert przyrostowy) ==='
CREATE TABLE extra AS
SELECT 200000 + g AS id, 'user' || (200000 + g) || '.' || substr(md5((200000 + g)::text), 1, 12) || '@corp.example' AS email
FROM generate_series(1, 20000) g;
\echo '-- t_none'
EXPLAIN (ANALYZE, COSTS OFF, TIMING OFF) INSERT INTO t_none  SELECT id, email FROM extra;
\echo '-- t_btree'
EXPLAIN (ANALYZE, COSTS OFF, TIMING OFF) INSERT INTO t_btree SELECT id, email FROM extra;
\echo '-- t_gin'
EXPLAIN (ANALYZE, COSTS OFF, TIMING OFF) INSERT INTO t_gin   SELECT id, email FROM extra;
SELECT 'ix_gin po insercie przyrostowym' AS obiekt, pg_size_pretty(pg_relation_size('ix_gin')) AS rozmiar;

\echo '=== D. UPDATE email 20 000 wierszy (zmiana kolumny indeksowanej) ==='
\echo '-- t_none'
EXPLAIN (ANALYZE, COSTS OFF, TIMING OFF) UPDATE t_none  SET email = email || 'x' WHERE id <= 20000;
\echo '-- t_btree'
EXPLAIN (ANALYZE, COSTS OFF, TIMING OFF) UPDATE t_btree SET email = email || 'x' WHERE id <= 20000;
\echo '-- t_gin'
EXPLAIN (ANALYZE, COSTS OFF, TIMING OFF) UPDATE t_gin   SET email = email || 'x' WHERE id <= 20000;
SELECT 'ix_gin po UPDATE' AS obiekt, pg_size_pretty(pg_relation_size('ix_gin')) AS rozmiar;

\echo '=== E. gin_pending_list_limit / fastupdate: ile siedzi w pending list ==='
SELECT n_pending_pages, n_pending_tuples FROM gin_metapage_info(get_raw_page('ix_gin', 0)) \gset
\echo 'n_pending_pages / n_pending_tuples:' :n_pending_pages '/' :n_pending_tuples
