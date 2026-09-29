CREATE TABLE IF NOT EXISTS "__EFMigrationsHistory" (
    "MigrationId" character varying(150) NOT NULL,
    "ProductVersion" character varying(32) NOT NULL,
    CONSTRAINT "PK___EFMigrationsHistory" PRIMARY KEY ("MigrationId")
);

START TRANSACTION;
CREATE EXTENSION IF NOT EXISTS vector;

CREATE TABLE items (
    "Id" integer NOT NULL,
    "Category" character varying(64) NOT NULL,
    "Embedding" vector(64),
    CONSTRAINT "PK_items" PRIMARY KEY ("Id")
);

CREATE INDEX ix_items_embedding_hnsw ON items USING hnsw ("Embedding" vector_cosine_ops) WITH (ef_construction=64, m=16);

INSERT INTO "__EFMigrationsHistory" ("MigrationId", "ProductVersion")
VALUES ('20260929024044_InitialCreate', '9.0.0');

COMMIT;

