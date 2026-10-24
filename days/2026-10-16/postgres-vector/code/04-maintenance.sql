-- Utrzymanie: przebudowa indeksu JEDNEJ partycji, wzorzec "CONCURRENTLY" dla tabeli partycjonowanej,
-- nowa partycja, ATTACH z gotowym indeksem, DETACH + DROP. Uruchamiac po 01-setup.sql.
-- UWAGA: krok 2 CELOWO konczy sie bledem (to jest tresc kroku) - nie uzywaj ON_ERROR_STOP.
\timing on

\echo '=== 1. REINDEX jednej partycji (2500 wierszy) vs CREATE INDEX calosci (20 000: ok. 4-6 s w 01-setup) ==='
REINDEX INDEX items_p_t3_embedding_idx;

\echo '=== 2. CREATE INDEX CONCURRENTLY wprost na rodzicu (PG16) ==='
CREATE INDEX CONCURRENTLY ix_p_l2 ON items_p USING hnsw (embedding vector_l2_ops);

\echo '=== 3. Wzorzec: ON ONLY (rodzic, indeks "invalid") + CONCURRENTLY per partycja + ATTACH INDEX ==='
CREATE INDEX ix_p_l2 ON ONLY items_p USING hnsw (embedding vector_l2_ops);
SELECT indexrelid::regclass AS indeks, indisvalid FROM pg_index WHERE indexrelid = 'ix_p_l2'::regclass;
CREATE INDEX CONCURRENTLY items_p_t0_l2 ON items_p_t0 USING hnsw (embedding vector_l2_ops);
ALTER INDEX ix_p_l2 ATTACH PARTITION items_p_t0_l2;
SELECT indexrelid::regclass AS indeks, indisvalid FROM pg_index WHERE indexrelid = 'ix_p_l2'::regclass;
CREATE INDEX CONCURRENTLY items_p_t1_l2 ON items_p_t1 USING hnsw (embedding vector_l2_ops);
ALTER INDEX ix_p_l2 ATTACH PARTITION items_p_t1_l2;
CREATE INDEX CONCURRENTLY items_p_t2_l2 ON items_p_t2 USING hnsw (embedding vector_l2_ops);
ALTER INDEX ix_p_l2 ATTACH PARTITION items_p_t2_l2;
CREATE INDEX CONCURRENTLY items_p_t3_l2 ON items_p_t3 USING hnsw (embedding vector_l2_ops);
ALTER INDEX ix_p_l2 ATTACH PARTITION items_p_t3_l2;
CREATE INDEX CONCURRENTLY items_p_t4_l2 ON items_p_t4 USING hnsw (embedding vector_l2_ops);
ALTER INDEX ix_p_l2 ATTACH PARTITION items_p_t4_l2;
CREATE INDEX CONCURRENTLY items_p_t5_l2 ON items_p_t5 USING hnsw (embedding vector_l2_ops);
ALTER INDEX ix_p_l2 ATTACH PARTITION items_p_t5_l2;
CREATE INDEX CONCURRENTLY items_p_t6_l2 ON items_p_t6 USING hnsw (embedding vector_l2_ops);
ALTER INDEX ix_p_l2 ATTACH PARTITION items_p_t6_l2;
\echo '--- przed ostatnia partycja: indeks rodzica nadal invalid ---'
SELECT indexrelid::regclass AS indeks, indisvalid FROM pg_index WHERE indexrelid = 'ix_p_l2'::regclass;
CREATE INDEX CONCURRENTLY items_p_t7_l2 ON items_p_t7 USING hnsw (embedding vector_l2_ops);
ALTER INDEX ix_p_l2 ATTACH PARTITION items_p_t7_l2;
\echo '--- po ostatniej: valid ---'
SELECT indexrelid::regclass AS indeks, indisvalid FROM pg_index WHERE indexrelid = 'ix_p_l2'::regclass;

\echo '=== 4. Nowa partycja: oba indeksy z rodzica powstaja automatycznie ==='
CREATE TABLE items_p_t8 PARTITION OF items_p FOR VALUES IN (8);
SELECT indexrelid::regclass AS indeks, indisvalid FROM pg_index WHERE indrelid = 'items_p_t8'::regclass ORDER BY 1;

\echo '=== 5. DETACH + DROP partycji: usuniecie danych tenanta bez DELETE (bez martwych krotek w grafie HNSW) ==='
ALTER TABLE items_p DETACH PARTITION items_p_t8;
DROP TABLE items_p_t8;
SELECT count(*) AS partycji FROM pg_inherits WHERE inhparent = 'items_p'::regclass;
