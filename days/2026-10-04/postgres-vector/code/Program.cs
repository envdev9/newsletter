using System.Diagnostics;
using Microsoft.EntityFrameworkCore;
using Npgsql;
using Pgvector;
using Pgvector.EntityFrameworkCore;

namespace PgVectorConcurrently;

public static class Program
{
    public static readonly string ConnectionString =
        Environment.GetEnvironmentVariable("PG_CONN")
        ?? "Host=localhost;Port=54341;Username=postgres;Password=demo;Database=demo;Command Timeout=120;Timeout=30";

    private const int Dim = 64;
    private const int NumClusters = 50;
    private const int RowsPerCluster = 400; // 50 * 400 = 20 000

    public static async Task Main(string[] args)
    {
        Console.WriteLine("=== 0. Polaczenie ===");
        Console.WriteLine($"PG_CONN = {ConnectionString}");

        var dsb = new NpgsqlDataSourceBuilder(ConnectionString);
        dsb.UseVector();
        await using var dataSource = dsb.Build();

        await using (var db0 = new AppDbContext(ConnectionString))
        {
            var pending = await db0.Database.GetPendingMigrationsAsync();
            var pendingList = pending.ToList();
            if (pendingList.Count > 0)
            {
                Console.WriteLine($"UWAGA: {pendingList.Count} niezaaplikowanych migracji: {string.Join(", ", pendingList)}");
                Console.WriteLine("Uruchom najpierw: dotnet tool run dotnet-ef database update <nazwa-migracji>");
                return;
            }
            Console.WriteLine("Migracje zaaplikowane (brak pending) - OK.");
        }

        // Jeden argument: "load" -> wczytaj 20k wierszy (binary COPY) do pustej/wyczyszczonej tabeli.
        // Bez argumentu -> tylko podglad stanu indeksu + mala kontrola kNN (zakladamy, ze dane juz sa).
        bool doLoad = args.Length > 0 && args[0] == "load";

        if (doLoad)
        {
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
        }

        Console.WriteLine("\n=== 4. Stan indeksow (pg_indexes) i walidacja (pg_index.indisvalid) ===");
        await using (var conn = dataSource.CreateConnection())
        {
            await conn.OpenAsync();
            await using var cmd = new NpgsqlCommand(
                @"SELECT i.indexname, i.indexdef, x.indisvalid
                  FROM pg_indexes i
                  JOIN pg_class c ON c.relname = i.indexname
                  JOIN pg_index x ON x.indexrelid = c.oid
                  WHERE i.tablename = 'items'
                  ORDER BY i.indexname", conn);
            await using var reader = await cmd.ExecuteReaderAsync();
            while (await reader.ReadAsync())
            {
                Console.WriteLine($"  valid={reader.GetBoolean(2)}  {reader.GetString(0)}: {reader.GetString(1)}");
            }
        }

        Console.WriteLine("\n=== 5. Szybka kontrola: kNN przez EF Core (CosineDistance) dziala na biezacym indeksie ===");
        await using (var connCheck = dataSource.CreateConnection())
        {
            await connCheck.OpenAsync();
            await using var cntCmd = new NpgsqlCommand("SELECT count(*) FROM items", connCheck);
            var count = (long)(await cntCmd.ExecuteScalarAsync())!;
            if (count == 0)
            {
                Console.WriteLine("  (tabela items jest pusta - uruchom `dotnet run load` najpierw)");
            }
            else
            {
                await using var db = new AppDbContext(ConnectionString);
                var first = await db.Items.OrderBy(x => x.Id).FirstAsync();
                var qParam = first.Embedding!;
                var top = await db.Items
                    .OrderBy(x => x.Embedding!.CosineDistance(qParam))
                    .Take(3)
                    .Select(x => new { x.Id, x.Category, Dist = x.Embedding!.CosineDistance(qParam) })
                    .ToListAsync();
                foreach (var r in top)
                    Console.WriteLine($"  id={r.Id,6}  cosine_dist={r.Dist:F4}  ({r.Category})");
            }
        }

        Console.WriteLine("\n=== Koniec ===");
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
