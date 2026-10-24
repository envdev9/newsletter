using System.Diagnostics;
using System.Text.Json;
using Microsoft.EntityFrameworkCore;
using Npgsql;
using PgPlanDemo;

// Uzycie: dotnet run -- --pg "Host=127.0.0.1;Port=15432;Username=postgres;Password=...;Database=postgres" --plan-dir <katalog>
// Wymaga PostgreSQL z shared_preload_libraries=pg_stat_statements (sekcja 1) i rozszerzenia pg_trgm (contrib - jest w obrazie postgres:16).
string? adminCs = null;
var planDir = "plans";
for (var i = 0; i < args.Length - 1; i++)
{
    if (args[i] == "--pg") adminCs = args[i + 1];
    if (args[i] == "--plan-dir") planDir = args[i + 1];
}
if (adminCs is null)
{
    Console.Error.WriteLine("Podaj --pg <connection string do PostgreSQL (superuser)>");
    return 2;
}

const string DbName = "prasowka_ai_1009";
var admin = new NpgsqlConnectionStringBuilder(adminCs);
var appCs = new NpgsqlConnectionStringBuilder(adminCs) { Database = DbName }.ConnectionString;
var lowMemCs = new NpgsqlConnectionStringBuilder(appCs) { Options = "-c work_mem=64kB" }.ConnectionString;

static void Exec(string cs, string sql)
{
    using var c = new NpgsqlConnection(cs);
    c.Open();
    using var cmd = new NpgsqlCommand(sql, c) { CommandTimeout = 300 };
    cmd.ExecuteNonQuery();
}

static T Scalar<T>(string cs, string sql)
{
    using var c = new NpgsqlConnection(cs);
    c.Open();
    using var cmd = new NpgsqlCommand(sql, c) { CommandTimeout = 300 };
    return (T)Convert.ChangeType(cmd.ExecuteScalar()!, typeof(T));
}

Exec(admin.ConnectionString, $"DROP DATABASE IF EXISTS {DbName} WITH (FORCE)");
Exec(admin.ConnectionString, $"CREATE DATABASE {DbName}");
try
{
    Exec(appCs, "CREATE EXTENSION IF NOT EXISTS pg_stat_statements");
    Exec(appCs, "CREATE EXTENSION IF NOT EXISTS pg_trgm");
    using (var db = new ShopContext(appCs)) { db.Database.EnsureCreated(); }
    Exec(appCs, "INSERT INTO customers (\"Id\", \"Email\") SELECT i, 'user' || i || '.' || substr(md5(i::text), 1, 12) || '@' || " +
                "(ARRAY['example.com','mail.test','corp.example','demo.org'])[1 + i % 4] FROM generate_series(1, 200000) i");
    Exec(appCs, "ANALYZE customers");
    Console.WriteLine($"PostgreSQL: {Scalar<string>(appCs, "SHOW server_version")}, collation bazy: {Scalar<string>(appCs, "SELECT datcollate FROM pg_database WHERE datname = current_database()")}, " +
                      $"wierszy: {Scalar<int>(appCs, "SELECT count(*) FROM customers")}");

    // ================= Sekcja 1: ids.Contains(...) w Npgsql =================
    Console.WriteLine();
    Console.WriteLine("== Sekcja 1: ids.Contains(c.Id) - jak Npgsql tlumaczy liste i ile wpisow robi w pg_stat_statements ==");
    var modes = new (string Name, ParameterTranslationMode? Mode)[]
    {
        ("domyslny (nie ustawiony)", null),
        ("Parameter", ParameterTranslationMode.Parameter),
        ("Constant", ParameterTranslationMode.Constant),
    };
    var three = new List<int> { 10, 20, 30 };
    foreach (var (name, mode) in modes)
    {
        using var db = new ShopContext(appCs, mode);
        Console.WriteLine($"SQL dla 3 elementow, tryb {name}:");
        Console.WriteLine(db.Customers.Where(c => three.Contains(c.Id)).ToQueryString());
    }
    foreach (var (name, mode) in modes)
    {
        Exec(appCs, "SELECT pg_stat_statements_reset()");
        var sw = Stopwatch.StartNew();
        using (var db = new ShopContext(appCs, mode))
        {
            for (var n = 1; n <= 300; n++)
            {
                Queries.ByIds(db, Enumerable.Range(1, n).ToList());
            }
        }
        sw.Stop();
        var entries = Scalar<int>(appCs, "SELECT count(*) FROM pg_stat_statements WHERE query LIKE '%FROM customers%' AND query NOT LIKE '%pg_stat%'");
        var calls = Scalar<int>(appCs, "SELECT coalesce(sum(calls), 0) FROM pg_stat_statements WHERE query LIKE '%FROM customers%' AND query NOT LIKE '%pg_stat%'");
        Console.WriteLine($"{name,-22} wpisow w pg_stat_statements: {entries,3}   wywolan: {calls}   czas 300 zapytan: {sw.ElapsedMilliseconds} ms");
    }
    Console.WriteLine("lista 5000 id:");
    foreach (var (name, mode) in modes)
    {
        using var db = new ShopContext(appCs, mode);
        var ids = Enumerable.Range(1, 5000).ToList();
        Queries.ByIds(db, ids.Take(10).ToList()); // rozgrzewka (polaczenie, JIT)
        var sw = Stopwatch.StartNew();
        var n = Queries.ByIds(db, ids);
        sw.Stop();
        Console.WriteLine($"{name,-22} wynik={n}, {sw.ElapsedMilliseconds} ms");
    }

    // ================= Sekcja 2: LIKE a indeksy =================
    Console.WriteLine();
    Console.WriteLine("== Sekcja 2: eq / StartsWith / Contains / EndsWith na varchar(100), 200 000 wierszy, EXPLAIN (ANALYZE, BUFFERS) z interceptora ==");
    var sample = Scalar<string>(appCs, "SELECT \"Email\" FROM customers WHERE \"Id\" = 77777");
    var prefix = sample[..(sample.IndexOf('.') + 5)];       // np. "user77777.1a2b"
    var term = sample.Substring(sample.IndexOf('.') + 3, 7);  // 7 znakow z hasha
    Console.WriteLine($"probka: eq='{sample}' prefix='{prefix}' term='{term}' suffix='@corp.example'");

    var variants = new (string Name, string[] Sql)[]
    {
        ("btree", Array.Empty<string>()),
        ("btree_pattern_ops", new[] { "DROP INDEX \"IX_customers_Email\"", "CREATE INDEX ix_email_pattern ON customers (\"Email\" varchar_pattern_ops)" }),
        ("gin_trgm", new[] { "DROP INDEX ix_email_pattern", "CREATE INDEX ix_email_trgm ON customers USING gin (\"Email\" gin_trgm_ops)" }),
    };
    Console.WriteLine($"{"indeks",-18} {"zapytanie",-11} {"wierszy",8} {"bufory",8} {"ms",8}  wezly (skan)");
    foreach (var (vname, sqls) in variants)
    {
        foreach (var s in sqls) Exec(appCs, s);
        Exec(appCs, "ANALYZE customers");
        var cap = new PgPlanCaptureInterceptor(appCs, planDir);
        using var db = new ShopContext(appCs, ParameterTranslationMode.Parameter, cap);
        var runs = new (string Q, Func<int> Run)[]
        {
            ("eq", () => Queries.Equals(db, sample)),
            ("startswith", () => Queries.StartsWith(db, prefix)),
            ("contains", () => Queries.Contains(db, term)),
            ("endswith", () => Queries.EndsWith(db, "@corp.example")),
        };
        foreach (var (q, run) in runs)
        {
            cap.NextLabel = $"{vname}_{q}";
            var rows = run();
            var info = PlanInfo.Read(Path.Combine(planDir, $"{vname}_{q}.json"));
            Console.WriteLine($"{vname,-18} {q,-11} {rows,8} {info.Buffers,8} {info.ExecutionMs,8:F2}  {info.ScanNodes}  {{{info.Cond}}}");
        }
    }

    // ================= Sekcja 3: spill w Postgresie =================
    Console.WriteLine();
    Console.WriteLine("== Sekcja 3: work_mem=64kB - hash join i sort na dysk (ten sam interceptor, EXPLAIN ANALYZE) ==");
    {
        Exec(appCs, "DROP INDEX ix_email_trgm");
        Exec(appCs, "ANALYZE customers");
        foreach (var (label, cs) in new[] { ("normal", appCs), ("lowmem", lowMemCs) })
        {
            var cap = new PgPlanCaptureInterceptor(cs, planDir);
            using var db = new ShopContext(cs, ParameterTranslationMode.Parameter, cap);
            cap.NextLabel = $"{label}_hashjoin";
            Queries.SelfJoinCount(db);
            var hj = PlanInfo.Read(Path.Combine(planDir, $"{label}_hashjoin.json"));
            cap.NextLabel = $"{label}_sort";
            Queries.SortAll(db);
            var so = PlanInfo.Read(Path.Combine(planDir, $"{label}_sort.json"));
            Console.WriteLine($"work_mem {(label == "normal" ? "domyslny" : "64kB    ")}  join: {hj.Spill,-40} {hj.ExecutionMs,8:F1} ms | sort: {so.Spill,-40} {so.ExecutionMs,8:F1} ms");
        }
    }
    Console.WriteLine($"-- plany zapisane w {planDir}");
}
finally
{
    Exec(admin.ConnectionString, $"DROP DATABASE IF EXISTS {DbName} WITH (FORCE)");
    Console.WriteLine($"-- baza {DbName} usunieta");
}
return 0;

namespace PgPlanDemo
{
    /// <summary>Wyciaga z planu JSON (EXPLAIN FORMAT JSON) kilka liczb do tabeli w konsoli.</summary>
    public record PlanInfo(double ExecutionMs, long Buffers, string ScanNodes, string Spill, string Cond)
    {
        public static PlanInfo Read(string path)
        {
            using var doc = JsonDocument.Parse(File.ReadAllText(path));
            var root = doc.RootElement[0];
            var plan = root.GetProperty("Plan");
            var scans = new List<string>();
            var spills = new List<string>();
            var conds = new List<string>();
            Walk(plan, scans, spills, conds);
            long buffers = Get(plan, "Shared Hit Blocks") + Get(plan, "Shared Read Blocks");
            return new PlanInfo(root.GetProperty("Execution Time").GetDouble(), buffers,
                string.Join(" + ", scans), spills.Count == 0 ? "bez spilla" : string.Join("; ", spills),
                string.Join(" | ", conds));
        }

        private static long Get(JsonElement e, string name) => e.TryGetProperty(name, out var v) ? v.GetInt64() : 0;

        private static void Walk(JsonElement n, List<string> scans, List<string> spills, List<string> conds)
        {
            var type = n.GetProperty("Node Type").GetString()!;
            foreach (var key in new[] { "Filter", "Index Cond", "Recheck Cond" })
            {
                if (n.TryGetProperty(key, out var cv)) conds.Add(cv.GetString()!);
            }
            if (type.Contains("Scan"))
            {
                var rel = n.TryGetProperty("Index Name", out var ix) ? ix.GetString() : n.GetProperty("Relation Name").GetString();
                scans.Add($"{type} [{rel}]");
            }
            if (type == "Hash" && n.TryGetProperty("Hash Batches", out var hb) && hb.GetInt32() > 1)
            {
                spills.Add($"Hash: {hb.GetInt32()} partii (batches)");
            }
            if (type == "Sort" && n.TryGetProperty("Sort Method", out var sm) && sm.GetString()!.Contains("external"))
            {
                spills.Add($"Sort: {sm.GetString()} {n.GetProperty("Sort Space Used").GetInt64()}kB na dysku");
            }
            if (n.TryGetProperty("Plans", out var kids))
            {
                foreach (var k in kids.EnumerateArray()) Walk(k, scans, spills, conds);
            }
        }
    }
}
