using System.Diagnostics;
using Microsoft.EntityFrameworkCore;
using Npgsql;
using Pgvector;
using Pgvector.EntityFrameworkCore;
using Pgvector.Npgsql;

// Connection string: domyslnie kontener z run-demo (port 54329), mozna nadpisac zmienna PG_CONN.
var connStr = Environment.GetEnvironmentVariable("PG_CONN")
    ?? "Host=localhost;Port=54329;Username=postgres;Password=demo;Database=demo";

const int Dim = 64;
const int Rows = 20_000;
const int Queries = 50;
const int K = 10;

Console.WriteLine("=== 0. Dane syntetyczne (deterministyczne, Random(42)) ===");
var rnd = new Random(42);
var centroids = Enumerable.Range(0, 50).Select(_ => RandomVec(rnd, Dim, 1.0f)).ToArray();
var data = new (int Category, float[] V)[Rows];
for (var i = 0; i < Rows; i++)
{
    var c = i % centroids.Length;
    var v = new float[Dim];
    for (var d = 0; d < Dim; d++) v[d] = centroids[c][d] + (float)(rnd.NextDouble() * 2 - 1) * 0.6f;
    data[i] = (c, v);
}
var qrnd = new Random(7);
var queries = Enumerable.Range(0, Queries).Select(_ =>
{
    var src = data[qrnd.Next(Rows)].V;
    return src.Select(x => x + (float)(qrnd.NextDouble() * 2 - 1) * 0.3f).ToArray();
}).ToArray();
Console.WriteLine($"{Rows} wektorow x {Dim}D, {centroids.Length} klastrow, {Queries} zapytan");

// --- Pulapka #1: DDL (CREATE EXTENSION) na zwyklym data source, DOPIERO POTEM data source z UseVector().
// Npgsql ladowal typy przy pierwszym polaczeniu; typ 'vector' musi juz istniec w bazie.
await using (var plain = NpgsqlDataSource.Create(connStr))
{
    await using var cmd = plain.CreateCommand("""
        CREATE EXTENSION IF NOT EXISTS vector;
        DROP TABLE IF EXISTS docs;
        CREATE TABLE docs (id int PRIMARY KEY, category int NOT NULL, emb vector(64) NOT NULL);
        """);
    await cmd.ExecuteNonQueryAsync();
}

var dsb = new NpgsqlDataSourceBuilder(connStr);
dsb.UseVector();                       // <- rejestruje mapowanie Pgvector.Vector <-> vector
await using var ds = dsb.Build();

Console.WriteLine();
Console.WriteLine("=== 1. Wersje ===");
await using (var cmd = ds.CreateCommand("SELECT version(), (SELECT extversion FROM pg_extension WHERE extname='vector')"))
await using (var r = await cmd.ExecuteReaderAsync())
{
    await r.ReadAsync();
    Console.WriteLine($"PostgreSQL: {r.GetString(0).Split(',')[0]} | pgvector: {r.GetString(1)}");
}

Console.WriteLine();
Console.WriteLine("=== 2. Ladowanie: binary COPY z typem Vector ===");
var sw = Stopwatch.StartNew();
await using (var writer = await ds.OpenConnectionAsync())
await using (var import = await writer.BeginBinaryImportAsync("COPY docs (id, category, emb) FROM STDIN (FORMAT BINARY)"))
{
    for (var i = 0; i < Rows; i++)
    {
        await import.StartRowAsync();
        await import.WriteAsync(i);
        await import.WriteAsync(data[i].Category);
        await import.WriteAsync(new Vector(data[i].V));
    }
    await import.CompleteAsync();
}
Console.WriteLine($"Zaladowano {Rows} wierszy w {sw.ElapsedMilliseconds} ms");

Console.WriteLine();
Console.WriteLine("=== 3. kNN z parametrem wektorowym (bez indeksu = dokladny Seq Scan) ===");
const string knnSql = "SELECT id, emb <=> $1 AS dist FROM docs ORDER BY emb <=> $1 LIMIT $2";

async Task<List<(int Id, double Dist)>> Knn(NpgsqlConnection conn, float[] q, int k)
{
    await using var cmd = new NpgsqlCommand(knnSql, conn);
    cmd.Parameters.AddWithValue(new Vector(q));   // typ Vector -> Npgsql wie, ze to 'vector'
    cmd.Parameters.AddWithValue(k);
    var res = new List<(int, double)>();
    await using var r = await cmd.ExecuteReaderAsync();
    while (await r.ReadAsync()) res.Add((r.GetInt32(0), r.GetDouble(1)));
    return res;
}

await using var conn = await ds.OpenConnectionAsync();
var top5 = await Knn(conn, queries[0], 5);
foreach (var (id, dist) in top5) Console.WriteLine($"  id={id,6}  cosine_dist={dist:F4}  (klaster {data[id].Category})");

// prawda do recall: dokladne top-K dla wszystkich zapytan
var truth = new List<HashSet<int>>();
sw.Restart();
foreach (var q in queries) truth.Add((await Knn(conn, q, K)).Select(x => x.Id).ToHashSet());
Console.WriteLine($"Dokladnie (Seq Scan): {sw.Elapsed.TotalMilliseconds / Queries:F2} ms/zapytanie");

Console.WriteLine();
Console.WriteLine("=== 4. Indeks HNSW + recall@10 w zaleznosci od hnsw.ef_search ===");
sw.Restart();
await using (var cmd = new NpgsqlCommand(
    "CREATE INDEX docs_hnsw ON docs USING hnsw (emb vector_cosine_ops) WITH (m = 16, ef_construction = 64)", conn))
    await cmd.ExecuteNonQueryAsync();
Console.WriteLine($"CREATE INDEX HNSW: {sw.Elapsed.TotalSeconds:F1} s");

foreach (var ef in new[] { 10, 40, 200 })
{
    // SET LOCAL zyje tylko w transakcji => bezpieczne przy puli polaczen
    await using var tx = await conn.BeginTransactionAsync();
    await using (var set = new NpgsqlCommand($"SET LOCAL hnsw.ef_search = {ef}", conn, tx))
        await set.ExecuteNonQueryAsync();
    double recall = 0;
    sw.Restart();
    for (var i = 0; i < Queries; i++)
    {
        var got = (await Knn(conn, queries[i], K)).Select(x => x.Id).ToHashSet();
        recall += got.Intersect(truth[i]).Count() / (double)K;
    }
    var ms = sw.Elapsed.TotalMilliseconds / Queries;
    await tx.CommitAsync();
    Console.WriteLine($"  ef_search={ef,3}: recall@{K}={recall / Queries:F3}  {ms:F2} ms/zapytanie");
}

Console.WriteLine();
Console.WriteLine("=== 5. Plan zapytania z parametrem (czy indeks jest uzywany?) ===");
await using (var cmd = new NpgsqlCommand("EXPLAIN SELECT id FROM docs ORDER BY emb <=> $1 LIMIT 10", conn))
{
    cmd.Parameters.AddWithValue(new Vector(queries[0]));
    await using var r = await cmd.ExecuteReaderAsync();
    while (await r.ReadAsync())   // literal wektora skracamy dla czytelnosci outputu
        Console.WriteLine("  " + System.Text.RegularExpressions.Regex.Replace(r.GetString(0), @"\[[^\]]+\]", "[...64 floaty...]"));
}

Console.WriteLine();
Console.WriteLine("=== 6. Pulapki: float[] zamiast Vector, zla wymiarowosc ===");
try
{
    await using var cmd = new NpgsqlCommand("SELECT id FROM docs ORDER BY emb <=> $1 LIMIT 1", conn);
    cmd.Parameters.AddWithValue(queries[0]);      // zwykle float[] => real[]
    await cmd.ExecuteScalarAsync();
}
catch (PostgresException e) { Console.WriteLine($"  float[]: {e.SqlState} {e.MessageText}"); }
try
{
    await using var cmd = new NpgsqlCommand("SELECT id FROM docs ORDER BY emb <=> $1 LIMIT 1", conn);
    cmd.Parameters.AddWithValue(new Vector(new float[] { 1, 2, 3 }));
    await cmd.ExecuteScalarAsync();
}
catch (PostgresException e) { Console.WriteLine($"  3D vs vector(64): {e.SqlState} {e.MessageText}"); }

Console.WriteLine();
Console.WriteLine("=== 7. EF Core: HasColumnType + HNSW w modelu + CosineDistance ===");
await using (var db = new DemoDb(connStr))
{
    await db.Database.EnsureDeletedAsync();
    await db.Database.EnsureCreatedAsync();   // w produkcji: migracje (dotnet ef migrations add)
    db.Items.AddRange(data.Take(2000).Select((d, i) => new Item { Id = i, Category = d.Category, Embedding = new Vector(d.V) }));
    await db.SaveChangesAsync();

    var q = new Vector(queries[0]);
    var query = db.Items.OrderBy(x => x.Embedding!.CosineDistance(q)).Take(5)
        .Select(x => new { x.Id, x.Category, Dist = x.Embedding!.CosineDistance(q) });
    Console.WriteLine("SQL wygenerowany przez EF Core:");
    Console.WriteLine(System.Text.RegularExpressions.Regex.Replace(query.ToQueryString(), @"\[[^\]]+\]", "[...64 floaty...]"));
    Console.WriteLine("Wynik (top 5 z pierwszych 2000 wierszy):");
    foreach (var x in await query.ToListAsync())
        Console.WriteLine($"  id={x.Id,5}  cosine_dist={x.Dist:F4}  (klaster {x.Category})");

    Console.WriteLine("Indeks z modelu (pg_indexes):");
    await using var c2 = await ds.OpenConnectionAsync();
    await using var cmd = c2.CreateCommand();
    cmd.CommandText = "SELECT indexdef FROM pg_indexes WHERE tablename = 'items' AND indexname = 'ix_items_embedding'";
    Console.WriteLine("  " + await cmd.ExecuteScalarAsync());
}

Console.WriteLine();
Console.WriteLine("Koniec.");

static float[] RandomVec(Random r, int dim, float scale)
{
    var v = new float[dim];
    for (var i = 0; i < dim; i++) v[i] = (float)(r.NextDouble() * 2 - 1) * scale;
    return v;
}

public class Item
{
    public int Id { get; set; }
    public int Category { get; set; }
    public Vector? Embedding { get; set; }
}

public class DemoDb(string connStr) : DbContext
{
    public DbSet<Item> Items => Set<Item>();

    protected override void OnConfiguring(DbContextOptionsBuilder o)
        => o.UseNpgsql(connStr, npgsql => npgsql.UseVector());

    protected override void OnModelCreating(ModelBuilder mb)
    {
        mb.HasPostgresExtension("vector");
        mb.Entity<Item>(e =>
        {
            e.ToTable("items");
            e.Property(x => x.Id).ValueGeneratedNever();   // klucze nadajemy sami (id z danych)
            e.Property(x => x.Embedding).HasColumnType("vector(64)");
            e.HasIndex(x => x.Embedding, "ix_items_embedding")
                .HasMethod("hnsw")
                .HasOperators("vector_cosine_ops")
                .HasStorageParameter("m", 16)
                .HasStorageParameter("ef_construction", 64);
        });
    }
}
