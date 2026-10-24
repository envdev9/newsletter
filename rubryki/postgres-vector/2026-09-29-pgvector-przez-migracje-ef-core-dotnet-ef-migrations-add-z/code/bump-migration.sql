START TRANSACTION;
DROP INDEX ix_items_embedding_hnsw;

CREATE INDEX ix_items_embedding_hnsw ON items USING hnsw ("Embedding" vector_cosine_ops) WITH (ef_construction=128, m=24);

INSERT INTO "__EFMigrationsHistory" ("MigrationId", "ProductVersion")
VALUES ('20260929024410_BumpHnswParams', '9.0.0');

COMMIT;

