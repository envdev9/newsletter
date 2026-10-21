using IdemDemo;
using MassTransit;
using Microsoft.Data.Sqlite;
using Microsoft.Extensions.DependencyInjection;
using Microsoft.Extensions.Hosting;
using Microsoft.Extensions.Logging;

// Uzycie:
//   dotnet <dll> reset                          - czysci baze SQLite i kolejke
//   dotnet <dll> worker <naive|atomic> <nazwa> <sekundy>  - konsument przez N sekund
//   dotnet <dll> publish <liczba-platnosci>     - kazda platnosc publikowana DWA razy (retry producenta)
//   dotnet <dll> report                         - ile razy wykonal sie skutek uboczny na klucz
var mode = args.Length > 0 ? args[0] : "report";

if (mode == "reset")
{
    Db.Reset();
    using var http = new HttpClient { BaseAddress = new Uri("http://127.0.0.1:56732/api/") };
    http.DefaultRequestHeaders.Authorization = new("Basic", Convert.ToBase64String("guest:guest"u8.ToArray()));
    var r = await http.DeleteAsync("queues/%2f/idem-pay");
    Console.WriteLine($"baza wyczyszczona, DELETE idem-pay -> {(int)r.StatusCode}");
    return;
}

if (mode == "report")
{
    Db.Report();
    return;
}

var builder = Host.CreateApplicationBuilder();
builder.Logging.SetMinimumLevel(LogLevel.Critical);

if (mode == "publish")
{
    var count = args.Length > 1 ? int.Parse(args[1]) : 5;
    builder.Services.AddMassTransit(x => x.UsingRabbitMq((ctx, cfg) =>
    {
        cfg.Host("127.0.0.1", 56731, "/", h => { h.Username("guest"); h.Password("guest"); });
    }));
    using var pub = builder.Build();
    await pub.StartAsync();
    var bus = pub.Services.GetRequiredService<IPublishEndpoint>();
    for (var i = 1; i <= count; i++)
    {
        // ten sam PaymentId, DWA rozne MessageId - jak retry po timeoucie u producenta
        await bus.Publish(new Pay($"pay-{i}", 100 * i));
        await bus.Publish(new Pay($"pay-{i}", 100 * i));
    }
    Console.WriteLine($"opublikowano {count * 2} wiadomosci ({count} platnosci x 2)");
    await pub.StopAsync();
    return;
}

if (mode == "worker")
{
    var strategy = args[1];
    var name = args[2];
    var seconds = int.Parse(args[3]);
    builder.Services.AddSingleton(new WorkerInfo(strategy, name));
    builder.Services.AddMassTransit(x =>
    {
        x.AddConsumer<PayConsumer>();
        x.UsingRabbitMq((ctx, cfg) =>
        {
            cfg.Host("127.0.0.1", 56731, "/", h => { h.Username("guest"); h.Password("guest"); });
            cfg.ReceiveEndpoint("idem-pay", e =>
            {
                e.PrefetchCount = 1;
                e.ConcurrentMessageLimit = 1;
                e.ConfigureConsumer<PayConsumer>(ctx);
            });
        });
    });
    builder.Services.Configure<HostOptions>(o => o.ShutdownTimeout = TimeSpan.FromSeconds(10));
    using var host = builder.Build();
    await host.StartAsync();
    Console.WriteLine($"[{name}] start strategy={strategy} pracuje {seconds}s");
    await Task.Delay(TimeSpan.FromSeconds(seconds));
    await host.StopAsync();
    Console.WriteLine($"[{name}] koniec");
    return;
}

Console.WriteLine("nieznany tryb");

namespace IdemDemo
{
    public record Pay(string PaymentId, int Amount);

    public record WorkerInfo(string Strategy, string Name);

    public class PayConsumer(WorkerInfo me) : IConsumer<Pay>
    {
        public async Task Consume(ConsumeContext<Pay> context)
        {
            var key = context.Message.PaymentId;
            var t = DateTime.UtcNow.ToString("HH:mm:ss.fff");
            if (me.Strategy == "naive")
            {
                // check-then-act: "czy juz byl?" i dopiero potem "zrob + zapisz"
                if (Db.AlreadyProcessed(key))
                {
                    Console.WriteLine($"{t} [{me.Name}] {key} SKIP (widzial wpis)");
                    return;
                }
                await Task.Delay(300); // skutek uboczny trwa (np. wywolanie bramki platnosci)
                Db.RecordEffect(key, me.Name);
                Db.MarkProcessedIgnore(key, me.Name);
                Console.WriteLine($"{t} [{me.Name}] {key} EFEKT (naive)");
            }
            else
            {
                // atomowo: jedno INSERT jest jednoczesnie sprawdzeniem i zajeciem klucza
                if (!Db.TryClaim(key, me.Name))
                {
                    Console.WriteLine($"{t} [{me.Name}] {key} SKIP (klucz zajety)");
                    return;
                }
                await Task.Delay(300);
                Db.RecordEffect(key, me.Name);
                Console.WriteLine($"{t} [{me.Name}] {key} EFEKT (atomic)");
            }
        }
    }

    public static class Db
    {
        private static readonly string Path = System.IO.Path.Combine(System.IO.Path.GetTempPath(), "mt-idem-demo.db");
        private static string Cs => $"Data Source={Path}";

        private static SqliteConnection Open()
        {
            var c = new SqliteConnection(Cs);
            c.Open();
            Exec(c, "PRAGMA busy_timeout=5000;");
            Exec(c, "CREATE TABLE IF NOT EXISTS processed(key TEXT PRIMARY KEY, worker TEXT);" +
                    "CREATE TABLE IF NOT EXISTS effects(id INTEGER PRIMARY KEY AUTOINCREMENT, key TEXT, worker TEXT);");
            return c;
        }

        private static int Exec(SqliteConnection c, string sql, params (string, object)[] p)
        {
            using var cmd = c.CreateCommand();
            cmd.CommandText = sql;
            foreach (var (n, v) in p) cmd.Parameters.AddWithValue(n, v);
            return cmd.ExecuteNonQuery();
        }

        public static void Reset()
        {
            foreach (var f in new[] { Path, Path + "-wal", Path + "-shm", Path + "-journal" })
                if (File.Exists(f)) File.Delete(f);
        }

        public static bool AlreadyProcessed(string key)
        {
            using var c = Open();
            using var cmd = c.CreateCommand();
            cmd.CommandText = "SELECT 1 FROM processed WHERE key=$k";
            cmd.Parameters.AddWithValue("$k", key);
            return cmd.ExecuteScalar() is not null;
        }

        public static void MarkProcessedIgnore(string key, string worker)
        {
            using var c = Open();
            Exec(c, "INSERT OR IGNORE INTO processed(key,worker) VALUES($k,$w)", ("$k", key), ("$w", worker));
        }

        public static bool TryClaim(string key, string worker)
        {
            using var c = Open();
            return Exec(c, "INSERT OR IGNORE INTO processed(key,worker) VALUES($k,$w)", ("$k", key), ("$w", worker)) == 1;
        }

        public static void RecordEffect(string key, string worker)
        {
            using var c = Open();
            Exec(c, "INSERT INTO effects(key,worker) VALUES($k,$w)", ("$k", key), ("$w", worker));
        }

        public static void Report()
        {
            using var c = Open();
            using var cmd = c.CreateCommand();
            cmd.CommandText = "SELECT key, COUNT(*), group_concat(worker) FROM effects GROUP BY key ORDER BY key";
            using var r = cmd.ExecuteReader();
            var total = 0; var dup = 0;
            while (r.Read())
            {
                var n = r.GetInt32(1);
                total += n; if (n > 1) dup++;
                Console.WriteLine($"{r.GetString(0)}: efektow={n} ({r.GetString(2)}){(n > 1 ? "  <-- DUPLIKAT" : "")}");
            }
            Console.WriteLine($"razem efektow={total}, platnosci z duplikatem={dup}");
        }
    }
}
