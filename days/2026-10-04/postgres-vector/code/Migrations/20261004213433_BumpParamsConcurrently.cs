using Microsoft.EntityFrameworkCore.Migrations;

#nullable disable

namespace PgVectorConcurrently.Migrations
{
    /// <inheritdoc />
    public partial class BumpParamsConcurrently : Migration
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
                .Annotation("Npgsql:CreatedConcurrently", true)
                .Annotation("Npgsql:IndexMethod", "hnsw")
                .Annotation("Npgsql:IndexOperators", new[] { "vector_cosine_ops" })
                .Annotation("Npgsql:StorageParameter:ef_construction", 200)
                .Annotation("Npgsql:StorageParameter:m", 32);
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
                .Annotation("Npgsql:StorageParameter:ef_construction", 128)
                .Annotation("Npgsql:StorageParameter:m", 24);
        }
    }
}
