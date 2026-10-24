using System.Diagnostics;
using Microsoft.Data.SqlClient;
using Microsoft.EntityFrameworkCore;
using EfPlanDemo;

// Uzycie:  dotnet run --project ef-plan-demo -- [--sqlserver "<connection string do master>"] [--plan-dir <katalog>]
// Sekcja 1 dziala bez bazy (ToQueryString). Sekcje 2-4 wymagaja --sqlserver (wlasny, jednorazowy SQL Server).
var live = ArgValue(args, "--sqlserver") ?? Environment.GetEnvironmentVariable("EFPLAN_SQLSERVER");
var planDir = ArgValue(args, "--plan-dir") ?? Path.Combine(Path.GetTempPath(), "efplan-out");

Section1_OfflineContains();
if (string.IsNullOrEmpty(live))
{
    Console.WriteLine();
    Console.WriteLine("== Sekcje 2-4 pominiete: brak --sqlserver \"<connection string>\" ==");
    return;
}
Section234_Live(live, planDir);

static DbContextOptions Opts(string cs, ParameterTranslationMode? mode = null,
    Microsoft.EntityFrameworkCore.Diagnostics.IInterceptor? interceptor = null)
{
    var b = new DbContextOptionsBuilder();
    // Pulapka (zmierzona, patrz artykul): z cache dostawcy uslug (domyslnie) pierwszy tryb "wygrywa" w calym procesie -
    // skompilowane zapytanie siedzi we wspoldzielonym cache i kolejne tryby dostaja SQL z pierwszego. W prawdziwej
    // aplikacji tryb ustawia sie raz; do POROWNANIA trybow w jednym procesie trzeba cache wylaczyc.
    b.EnableServiceProviderCaching(false);
    b.ConfigureWarnings(w => w.Ignore(Microsoft.EntityFrameworkCore.Diagnostics.CoreEventId.ManyServiceProvidersCreatedWarning));
    b.UseSqlServer(cs, o =>
    {
        if (mode is { } m) o.UseParameterizedCollectionMode(m);
    });
    if (interceptor is not null) b.AddInterceptors(interceptor);
    return b.Options;
}

static (string Name, ParameterTranslationMode? Mode)[] Modes() => new[]
{
    ("domyslny", (ParameterTranslationMode?)null),
    ("Parameter (OPENJSON)", ParameterTranslationMode.Parameter),
    ("Constant", ParameterTranslationMode.Constant),
};

static void Section1_OfflineContains()
{
    Console.WriteLine("== Sekcja 1: ids.Contains(c.Id) - ile parametrow generuje EF Core 10 (bez polaczenia z baza) ==");
    const string fake = "Server=localhost;Database=Offline;TrustServerCertificate=true";
    foreach (var (name, mode) in Modes())
    {
        using var db = new ShopContext(Opts(fake, mode));
        Console.Write($"tryb {name,-22} rozmiar listy -> liczba DECLARE:");
        foreach (var n in new[] { 1, 2, 5, 6, 9, 17, 100, 500, 1000, 2000, 2100, 2200 })
        {
            var ids = Enumerable.Range(1, n).ToList();
            var sql = Queries.ByIds(db, ids).ToQueryString();
            Console.Write($" {n}->{sql.Split('\n').Count(l => l.StartsWith("DECLARE"))}");
        }
        Console.WriteLine();
    }
    foreach (var (name, mode) in Modes().Take(2))
    {
        using var db = new ShopContext(Opts(fake, mode));
        Console.WriteLine($"-- tryb {name}, 3 elementy:");
        Console.WriteLine(Queries.ByIds(db, new List<int> { 10, 20, 30 }).ToQueryString());
    }
}

static void Section234_Live(string master, string planDir)
{
    const string dbName = "PrasowkaAiPlan1008";
    Exec(master, $"IF DB_ID('{dbName}') IS NOT NULL BEGIN ALTER DATABASE {dbName} SET SINGLE_USER WITH ROLLBACK IMMEDIATE; DROP DATABASE {dbName}; END; CREATE DATABASE {dbName};");
    try
    {
        var cs = new SqlConnectionStringBuilder(master) { InitialCatalog = dbName }.ConnectionString;
        Exec(cs, "CREATE TABLE dbo.Customers (Id int IDENTITY PRIMARY KEY, Email varchar(100) NOT NULL, Name nvarchar(100) NOT NULL);");
        Exec(cs, "INSERT INTO dbo.Customers (Email, Name) SELECT 'user' + CAST(value AS varchar(10)) + '@example.com', N'User ' + CAST(value AS nvarchar(10)) FROM GENERATE_SERIES(1, 50000);");
        Exec(cs, "CREATE INDEX IX_Customers_Email ON dbo.Customers (Email);");

        Console.WriteLine();
        Console.WriteLine("== Sekcja 2: plan cache - listy o rozmiarach 1..300, po jednym zapytaniu na rozmiar ==");
        using (var warm = new ShopContext(Opts(cs))) // rozgrzewka JIT/polaczen, zeby pierwszy tryb nie placil za wszystkich
        {
            _ = Queries.ByIds(warm, new List<int> { 1 }).ToList();
        }
        var variants = Modes().Select(m => (m.Name, m.Mode, Q: (Func<ShopContext, List<int>, IQueryable<Customer>>)Queries.ByIds))
            .Append(("EF.Constant(ids) w kodzie", null, Queries.ByIdsConstant));
        foreach (var (name, mode, q) in variants)
        {
            Exec(cs, "ALTER DATABASE SCOPED CONFIGURATION CLEAR PROCEDURE_CACHE;");
            var sw = Stopwatch.StartNew();
            using (var db = new ShopContext(Opts(cs, mode)))
            {
                for (var n = 1; n <= 300; n++)
                {
                    var ids = Enumerable.Range(1, n).ToList();
                    _ = q(db, ids).ToList();
                }
            }
            sw.Stop();
            Console.WriteLine($"{name,-26} wpisow w plan cache: {CachedPlans(cs),4}   czas 300 zapytan: {sw.ElapsedMilliseconds} ms");
        }

        Console.WriteLine();
        Console.WriteLine("== Sekcja 3: duza lista (5000 id) w roznych trybach ==");
        foreach (var (name, mode) in Modes())
        {
            try
            {
                using var db = new ShopContext(Opts(cs, mode));
                var ids = Enumerable.Range(1, 5000).ToList();
                var sqlText = Queries.ByIds(db, ids).ToQueryString();
                var declares = sqlText.Split('\n').Count(l => l.StartsWith("DECLARE"));
                var sw = Stopwatch.StartNew();
                var n = Queries.ByIds(db, ids).Count();
                sw.Stop();
                Console.WriteLine($"{name,-22} SQL: {declares} DECLARE, {sqlText.Length} znakow; wynik={n}, {sw.ElapsedMilliseconds} ms");
            }
            catch (Exception ex)
            {
                var msg = ex.GetBaseException().Message.Split('\n')[0];
                Console.WriteLine($"{name,-22} WYJATEK {ex.GetBaseException().GetType().Name}: {msg}");
            }
        }

        Console.WriteLine();
        Console.WriteLine("== Sekcja 4: LIKE '%x%' vs LIKE 'x%' na varchar(100) z indeksem, 50 000 wierszy (plan z interceptora) ==");
        var cap = new PlanCaptureInterceptor(cs, planDir);
        var probes = new (string Label, Func<ShopContext, IQueryable<Customer>> Query)[]
        {
            ("eq",          db => Queries.EmailEquals(db, "user42424@example.com")),
            ("startswith",  db => Queries.EmailStartsWith(db, "user4242")),
            ("contains",    db => Queries.EmailContains(db, "42424@")),
            ("endswith",    db => Queries.EmailEndsWith(db, "424@example.com")),
        };
        Console.WriteLine($"{"zapytanie",-12} {"wierszy",8} {"logical reads",14}   WHERE w SQL");
        foreach (var (label, q) in probes)
        {
            Exec(cs, "ALTER DATABASE SCOPED CONFIGURATION CLEAR PROCEDURE_CACHE;");
            using var db = new ShopContext(Opts(cs, null, cap));
            cap.NextLabel = "like_" + label;
            var rows = q(db).ToList().Count;
            Console.WriteLine($"{label,-12} {rows,8} {LogicalReads(cs),14}   {WhereLine(q(db).ToQueryString())}");
        }
        Console.WriteLine($"-- plany zapisane ({cap.Written.Count}): {string.Join(", ", cap.Written.Select(Path.GetFileName))}");
        foreach (var s in cap.Skipped) Console.WriteLine($"-- pominiety plan: {s}");
    }
    finally
    {
        SqlConnection.ClearAllPools();
        Exec(master, $"ALTER DATABASE {dbName} SET SINGLE_USER WITH ROLLBACK IMMEDIATE; DROP DATABASE {dbName};");
        Console.WriteLine($"-- baza {dbName} usunieta");
    }
}

static string WhereLine(string sql) =>
    sql.Split('\n').FirstOrDefault(l => l.StartsWith("WHERE"))?.Trim() ?? "?";

static int CachedPlans(string cs)
{
    using var c = new SqlConnection(cs);
    c.Open();
    using var cmd = c.CreateCommand();
    // 'Prepared' = sp_executesql z parametrami; 'Adhoc' = literaly wpisane w tekst SQL (tryb Constant)
    cmd.CommandText = "SELECT COUNT(*) FROM sys.dm_exec_cached_plans cp CROSS APPLY sys.dm_exec_sql_text(cp.plan_handle) t " +
                      "WHERE cp.objtype IN ('Prepared', 'Adhoc') AND t.text LIKE '%FROM [[]Customers]%' AND t.text NOT LIKE '%dm_exec%'";
    return (int)cmd.ExecuteScalar()!;
}

static long LogicalReads(string cs)
{
    using var c = new SqlConnection(cs);
    c.Open();
    using var cmd = c.CreateCommand();
    cmd.CommandText = "SELECT TOP 1 qs.total_logical_reads FROM sys.dm_exec_query_stats qs CROSS APPLY sys.dm_exec_sql_text(qs.sql_handle) t " +
                      "WHERE t.text LIKE '%FROM [[]Customers]%' AND t.text NOT LIKE '%dm_exec%'";
    return (long)(cmd.ExecuteScalar() ?? -1L);
}

static void Exec(string cs, string sql)
{
    using var c = new SqlConnection(cs);
    c.Open();
    using var cmd = c.CreateCommand();
    cmd.CommandText = sql;
    cmd.CommandTimeout = 120;
    cmd.ExecuteNonQuery();
}

static string? ArgValue(string[] args, string name)
{
    var i = Array.IndexOf(args, name);
    return i >= 0 && i + 1 < args.Length ? args[i + 1] : null;
}
