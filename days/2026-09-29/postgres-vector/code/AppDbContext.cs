using Microsoft.EntityFrameworkCore;
using Microsoft.EntityFrameworkCore.Design;
using Pgvector;

namespace PgVectorEfMigrations;

public class Item
{
    public int Id { get; set; }
    public string Category { get; set; } = "";
    public Vector? Embedding { get; set; }
}

public class AppDbContext : DbContext
{
    private readonly string _connectionString;

    public AppDbContext(string connectionString)
    {
        _connectionString = connectionString;
    }

    public DbSet<Item> Items => Set<Item>();

    protected override void OnConfiguring(DbContextOptionsBuilder optionsBuilder)
    {
        if (!optionsBuilder.IsConfigured)
        {
            optionsBuilder.UseNpgsql(_connectionString, npgsql => npgsql.UseVector());
        }
    }

    protected override void OnModelCreating(ModelBuilder modelBuilder)
    {
        modelBuilder.HasPostgresExtension("vector");

        modelBuilder.Entity<Item>(e =>
        {
            e.ToTable("items");
            e.HasKey(x => x.Id);
            e.Property(x => x.Id).ValueGeneratedNever();
            e.Property(x => x.Category).HasMaxLength(64);
            e.Property(x => x.Embedding).HasColumnType("vector(64)");

            e.HasIndex(x => x.Embedding, "ix_items_embedding_hnsw")
                .HasMethod("hnsw")
                .HasOperators("vector_cosine_ops")
                .HasStorageParameter("m", 24)
                .HasStorageParameter("ef_construction", 128);
        });
    }
}

/// <summary>
/// Fabryka design-time, której szuka `dotnet ef` przy `migrations add` / `database update`.
/// Bez niej EF próbowałby uruchomić Program.Main (host builder), a to demo go nie ma - fabryka
/// daje kontekst "na sucho", tylko do budowy migracji / SQL-a, bez ładowania danych.
/// Connection string bierze z PG_CONN, tak samo jak Program.cs.
/// </summary>
public class AppDbContextFactory : IDesignTimeDbContextFactory<AppDbContext>
{
    public AppDbContext CreateDbContext(string[] args)
    {
        var connStr = Environment.GetEnvironmentVariable("PG_CONN")
            ?? "Host=localhost;Port=54340;Username=postgres;Password=demo;Database=demo";
        return new AppDbContext(connStr);
    }
}
