using System.Diagnostics;
using Microsoft.EntityFrameworkCore;
using Npgsql;
using Pgvector;
using Pgvector.EntityFrameworkCore;

namespace PgVectorEfMigrations;

public static class Program
{
    public static readonly string ConnectionString =
        Environment.GetEnvironmentVariable("PG_CONN")
        ?? "Host=localhost;Port=54340;Username=postgres;Password=demo;Database=demo;Command Timeout=120;Timeout=30";

    private const int Dim = 64;
    private const int NumClusters = 50;
    private const int RowsPerCluster = 400; // 50 * 400 = 20 000
    private const int NumQueries = 50;

    public static async Task Main()
    {
        Console.WriteLine("=== 0. Polaczenie ===");
        Console.WriteLine($"PG_CONN = {ConnectionString}");

        // Zwykly NpgsqlConnection(connStr) NIE zna typu 'vector' (Npgsql musi go zarejestrowac
        // przez NpgsqlDataSourceBuilder.UseVector() - identycznie jak w wydaniu #4). Extension
        // 'vector' juz istnieje (utworzony przez migracje EF), wiec budowa data source jest bezpieczna.
        var dsb = new NpgsqlDataSourceBuilder(ConnectionString);
        dsb.UseVector();
        await using var dataSource = dsb.Build();

        // Ten program NIE tworzy schematu - to robi `dotnet ef database update`.
        // Tu tylko ladujemy dane (binary COPY, jak w wydaniu #4) i odpytujemy przez EF Core.
        await using (var db0 = new AppDbContext(ConnectionString))
        {
            var pending = await db0.Database.GetPendingMigrationsAsync();
            var pendingList = pending.ToList();
            if (pendingList.Count > 0)
            {
                Console.WriteLine($"UWAGA: {pendingList.Count} niezaaplikowanych migracji: {string.Join(", ", pendingList)}");
                Console.WriteLine("Uruchom najpierw: dotnet dotnet-ef database update");
                return;
            }
            Console.WriteLine("Migracje zaaplikowane (brak pending) - OK.");
        }

        Console.WriteLine("\n=== 1. Czyszczenie tabeli items (TRUNCATE) ===");
        await using (var conn = dataSource.CreateConnection())
        {
            await conn.OpenAsync();
            await using var truncCmd = new NpgsqlCommand("TRUNCATE TABLE items", conn);
            await truncCmd.ExecuteNonQueryAsync();
        }

        Console.WriteLine("\n=== 2. Generowanie danych (deterministyczne, Random(42)) ===");
        var rnd = new Random(42);
        var data = GenerateClusteredVectors(rnd, NumClusters, RowsPerCluster, Dim);
        Console.WriteLine($"Wygenerowano {data.Count} wektorow, {NumClusters} klastrow, dim={Dim}");

        Console.WriteLine("\n=== 3. Ladowanie: binary COPY (kolumna vector z Pgvector.Vector) ===");
        var sw = Stopwatch.StartNew();
        await using (var conn = dataSource.CreateConnection())
        {
            await conn.OpenAsync();
            await using var import = await conn.BeginBinaryImportAsync(
                "COPY items (\"Id\", \"Category\", \"Embedding\") FROM STDIN (FORMAT BINARY)");
            for (int i = 0; i < data.Count; i++)
            {
                await import.StartRowAsync();
                await import.WriteAsync(i + 1);
                await import.WriteAsync(data[i].Category);
                await import.WriteAsync(new Vector(data[i].V));
            }
            await import.CompleteAsync();
        }
        sw.Stop();
        Console.WriteLine($"Zaladowano {data.Count} wierszy w {sw.ElapsedMilliseconds} ms");

        Console.WriteLine("\n=== 4. Indeks z migracji - co widzi pg_indexes ===");
        await using (var conn = dataSource.CreateConnection())
        {
            await conn.OpenAsync();
            await using var cmd = new NpgsqlCommand(
                "SELECT indexdef FROM pg_indexes WHERE tablename = 'items' ORDER BY indexname", conn);
            await using var reader = await cmd.ExecuteReaderAsync();
            while (await reader.ReadAsync())
            {
                Console.WriteLine($"  {reader.GetString(0)}");
            }
        }

        Console.WriteLine("\n=== 5. kNN przez EF Core (CosineDistance) - 'prawda' bez indeksu vs z indeksem ===");
        // Zapytanie referencyjne (query embedding = pierwszy wektor klastra 7)
        var queryVec = data.First(d => d.Category == "cluster-07").V;
        var qParam = new Vector(queryVec);

        await using (var db = new AppDbContext(ConnectionString))
        {
            var top = await db.Items
                .OrderBy(x => x.Embedding!.CosineDistance(qParam))
                .Take(5)
                .Select(x => new { x.Id, x.Category, Dist = x.Embedding!.CosineDistance(qParam) })
                .ToListAsync();

            Console.WriteLine("Top 5 (LINQ, CosineDistance, indeks HNSW z migracji):");
            foreach (var r in top)
                Console.WriteLine($"  id={r.Id,6}  cosine_dist={r.Dist:F4}  ({r.Category})");

            Console.WriteLine("\nSQL wygenerowany przez EF Core (ToQueryString):");
            var query = db.Items
                .OrderBy(x => x.Embedding!.CosineDistance(qParam))
                .Take(5)
                .Select(x => new { x.Id, x.Category, Dist = x.Embedding!.CosineDistance(qParam) });
            foreach (var line in query.ToQueryString().Split('\n'))
                Console.WriteLine($"  {line}");
        }

        Console.WriteLine("\n=== 6. EXPLAIN - czy planner faktycznie uzywa indeksu z migracji? ===");
        await using (var conn = dataSource.CreateConnection())
        {
            await conn.OpenAsync();
            await using var cmd = new NpgsqlCommand(
                "EXPLAIN SELECT \"Id\" FROM items ORDER BY \"Embedding\" <=> $1 LIMIT 5", conn);
            cmd.Parameters.AddWithValue(qParam);
            await using var reader = await cmd.ExecuteReaderAsync();
            while (await reader.ReadAsync())
                Console.WriteLine($"  {reader.GetString(0)}");
        }

        Console.WriteLine("\n=== 7. Recall@10 z indeksem z migracji (HNSW ef_search domyslne) ===");
        await using (var conn = dataSource.CreateConnection())
        {
            await conn.OpenAsync();
            var queries = Enumerable.Range(0, NumQueries)
                .Select(_ => data[rnd.Next(data.Count)].V)
                .ToList();

            // "Prawda": dokladny top-10 liczony w C#, bez indeksu.
            var truth = queries.Select(q => ExactTopK(data, q, 10)).ToList();

            int hitCount = 0;
            var qsw = Stopwatch.StartNew();
            for (int i = 0; i < queries.Count; i++)
            {
                await using var cmd = new NpgsqlCommand(
                    "SELECT \"Id\" FROM items ORDER BY \"Embedding\" <=> $1 LIMIT 10", conn);
                cmd.Parameters.AddWithValue(new Vector(queries[i]));
                await using var reader = await cmd.ExecuteReaderAsync();
                var got = new List<int>();
                while (await reader.ReadAsync()) got.Add(reader.GetInt32(0));
                hitCount += got.Count(id => truth[i].Contains(id));
            }
            qsw.Stop();
            double recall = hitCount / (double)(queries.Count * 10);
            Console.WriteLine($"recall@10 = {recall:F3}  ({qsw.ElapsedMilliseconds} ms / {queries.Count} zapytan = {qsw.ElapsedMilliseconds / (double)queries.Count:F2} ms/zapytanie)");
        }

        Console.WriteLine("\n=== Koniec ===");
    }

    private static HashSet<int> ExactTopK(List<(int Id, string Category, float[] V)> data, float[] q, int k)
    {
        return data
            .Select(d => (Id: d.Id + 1, Dist: CosineDistance(d.V, q))) // +1: baza ma Id 1..N (COPY pisze i+1), lista C# jest 0-based
            .OrderBy(x => x.Dist)
            .Take(k)
            .Select(x => x.Id)
            .ToHashSet();
    }

    private static float CosineDistance(float[] a, float[] b)
    {
        double dot = 0, na = 0, nb = 0;
        for (int i = 0; i < a.Length; i++)
        {
            dot += a[i] * b[i];
            na += a[i] * a[i];
            nb += b[i] * b[i];
        }
        return (float)(1.0 - dot / (Math.Sqrt(na) * Math.Sqrt(nb)));
    }

    private static List<(int Id, string Category, float[] V)> GenerateClusteredVectors(
        Random rnd, int numClusters, int rowsPerCluster, int dim)
    {
        var centers = new float[numClusters][];
        for (int c = 0; c < numClusters; c++)
        {
            centers[c] = new float[dim];
            for (int d = 0; d < dim; d++)
                centers[c][d] = (float)(rnd.NextDouble() * 2 - 1);
        }

        var result = new List<(int, string, float[])>();
        int id = 0;
        for (int c = 0; c < numClusters; c++)
        {
            var category = $"cluster-{c:D2}";
            for (int r = 0; r < rowsPerCluster; r++)
            {
                var v = new float[dim];
                for (int d = 0; d < dim; d++)
                    v[d] = centers[c][d] + (float)((rnd.NextDouble() - 0.5) * 0.3);
                result.Add((id, category, v));
                id++;
            }
        }
        return result;
    }
}
