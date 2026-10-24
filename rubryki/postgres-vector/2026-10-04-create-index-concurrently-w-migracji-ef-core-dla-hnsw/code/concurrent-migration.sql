START TRANSACTION;
DROP INDEX ix_items_embedding_hnsw;

COMMIT;

CREATE INDEX CONCURRENTLY ix_items_embedding_hnsw ON items USING hnsw ("Embedding" vector_cosine_ops) WITH (ef_construction=200, m=32);

INSERT INTO "__EFMigrationsHistory" ("MigrationId", "ProductVersion")
VALUES ('20261004213433_BumpParamsConcurrently', '9.0.0');

