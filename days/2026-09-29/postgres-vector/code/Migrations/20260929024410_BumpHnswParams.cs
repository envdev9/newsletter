using Microsoft.EntityFrameworkCore.Migrations;

#nullable disable

namespace PgVectorEfMigrations.Migrations
{
    /// <inheritdoc />
    public partial class BumpHnswParams : Migration
    {
        /// <inheritdoc />
        protected override void Up(MigrationBuilder migrationBuilder)
        {
            migrationBuilder.DropIndex(
                name: "ix_items_embedding_hnsw",
                table: "items");

            migrationBuilder.CreateIndex(
                name: "ix_items_embedding_hnsw",
                table: "items",
                column: "Embedding")
                .Annotation("Npgsql:IndexMethod", "hnsw")
                .Annotation("Npgsql:IndexOperators", new[] { "vector_cosine_ops" })
                .Annotation("Npgsql:StorageParameter:ef_construction", 128)
                .Annotation("Npgsql:StorageParameter:m", 24);
        }

        /// <inheritdoc />
        protected override void Down(MigrationBuilder migrationBuilder)
        {
            migrationBuilder.DropIndex(
                name: "ix_items_embedding_hnsw",
                table: "items");

            migrationBuilder.CreateIndex(
                name: "ix_items_embedding_hnsw",
                table: "items",
                column: "Embedding")
                .Annotation("Npgsql:IndexMethod", "hnsw")
                .Annotation("Npgsql:IndexOperators", new[] { "vector_cosine_ops" })
                .Annotation("Npgsql:StorageParameter:ef_construction", 64)
                .Annotation("Npgsql:StorageParameter:m", 16);
        }
    }
}
