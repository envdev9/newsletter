using Microsoft.EntityFrameworkCore;
using Microsoft.EntityFrameworkCore.Design;
using Pgvector;

namespace PgVectorConcurrently;

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

    // STAN KONCOWY modelu (po wszystkich migracjach): m=32, ef_construction=200,
    // IsCreatedConcurrently(true). Historia zmian parametrow (16/64 -> 24/128 -> 32/200)
    // i przejscie z plain CREATE INDEX na CREATE INDEX CONCURRENTLY zyje w Migrations/.
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
                .HasStorageParameter("m", 32)
                .HasStorageParameter("ef_construction", 200)
                .IsCreatedConcurrently(true);
        });
    }
}

/// <summary>
/// Fabryka design-time, ktorej szuka `dotnet ef` przy `migrations add` / `database update`.
/// Connection string bierze z PG_CONN, tak samo jak Program.cs.
/// </summary>
public class AppDbContextFactory : IDesignTimeDbContextFactory<AppDbContext>
{
    public AppDbContext CreateDbContext(string[] args)
    {
        var connStr = Environment.GetEnvironmentVariable("PG_CONN")
            ?? "Host=localhost;Port=54341;Username=postgres;Password=demo;Database=demo";
        return new AppDbContext(connStr);
    }
}
