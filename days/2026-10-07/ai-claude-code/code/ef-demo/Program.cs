using System.Data.Common;
using Microsoft.Data.Sqlite;
using Microsoft.Data.SqlClient;
using Microsoft.EntityFrameworkCore;
using Microsoft.EntityFrameworkCore.Diagnostics;
using EfDemo;

// Sekcja 1: SQL generowany przez prawdziwego providera SqlServer - BEZ polaczenia z baza.
Section1_OfflineSql();
// Sekcja 2: liczba polecen / sledzonych encji - SQLite in-memory.
Section2_Measure();
// Sekcja 3 (opcjonalna): prawdziwy SQL Server (EFDEMO_SQLSERVER = connection string do master).
// Connection string mozna podac argumentem `--sqlserver "<cs>"` albo zmienna srodowiskowa.
var live = ArgValue(args, "--sqlserver") ?? Environment.GetEnvironmentVariable("EFDEMO_SQLSERVER");
var planDirArg = ArgValue(args, "--plan-dir") ?? Environment.GetEnvironmentVariable("EFDEMO_PLAN_DIR");
if (!string.IsNullOrEmpty(live))
{
    Section3_Live(live, planDirArg);
}
else
{
    Console.WriteLine();
    Console.WriteLine("== Sekcja 3 pominieta: brak --sqlserver \"<connection string>\" (ani zmiennej EFDEMO_SQLSERVER) ==");
}

static void Section1_OfflineSql()
{
    Console.WriteLine("== Sekcja 1: SQL z EF Core (provider SqlServer, bez polaczenia) ==");
    var o = new DbContextOptionsBuilder()
        .UseSqlServer("Server=localhost;Database=Offline;TrustServerCertificate=true").Options;
    using var bad = new BadShopContext(o);
    using var good = new GoodShopContext(o);
    var email = "user42@example.com";

    Console.WriteLine("-- BadShopContext (Email: zwykly string):");
    Console.WriteLine(BadQueries.EmailQuery(bad, email).ToQueryString());
    Console.WriteLine("-- GoodShopContext (Email: IsUnicode(false)):");
    Console.WriteLine(GoodQueries.EmailQuery(good, email).ToQueryString());
    Console.WriteLine("-- funkcja na kolumnie (ToLower) w Where:");
    Console.WriteLine(bad.Customers.Where(c => c.Email.ToLower() == email.ToLower()).ToQueryString());
}

static void Section2_Measure()
{
    Console.WriteLine();
    Console.WriteLine("== Sekcja 2: pomiary na SQLite in-memory (20 klientow, 200 zamowien, 160 tagow) ==");
    var stats = new Stats();
    using var conn = new SqliteConnection("DataSource=:memory:");
    conn.Open();
    var opts = new DbContextOptionsBuilder().UseSqlite(conn).AddInterceptors(stats).Options;

    using (var seed = new GoodShopContext(opts))
    {
        seed.Database.EnsureCreated();
        for (var i = 1; i <= 20; i++)
        {
            var c = new Customer { Email = $"user{i}@example.com", Name = $"User {i}" };
            for (var j = 1; j <= 10; j++) c.Orders.Add(new Order { Total = (i * 37 + j * 91) % 1000 });
            for (var j = 1; j <= 8; j++) c.Tags.Add(new Tag { Label = $"tag{j}" });
            seed.Customers.Add(c);
        }
        seed.SaveChanges();
    }

    Console.WriteLine($"{"scenariusz",-36} {"polecen",8} {"sledzonych",11}");
    Measure<BadShopContext>("N+1 (zle)", stats, opts, db => BadQueries.OrderCountsNPlusOne(db).Count);
    Measure<GoodShopContext>("N+1 (dobrze: Select + Count)", stats, opts, db => GoodQueries.OrderCounts(db).Count);
    Measure<BadShopContext>("ToList() przed Where (zle)", stats, opts, db => BadQueries.ExpensiveOrdersInMemory(db));
    Measure<GoodShopContext>("Count w SQL (dobrze)", stats, opts, db => GoodQueries.ExpensiveOrders(db));
    Measure<BadShopContext>("Include x2 bez split (zle)", stats, opts, db => BadQueries.CustomersWithOrdersAndTags(db).Count);
    Measure<GoodShopContext>("Include x2 + AsSplitQuery (dobrze)", stats, opts, db => GoodQueries.CustomersWithOrdersAndTags(db).Count);
    Measure<BadShopContext>("odczyt bez AsNoTracking (zle)", stats, opts, db => BadQueries.AllOrdersTracked(db).Count);
    Measure<GoodShopContext>("odczyt z AsNoTracking (dobrze)", stats, opts, db => GoodQueries.AllOrders(db).Count);

    // Ile wierszy zwraca pojedyncze zapytanie z dwoma Include (iloczyn Orders x Tags per klient)?
    using var probe = new BadShopContext(opts);
    var sql = probe.Customers.AsNoTracking().Include(c => c.Orders).Include(c => c.Tags).ToQueryString();
#pragma warning disable EF1003 // sql pochodzi z ToQueryString() wlasnego zapytania, nie z wejscia uzytkownika
    var rows = probe.Database.SqlQueryRaw<int>("SELECT COUNT(*) AS Value FROM (" + sql + ")").Single();
#pragma warning restore EF1003
    Console.WriteLine($"zapytanie z Include x2 zwraca {rows} wierszy; split query: 20 + 200 + 160 = 380");
    Console.WriteLine("(SQLite nie batchuje INSERT-ow, wiec SaveChanges w petli mierzymy na prawdziwym SQL Server - sekcja 3)");
}

static void Measure<T>(string name, Stats stats, DbContextOptions opts, Func<T, int> action) where T : DbContext
{
    using var db = (T)Activator.CreateInstance(typeof(T), opts)!;
    stats.Reset();
    action(db);
    Console.WriteLine($"{name,-36} {stats.Commands,8} {db.ChangeTracker.Entries().Count(),11}");
}

static string? ArgValue(string[] args, string name)
{
    var i = Array.IndexOf(args, name);
    return i >= 0 && i + 1 < args.Length ? args[i + 1] : null;
}

static void Section3_Live(string masterConnection, string? planDir)
{
    Console.WriteLine();
    Console.WriteLine("== Sekcja 3: prawdziwy SQL Server (kolumna varchar(100) + indeks, 50 000 wierszy) ==");
    const string dbName = "PrasowkaAiEf1007";
    Exec(masterConnection, $"IF DB_ID('{dbName}') IS NOT NULL BEGIN ALTER DATABASE {dbName} SET SINGLE_USER WITH ROLLBACK IMMEDIATE; DROP DATABASE {dbName}; END; CREATE DATABASE {dbName};");
    try
    {
        var cs = new SqlConnectionStringBuilder(masterConnection) { InitialCatalog = dbName }.ConnectionString;
        Exec(cs, "CREATE TABLE dbo.Customers (Id int IDENTITY PRIMARY KEY, Email varchar(100) NOT NULL, Name nvarchar(100) NOT NULL);");
        Exec(cs, "CREATE TABLE dbo.Tags (Id int IDENTITY PRIMARY KEY, CustomerId int NOT NULL, Label nvarchar(max) NOT NULL);");
        Exec(cs, "INSERT INTO dbo.Customers (Email, Name) SELECT 'user' + CAST(value AS varchar(10)) + '@example.com', N'User ' + CAST(value AS nvarchar(10)) FROM GENERATE_SERIES(1, 50000);");
        Exec(cs, "CREATE INDEX IX_Customers_Email ON dbo.Customers (Email);");

        foreach (var kind in new[] { "bad", "good" })
        {
            var probe = new LiveProbe();
            var opts = new DbContextOptionsBuilder().UseSqlServer(cs).AddInterceptors(probe).Options;
            int n;
            if (kind == "bad")
            {
                using var db = new BadShopContext(opts);
                n = BadQueries.EmailQuery(db, "user42424@example.com").AsNoTracking().ToList().Count;
            }
            else
            {
                using var db = new GoodShopContext(opts);
                n = GoodQueries.EmailQuery(db, "user42424@example.com").AsNoTracking().ToList().Count;
            }
            Console.WriteLine($"-- {kind}: wynik={n} wiersz, parametr: {probe.ParamInfo}");
        }

        // Plan z cache planow: to plan zapytania, ktore EF naprawde wyslal (sp_executesql z parametrem).
        if (planDir != null)
        {
            foreach (var (kind, decl) in new[] { ("bad", "(@email nvarchar(100))%"), ("good", "(@email varchar(100))%") })
            {
                using var c = new SqlConnection(cs);
                c.Open();
                using var cmd = c.CreateCommand();
                cmd.CommandText = "SELECT TOP 1 CAST(p.query_plan AS nvarchar(max)), qs.total_logical_reads, qs.execution_count FROM sys.dm_exec_query_stats qs " +
                                  "CROSS APPLY sys.dm_exec_sql_text(qs.sql_handle) t " +
                                  "CROSS APPLY sys.dm_exec_query_plan(qs.plan_handle) p " +
                                  "WHERE t.text LIKE @decl AND t.text LIKE '%FROM [[]Customers]%' AND t.text NOT LIKE '%dm_exec%'";
                cmd.Parameters.Add(new SqlParameter("@decl", decl));
                using var r = cmd.ExecuteReader();
                if (!r.Read()) { Console.WriteLine($"-- brak planu w cache dla {kind}"); continue; }
                var path = Path.Combine(planDir, $"ef_{kind}.xml");
                File.WriteAllText(path, r.GetString(0));
                Console.WriteLine($"-- {kind}: logical reads (dm_exec_query_stats) = {r.GetInt64(1)} przy {r.GetInt64(2)} wykonaniu, plan zapisany: {path}");
            }
        }

        // SaveChanges w petli vs jeden SaveChanges - liczymy polecenia wyslane do SQL Server.
        var labels = Enumerable.Range(1, 20).Select(i => $"x{i}").ToList();
        var stats = new Stats();
        var so = new DbContextOptionsBuilder().UseSqlServer(cs).AddInterceptors(stats).Options;
        using (var db = new BadShopContext(so)) { BadQueries.AddOneByOne(db, labels, 1); }
        Console.WriteLine($"-- SaveChanges w petli (20 Tag): {stats.Commands} polecen do SQL Server");
        stats.Reset();
        using (var db = new GoodShopContext(so)) { GoodQueries.AddBatch(db, labels, 1); }
        Console.WriteLine($"-- jeden SaveChanges (20 Tag):   {stats.Commands} polecen do SQL Server");
    }
    finally
    {
        SqlConnection.ClearAllPools();
        Exec(masterConnection, $"ALTER DATABASE {dbName} SET SINGLE_USER WITH ROLLBACK IMMEDIATE; DROP DATABASE {dbName};");
        Console.WriteLine($"-- baza {dbName} usunieta");
    }
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

class Stats : DbCommandInterceptor
{
    public int Commands;
    public void Reset() { Commands = 0; }

    public override InterceptionResult<DbDataReader> ReaderExecuting(
        DbCommand command, CommandEventData eventData, InterceptionResult<DbDataReader> result)
    {
        Commands++;
        return result;
    }
}

// Sonda dla prawdziwego SQL Servera: zapamietuje typ parametru, ktory EF faktycznie wysyla.
class LiveProbe : DbCommandInterceptor
{
    public string ParamInfo { get; private set; } = "";

    public override InterceptionResult<DbDataReader> ReaderExecuting(
        DbCommand command, CommandEventData eventData, InterceptionResult<DbDataReader> result)
    {
        if (command.Connection is SqlConnection && command.CommandText.Contains("FROM [Customers]"))
        {
            ParamInfo = string.Join(", ", command.Parameters.Cast<SqlParameter>()
                .Select(p => $"{p.ParameterName} {p.SqlDbType}({p.Size})"));
        }
        return result;
    }
}
