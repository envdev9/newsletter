using System.Net.Http.Headers;
using System.Text;
using System.Text.Json;
using MassTransit;
using MassTransit.RabbitMqTransport;
using MassTransitUnrouted;
using Microsoft.Extensions.DependencyInjection;
using Microsoft.Extensions.Hosting;
using Microsoft.Extensions.Logging;
using RabbitMQ.Client;

// Dane dostępowe do lokalnego brokera w Dockerze - WYŁĄCZNIE do demo (jak w wydaniach #5-#13).
const string RabbitHost = "localhost";
const string RabbitUser = "newsletter_dev";
const string RabbitPass = "newsletter_dev_local_only";
const string ManagementBaseUrl = "http://localhost:15672";
const string AlternateExchange = "unrouted-ae";

if (args.Length == 0)
{
    Console.WriteLine("Użycie: dotnet run -- <run|mandatory|mandatory-ae|inspect|ae-conflict>");
    return 1;
}

switch (args[0])
{
    case "run": await RunAsync(); break;
    case "mandatory": await MandatoryAsync(); break;
    case "mandatory-ae": await MandatoryAeAsync(); break;
    case "inspect": await InspectAsync(); break;
    case "ae-conflict": await AeConflictAsync(); break;
    default:
        Console.WriteLine($"Nieznany tryb: {args[0]}");
        return 1;
}

return 0;

// Dwa typy, ten sam scenariusz: 1 wiadomość trafia w wiązanie 'critical', 1 w nic ('info').
// Alert nie ma alternate-exchange (znika), Notice ma (ląduje w koszu).
async Task RunAsync()
{
    Console.WriteLine("=== RUN: Alert (bez AE) i Notice (z alternate-exchange), po 'critical' i 'info' ===");
    using var host = BuildHost();
    await host.StartAsync();
    var bus = host.Services.GetRequiredService<IBus>();

    await bus.Publish(new Alert("critical", "dysk pelny"));
    await bus.Publish(new Alert("info", "backup zakonczony"));
    await bus.Publish(new Notice("critical", "certyfikat wygasa"));
    await bus.Publish(new Notice("info", "wdrozenie zakonczone"));

    await Task.Delay(TimeSpan.FromSeconds(2));
    await host.StopAsync();

    Console.WriteLine("--- podsumowanie ---");
    foreach (var name in new[] { "alerts-critical", "notices-critical", "unrouted-sink" })
        Console.WriteLine($"  {name,-17} {(Tally.Received.TryGetValue(name, out var bag) ? bag.Count : 0)}");
}

// Flaga mandatory na wiadomości bez trasy: co zgłasza MassTransit 8.5.10?
async Task MandatoryAsync()
{
    Console.WriteLine("=== MANDATORY: Alert 'info' (bez wiązania), mandatory=true vs false ===");
    using var host = BuildHost(withAlternateExchange: false);
    await host.StartAsync();
    var bus = host.Services.GetRequiredService<IBus>();

    foreach (var mandatory in new[] { false, true })
    {
        try
        {
            using var cts = new CancellationTokenSource(TimeSpan.FromSeconds(10));
            var found = false;
            var sw = System.Diagnostics.Stopwatch.StartNew();
            await bus.Publish(new Alert("info", $"mandatory={mandatory}"), ctx =>
            {
                if (ctx.TryGetPayload<RabbitMqSendContext>(out var rmq))
                {
                    found = true;
                    rmq.Mandatory = mandatory;
                }
            }, cts.Token);
            Console.WriteLine($"  mandatory={mandatory,-5} payload RabbitMqSendContext={found}  Publish zakonczony BEZ wyjatku po {sw.ElapsedMilliseconds} ms");
        }
        catch (Exception ex)
        {
            Console.WriteLine($"  mandatory={mandatory,-5} WYJATEK {ex.GetType().Name}: {ex.Message}");
            for (var inner = ex.InnerException; inner != null; inner = inner.InnerException)
                Console.WriteLine($"    inner {inner.GetType().Name}: {inner.Message}");
        }
    }

    await Task.Delay(TimeSpan.FromSeconds(1));
    await host.StopAsync();
}

// mandatory=true na wiadomosci, ktora NIE ma trasy, ale exchange ma alternate-exchange: czy broker zwroci ja nadawcy?
async Task MandatoryAeAsync()
{
    Console.WriteLine("=== MANDATORY-AE: Notice 'info' (brak wiazania, ale exchange ma AE), mandatory=true ===");
    using var host = BuildHost();
    await host.StartAsync();
    var bus = host.Services.GetRequiredService<IBus>();
    try
    {
        await bus.Publish(new Notice("info", "mandatory + AE"), ctx =>
        {
            if (ctx.TryGetPayload<RabbitMqSendContext>(out var rmq)) rmq.Mandatory = true;
        });
        Console.WriteLine("  Publish zakonczony BEZ wyjatku");
    }
    catch (Exception ex)
    {
        Console.WriteLine($"  WYJATEK {ex.GetType().Name}: {ex.Message}");
    }
    await Task.Delay(TimeSpan.FromSeconds(1.5));
    await host.StopAsync();
}

// Pokazuje argumenty exchange'y (alternate-exchange), wiązania i statystyki z REST API managementu.
async Task InspectAsync()
{
    Console.WriteLine("=== INSPECT ===");
    using var http = new HttpClient { BaseAddress = new Uri(ManagementBaseUrl) };
    http.DefaultRequestHeaders.Authorization = new AuthenticationHeaderValue("Basic",
        Convert.ToBase64String(Encoding.ASCII.GetBytes($"{RabbitUser}:{RabbitPass}")));

    var exchanges = await GetAsync(http, "/api/exchanges/%2f");
    Console.WriteLine("--- exchange'e (typ, argumenty, publish_in/out) ---");
    foreach (var ex in exchanges.EnumerateArray().OrderBy(e => e.GetProperty("name").GetString()))
    {
        var name = ex.GetProperty("name").GetString() ?? "";
        if (!name.StartsWith("MassTransitUnrouted:") && name != AlternateExchange) continue;
        var stats = ex.TryGetProperty("message_stats", out var s) ? s : default;
        var pubIn = stats.ValueKind == JsonValueKind.Object && stats.TryGetProperty("publish_in", out var pi) ? pi.GetInt32() : 0;
        var pubOut = stats.ValueKind == JsonValueKind.Object && stats.TryGetProperty("publish_out", out var po) ? po.GetInt32() : 0;
        Console.WriteLine($"  '{name}'  typ={ex.GetProperty("type").GetString()}  args={ex.GetProperty("arguments").GetRawText()}  publish_in={pubIn}  publish_out={pubOut}");
    }

    var bindings = await GetAsync(http, "/api/bindings/%2f");
    Console.WriteLine("--- wiazania ---");
    foreach (var b in bindings.EnumerateArray()
                 .OrderBy(b => b.GetProperty("source").GetString()).ThenBy(b => b.GetProperty("destination").GetString()))
    {
        var src = b.GetProperty("source").GetString() ?? "";
        if (!src.StartsWith("MassTransitUnrouted:") && src != AlternateExchange) continue;
        Console.WriteLine($"  {src}  ->  {b.GetProperty("destination").GetString()} ({b.GetProperty("destination_type").GetString()})  routing_key='{b.GetProperty("routing_key").GetString()}'");
    }
}

// Pułapka: exchange 'Notice' istnieje z argumentem alternate-exchange, a drugi klient deklaruje go bez argumentu.
async Task AeConflictAsync()
{
    Console.WriteLine("=== AE-CONFLICT: publikacja Notice BEZ argumentu alternate-exchange na istniejacym exchange z AE ===");
    var builder = Host.CreateApplicationBuilder();
    builder.Logging.SetMinimumLevel(LogLevel.Critical);
    builder.Services.AddMassTransit(x =>
    {
        x.UsingRabbitMq((context, cfg) =>
        {
            cfg.Host(RabbitHost, "/", h => { h.Username(RabbitUser); h.Password(RabbitPass); });
            cfg.Publish<Notice>(p => p.ExchangeType = ExchangeType.Direct);
            cfg.Send<Notice>(s => s.UseRoutingKeyFormatter(ctx => ctx.Message.Severity));
        });
    });
    using var host = builder.Build();
    try
    {
        await host.StartAsync();
        var bus = host.Services.GetRequiredService<IBus>();
        using var cts = new CancellationTokenSource(TimeSpan.FromSeconds(10));
        await bus.Publish(new Notice("critical", "x"), cts.Token);
        Console.WriteLine("publish zakonczony bez wyjatku");
    }
    catch (Exception ex)
    {
        Console.WriteLine($"WYJATEK {ex.GetType().Name}: {ex.Message}");
        for (var inner = ex.InnerException; inner != null; inner = inner.InnerException)
            Console.WriteLine($"  inner {inner.GetType().Name}: {inner.Message}");
    }
    finally
    {
        try { await host.StopAsync(); } catch { /* demo */ }
    }
}

static async Task<JsonElement> GetAsync(HttpClient http, string path)
{
    var response = await http.GetAsync(path);
    response.EnsureSuccessStatusCode();
    using var doc = await JsonDocument.ParseAsync(await response.Content.ReadAsStreamAsync());
    return doc.RootElement.Clone();
}

IHost BuildHost(bool withAlternateExchange = true)
{
    var builder = Host.CreateApplicationBuilder();
    builder.Logging.SetMinimumLevel(LogLevel.Warning);
    builder.Logging.AddFilter("MassTransit", LogLevel.Critical);

    builder.Services.AddMassTransit(x =>
    {
        x.AddConsumer<CriticalAlertConsumer>();
        x.AddConsumer<CriticalNoticeConsumer>();
        x.AddConsumer<UnroutedNoticeConsumer>();

        x.UsingRabbitMq((context, cfg) =>
        {
            cfg.Host(RabbitHost, "/", h => { h.Username(RabbitUser); h.Password(RabbitPass); });

            cfg.Publish<Alert>(p => p.ExchangeType = ExchangeType.Direct);
            cfg.Send<Alert>(s => s.UseRoutingKeyFormatter(ctx => ctx.Message.Severity));

            cfg.Publish<Notice>(p =>
            {
                p.ExchangeType = ExchangeType.Direct;
                if (withAlternateExchange)
                    p.SetExchangeArgument("alternate-exchange", AlternateExchange);
            });
            cfg.Send<Notice>(s => s.UseRoutingKeyFormatter(ctx => ctx.Message.Severity));

            cfg.ReceiveEndpoint("alerts-critical", e =>
            {
                e.ConfigureConsumeTopology = false;
                e.Bind<Alert>(b => { b.ExchangeType = ExchangeType.Direct; b.RoutingKey = "critical"; });
                e.ConfigureConsumer<CriticalAlertConsumer>(context);
            });

            if (withAlternateExchange)
            {
                cfg.ReceiveEndpoint("notices-critical", e =>
                {
                    e.ConfigureConsumeTopology = false;
                    e.Bind<Notice>(b =>
                    {
                        b.ExchangeType = ExchangeType.Direct;
                        b.RoutingKey = "critical";
                        b.SetExchangeArgument("alternate-exchange", AlternateExchange);
                    });
                    e.ConfigureConsumer<CriticalNoticeConsumer>(context);
                });

                // "Kosz": exchange fanout deklarowany przez Bind + kolejka. Wlasnie na niego wskazuje alternate-exchange.
                cfg.ReceiveEndpoint("unrouted-sink", e =>
                {
                    e.ConfigureConsumeTopology = false;
                    e.Bind(AlternateExchange, b => b.ExchangeType = ExchangeType.Fanout);
                    e.ConfigureConsumer<UnroutedNoticeConsumer>(context);
                });
            }
        });
    });

    return builder.Build();
}
