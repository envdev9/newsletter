using System.Diagnostics;
using Npgsql;
using NpgsqlTypes;
using Pgvector;
using Pgvector.Npgsql;

// Uzycie: dotnet run -- <load|halfvec|pool>
//   load    - schemat + 20 000 wierszy (vector(64) + halfvec(64) + tenant) + dwa indeksy HNSW
//   halfvec - rozmiary, recall@10, plan: vector vs halfvec
//   pool    - iterative_scan a pula polaczen: wyciek SET, Options w connection stringu, SET LOCAL, wspolbieznosc
const int Dim = 64, Rows = 20_000, Tenants = 200;

var baseCs = Environment.GetEnvironmentVariable("PG_CONN")
    ?? "Host=localhost;Port=54351;Username=postgres;Password=demo;Database=demo;Command Timeout=300";

switch (args.FirstOrDefault())
{
    case "load": await Load(); break;
    case "halfvec": await HalfVecDemo(); break;
    case "pool": await PoolDemo(); break;
    default: Console.WriteLine("dotnet run -- <load|halfvec|pool>"); break;
}

NpgsqlDataSource Build(string cs)
{
    var b = new NpgsqlDataSourceBuilder(cs);
    b.UseVector();
    return b.Build();
}

// ---------- dane syntetyczne, deterministyczne (Random(42)) ----------
static float[][] MakeData(int n, int seed)
{
    var rnd = new Random(seed);
    var centers = new float[50][];
    for (int c = 0; c < centers.Length; c++)
        centers[c] = Enumerable.Range(0, Dim).Select(_ => (float)(rnd.NextDouble() * 2 - 1)).ToArray();
    var res = new float[n][];
    for (int i = 0; i < n; i++)
    {
        var ctr = centers[rnd.Next(centers.Length)];
        res[i] = ctr.Select(x => x + (float)(rnd.NextDouble() - 0.5) * 0.4f).ToArray();
    }
    return res;
}

async Task Load()
{
    await using var ds = Build(baseCs);
    await using var conn = await ds.OpenConnectionAsync();
    await Exec(conn, "CREATE EXTENSION IF NOT EXISTS vector");
    // Npgsql zaladowal katalog typow przy otwarciu polaczenia - PRZED CREATE EXTENSION. Bez tego: "Cannot resolve 'vector'".
    await conn.ReloadTypesAsync();
    await Exec(conn, "DROP TABLE IF EXISTS items");
    await Exec(conn, $"CREATE TABLE items (id int PRIMARY KEY, tenant int NOT NULL, tier int NOT NULL, embedding vector({Dim}) NOT NULL, embedding_h halfvec({Dim}) NOT NULL)");

    var data = MakeData(Rows, 42);
    var sw = Stopwatch.StartNew();
    await using (var w = await conn.BeginBinaryImportAsync(
        "COPY items (id, tenant, tier, embedding, embedding_h) FROM STDIN (FORMAT BINARY)"))
    {
        for (int i = 0; i < data.Length; i++)
        {
            await w.StartRowAsync();
            await w.WriteAsync(i + 1, NpgsqlDbType.Integer);
            await w.WriteAsync(i % Tenants, NpgsqlDbType.Integer);     // ~100 wierszy na tenanta (z indeksem B-tree)
            await w.WriteAsync((i / 7) % 20, NpgsqlDbType.Integer);    // 20 "tierow" po ~1000 wierszy (BEZ indeksu)
            await w.WriteAsync(new Vector(data[i]));
            // float[] -> Half[] -> HalfVector: konwersja po stronie klienta, 2 bajty na wymiar na drucie
            await w.WriteAsync(new HalfVector(data[i].Select(x => (Half)x).ToArray()));
        }
        await w.CompleteAsync();
    }
    Console.WriteLine($"COPY {Rows} wierszy (vector + halfvec) w {sw.ElapsedMilliseconds} ms");

    sw.Restart();
    await Exec(conn, "CREATE INDEX ix_items_vec ON items USING hnsw (embedding vector_cosine_ops) WITH (m=16, ef_construction=64)");
    Console.WriteLine($"HNSW na vector  : {sw.ElapsedMilliseconds} ms");
    sw.Restart();
    await Exec(conn, "CREATE INDEX ix_items_half ON items USING hnsw (embedding_h halfvec_cosine_ops) WITH (m=16, ef_construction=64)");
    Console.WriteLine($"HNSW na halfvec : {sw.ElapsedMilliseconds} ms");
    await Exec(conn, "CREATE INDEX ix_items_tenant ON items (tenant)");
    await Exec(conn, "ANALYZE items");
}

async Task HalfVecDemo()
{
    await using var ds = Build(baseCs);
    await using var conn = await ds.OpenConnectionAsync();

    Console.WriteLine("== Rozmiary ==");
    foreach (var (label, sql) in new[]
    {
        ("pg_column_size(vector(64))  ", "SELECT pg_column_size(embedding) FROM items WHERE id=1"),
        ("pg_column_size(halfvec(64)) ", "SELECT pg_column_size(embedding_h) FROM items WHERE id=1"),
        ("indeks HNSW vector  (bajty) ", "SELECT pg_relation_size('ix_items_vec')"),
        ("indeks HNSW halfvec (bajty) ", "SELECT pg_relation_size('ix_items_half')"),
        ("tabela (heap, bajty)        ", "SELECT pg_relation_size('items')"),
    })
        Console.WriteLine($"{label}: {await Scalar(conn, sql)}");

    // Round-trip: co dostajemy z powrotem z halfvec?
    await using (var cmd = new NpgsqlCommand("SELECT embedding, embedding_h FROM items WHERE id=1", conn))
    await using (var r = await cmd.ExecuteReaderAsync())
    {
        await r.ReadAsync();
        var v = r.GetFieldValue<Vector>(0).ToArray();
        var h = r.GetFieldValue<HalfVector>(1).ToArray();
        Console.WriteLine("\n== Round-trip id=1, pierwsze 3 wymiary ==");
        for (int i = 0; i < 3; i++)
            Console.WriteLine($"  float32={v[i]:R}  half={(float)h[i]:R}  blad={Math.Abs(v[i] - (float)h[i]):E2}");
    }

    // recall@10: ground truth = dokladny kNN na float32 (bez indeksu)
    var queries = MakeData(Rows, 42).Where((_, i) => i % 1000 == 7).Select(q => q.Select(x => x + 0.05f).ToArray()).ToArray();
    Console.WriteLine($"\n== recall@10 ({queries.Length} zapytan, ef_search=40) ==");
    double rv = 0, rh = 0, tv = 0, th = 0;
    foreach (var q in queries)
    {
        var truth = await Knn(conn, "SELECT id FROM items ORDER BY embedding <=> $1 LIMIT 10", new Vector(q), exact: true);
        var sw = Stopwatch.StartNew();
        var gv = await Knn(conn, "SELECT id FROM items ORDER BY embedding <=> $1 LIMIT 10", new Vector(q), exact: false);
        tv += sw.Elapsed.TotalMilliseconds;
        sw.Restart();
        var gh = await Knn(conn, "SELECT id FROM items ORDER BY embedding_h <=> $1 LIMIT 10", new HalfVector(q.Select(x => (Half)x).ToArray()), exact: false);
        th += sw.Elapsed.TotalMilliseconds;
        rv += truth.Intersect(gv).Count() / 10.0;
        rh += truth.Intersect(gh).Count() / 10.0;
    }
    Console.WriteLine($"  vector  : recall {rv / queries.Length:F3}, sr. {tv / queries.Length:F2} ms");
    Console.WriteLine($"  halfvec : recall {rh / queries.Length:F3}, sr. {th / queries.Length:F2} ms");

    Console.WriteLine("\n== EXPLAIN halfvec (kolumna halfvec) ==");
    await using (var cmd = new NpgsqlCommand(
        "EXPLAIN SELECT id FROM items ORDER BY embedding_h <=> $1 LIMIT 10", conn))
    {
        cmd.Parameters.AddWithValue(new HalfVector(queries[0].Select(x => (Half)x).ToArray()));
        await using var r = await cmd.ExecuteReaderAsync();
        while (await r.ReadAsync()) Console.WriteLine("  " + Short(r.GetString(0)));
    }

    // Wzorzec "wektor w float32, indeks na rzutowaniu": kolumna vector, indeks na (embedding::halfvec(64))
    Console.WriteLine("\n== Indeks na rzutowaniu (embedding::halfvec(64)) na kolumnie vector ==");
    await Exec(conn, $"CREATE INDEX ix_items_cast ON items USING hnsw ((embedding::halfvec({Dim})) halfvec_cosine_ops) WITH (m=16, ef_construction=64)");
    Console.WriteLine($"  rozmiar indeksu: {await Scalar(conn, "SELECT pg_relation_size('ix_items_cast')")} B");
    foreach (var expr in new[] { $"embedding::halfvec({Dim})", "embedding" })
    {
        await using var cmd = new NpgsqlCommand(
            $"EXPLAIN SELECT id FROM items ORDER BY {expr} <=> $1 LIMIT 10", conn);
        cmd.Parameters.AddWithValue(expr == "embedding" ? new Vector(queries[0]) : new HalfVector(queries[0].Select(x => (Half)x).ToArray()));
        await using var r = await cmd.ExecuteReaderAsync();
        Console.WriteLine($"  ORDER BY {expr} <=> ...");
        while (await r.ReadAsync()) Console.WriteLine("    " + Short(r.GetString(0)));
    }
    await Exec(conn, "DROP INDEX ix_items_cast");
}

async Task PoolDemo()
{
    var query = MakeData(Rows, 42)[123].Select(x => x + 0.05f).ToArray();
    const string filtered = "SELECT id FROM items WHERE tier = $1 ORDER BY embedding <=> $2 LIMIT 10";

    // ---- 1. Problem: filtr po indeksie ----
    Console.WriteLine("== 1a. Co planner robi z filtrem po tenant (~0,5% wierszy, jest B-tree)? ==");
    await using (var ds = Build(baseCs))
    await using (var conn = await ds.OpenConnectionAsync())
    {
        foreach (var col in new[] { "tenant", "tier" })
        {
            await using var cmd = new NpgsqlCommand($"EXPLAIN SELECT id FROM items WHERE {col} = 5 ORDER BY embedding <=> $1 LIMIT 10", conn);
            cmd.Parameters.AddWithValue(new Vector(query));
            await using var r = await cmd.ExecuteReaderAsync();
            Console.WriteLine($"  WHERE {col} = 5:");
            while (await r.ReadAsync()) { var l = r.GetString(0); if (!l.Contains("Order By")) Console.WriteLine("    " + Short(l)); }
        }

        Console.WriteLine("\n== 1b. Filtr tier (5% wierszy = ~1000 z 20 000), 20 zapytan, LIMIT 10 ==");
        var qs = MakeData(Rows, 42).Where((_, i) => i % 1000 == 7).ToArray();
        foreach (var mode in new[] { "off", "strict_order", "relaxed_order" })
        {
            double recall = 0; int rowsRet = 0; double ms = 0;
            foreach (var (q, n) in qs.Select((q, n) => (q, n)))
            {
                int tenant = (n * 13 + 5) % 20; // wartosc filtra (tier)
                var truth = await FilteredKnn(conn, filtered, tenant, q, mode: "off", exact: true);
                var sw = Stopwatch.StartNew();
                var got = await FilteredKnn(conn, filtered, tenant, q, mode, exact: false);
                ms += sw.Elapsed.TotalMilliseconds;
                rowsRet += got.Count;
                recall += truth.Count == 0 ? 1 : truth.Intersect(got).Count() / (double)truth.Count;
            }
            Console.WriteLine($"  iterative_scan={mode,-14} wierszy zwroconych: {rowsRet,3}/200  recall: {recall / qs.Length:F3}  sr. {ms / qs.Length:F2} ms");
        }
    }

    // ---- 2a. Pulapka: SHOW na swiezym backendzie ----
    Console.WriteLine("\n== 2a. SHOW hnsw.iterative_scan na SWIEZYM backendzie (biblioteka vector jeszcze nie zaladowana) ==");
    {
        await using var ds = Build(baseCs + ";Maximum Pool Size=1;Pooling=false");
        await using var c = await ds.OpenConnectionAsync();
        try { Console.WriteLine($"  SHOW: {await Scalar(c, "SHOW hnsw.iterative_scan")}"); }
        catch (PostgresException e) { Console.WriteLine($"  SHOW -> {e.SqlState}: {e.MessageText}"); }
        Console.WriteLine($"  current_setting(..., true) -> {(await Scalar(c, "SELECT current_setting('hnsw.iterative_scan', true)") is DBNull ? "NULL" : "wartosc")}");
        await Scalar(c, "SELECT '[1,2,3]'::vector(3)");
        Console.WriteLine($"  po pierwszym uzyciu typu vector: SHOW -> {await Scalar(c, "SHOW hnsw.iterative_scan")}");
    }

    // ---- 2. SET na polaczeniu z puli: czy wycieka? ----
    Console.WriteLine("\n== 2. Czy SET przezywa zwrot polaczenia do puli? ==");
    foreach (var noReset in new[] { false, true })
    {
        var cs = baseCs + $";Maximum Pool Size=1;No Reset On Close={noReset}";
        await using var ds = Build(cs);
        int pid1, pid2; string before, after;
        await using (var c = await ds.OpenConnectionAsync())
        {
            await Exec(c, "SET hnsw.iterative_scan = 'relaxed_order'");
            pid1 = Convert.ToInt32(await Scalar(c, "SELECT pg_backend_pid()"));
            before = (string)(await Scalar(c, "SHOW hnsw.iterative_scan"))!;
        }
        await using (var c = await ds.OpenConnectionAsync())
        {
            pid2 = Convert.ToInt32(await Scalar(c, "SELECT pg_backend_pid()"));
            after = (string)(await Scalar(c, "SHOW hnsw.iterative_scan"))!;
        }
        Console.WriteLine($"  No Reset On Close={noReset,-5}  backend pid {(pid1 == pid2 ? "TEN SAM" : "inny")}  SHOW przed zwrotem: {before}  po ponownym otwarciu: {after}");
    }

    // ---- 3. Options w connection stringu ----
    Console.WriteLine("\n== 3. Options=-c hnsw.iterative_scan=relaxed_order w connection stringu ==");
    {
        var cs = baseCs + ";Maximum Pool Size=1;Options=-c hnsw.iterative_scan=relaxed_order -c hnsw.max_scan_tuples=5000";
        await using var ds = Build(cs);
        await using (var c = await ds.OpenConnectionAsync())
        {
            Console.WriteLine($"  swieze polaczenie : iterative_scan={await Scalar(c, "SHOW hnsw.iterative_scan")}, max_scan_tuples={await Scalar(c, "SHOW hnsw.max_scan_tuples")}");
            await Exec(c, "SET hnsw.iterative_scan = 'off'");
            Console.WriteLine($"  po SET ... 'off'  : iterative_scan={await Scalar(c, "SHOW hnsw.iterative_scan")}");
        }
        await using (var c = await ds.OpenConnectionAsync())
            Console.WriteLine($"  po zwrocie do puli (reset): iterative_scan={await Scalar(c, "SHOW hnsw.iterative_scan")}");
    }

    // ---- 4. SET LOCAL / set_config(..., true) w transakcji ----
    Console.WriteLine("\n== 4. SET LOCAL w transakcji (No Reset On Close=true, czyli BEZ ratunku od Npgsql) ==");
    {
        var cs = baseCs + ";Maximum Pool Size=1;No Reset On Close=true";
        await using var ds = Build(cs);
        await using (var c = await ds.OpenConnectionAsync())
        {
            await using var tx = await c.BeginTransactionAsync();
            await Exec(c, "SELECT set_config('hnsw.iterative_scan', 'relaxed_order', true)");
            Console.WriteLine($"  w transakcji      : {await Scalar(c, "SHOW hnsw.iterative_scan")}");
            await tx.CommitAsync();
        }
        await using (var c = await ds.OpenConnectionAsync())
            Console.WriteLine($"  po COMMIT/zwrocie : {await Scalar(c, "SHOW hnsw.iterative_scan")}");
    }

    // ---- 5. Wspolbieznosc: pula 4, 16 zadan; parzyste ustawiaja relaxed_order, nieparzyste NIE ustawiaja nic ----
    foreach (var useLocal in new[] { false, true })
    {
        Console.WriteLine($"\n== 5{(useLocal ? "b" : "a")}. Pula 4 (No Reset On Close=true), 16 zadan x 50 zapytan, parzyste: {(useLocal ? "set_config(..., true) w transakcji" : "SET sesyjny")}, nieparzyste: nic nie ustawiaja ==");
        var cs = baseCs + ";Maximum Pool Size=4;No Reset On Close=true"; // najgorszy przypadek: brak resetu
        await using var ds = Build(cs);
        int oddSawRelaxed = 0, oddTotal = 0;
        await Task.WhenAll(Enumerable.Range(0, 16).Select(t => Task.Run(async () =>
        {
            for (int i = 0; i < 50; i++)
            {
                await using var c = await ds.OpenConnectionAsync();
                await using var tx = await c.BeginTransactionAsync();
                if (t % 2 == 0)
                    await Exec(c, useLocal
                        ? "SELECT set_config('hnsw.iterative_scan', 'relaxed_order', true)"
                        : "SET hnsw.iterative_scan = 'relaxed_order'");
                else
                {
                    // current_setting(..., true) - SHOW wywala 42704 na swiezym backendzie (patrz sekcja 2)
                    var seen = await Scalar(c, "SELECT current_setting('hnsw.iterative_scan', true)", tx) as string;
                    Interlocked.Increment(ref oddTotal);
                    if (seen == "relaxed_order") Interlocked.Increment(ref oddSawRelaxed);
                }
                await using var cmd = new NpgsqlCommand(filtered, c, tx);
                cmd.Parameters.AddWithValue((t * 7 + i) % 20);
                cmd.Parameters.AddWithValue(new Vector(query));
                await using var r = await cmd.ExecuteReaderAsync();
                while (await r.ReadAsync()) { }
                await r.CloseAsync();
                await tx.CommitAsync();
            }
        })));
        Console.WriteLine($"  zadania nieparzyste (nic nie ustawialy) zobaczyly relaxed_order w {oddSawRelaxed} z {oddTotal} zapytan");
    }
}

// ---------- pomocnicze ----------
static string Short(string s) => s.Length > 100 ? s[..100] + " ...]'" : s;

static async Task Exec(NpgsqlConnection c, string sql)
{
    await using var cmd = new NpgsqlCommand(sql, c);
    await cmd.ExecuteNonQueryAsync();
}

static async Task<object?> Scalar(NpgsqlConnection c, string sql, NpgsqlTransaction? tx = null)
{
    await using var cmd = new NpgsqlCommand(sql, c, tx);
    return await cmd.ExecuteScalarAsync();
}

static async Task<List<int>> Knn(NpgsqlConnection c, string sql, object vec, bool exact)
{
    await using var tx = await c.BeginTransactionAsync();
    await Exec(c, exact
        ? "SET LOCAL enable_indexscan = off"
        : "SET LOCAL hnsw.ef_search = 40");
    await using var cmd = new NpgsqlCommand(sql, c, tx);
    cmd.Parameters.AddWithValue(vec);
    var res = new List<int>();
    await using (var r = await cmd.ExecuteReaderAsync())
        while (await r.ReadAsync()) res.Add(r.GetInt32(0));
    await tx.CommitAsync();
    return res;
}

static async Task<List<int>> FilteredKnn(NpgsqlConnection c, string sql, int tenant, float[] q, string mode, bool exact)
{
    await using var tx = await c.BeginTransactionAsync();
    await Exec(c, exact ? "SET LOCAL enable_indexscan = off; SET LOCAL enable_bitmapscan = off"
                        : $"SET LOCAL hnsw.ef_search = 40; SET LOCAL hnsw.iterative_scan = '{mode}'");
    await using var cmd = new NpgsqlCommand(sql, c, tx);
    cmd.Parameters.AddWithValue(tenant);
    cmd.Parameters.AddWithValue(new Vector(q));
    var res = new List<int>();
    await using (var r = await cmd.ExecuteReaderAsync())
        while (await r.ReadAsync()) res.Add(r.GetInt32(0));
    await tx.CommitAsync();
    return res;
}
