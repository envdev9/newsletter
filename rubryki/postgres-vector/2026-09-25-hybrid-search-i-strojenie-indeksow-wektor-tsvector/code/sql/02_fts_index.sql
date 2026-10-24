-- Po załadowaniu danych: indeks GIN na tsvector (część "słownikowa" hybrid search).
CREATE INDEX kb_tsv_gin ON kb USING gin (tsv);
-- Indeks wektorowy dla kb (na 24 wierszach planner i tak go zignoruje - to tylko komplet).
CREATE INDEX kb_emb_hnsw ON kb USING hnsw (emb vector_cosine_ops);
ANALYZE kb;
