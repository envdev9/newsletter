using System.Net.Http.Headers;
using System.Text;
using System.Text.Json;
using MassTransit;
using MassTransitTopicRouting;
using Microsoft.Extensions.DependencyInjection;
using Microsoft.Extensions.Hosting;
using Microsoft.Extensions.Logging;
using RabbitMQ.Client;

// Dane dostępowe do lokalnego brokera w Dockerze - WYŁĄCZNIE do demo (jak w wydaniach #5-#12).
const string RabbitHost = "localhost";
const string RabbitUser = "newsletter_dev";
const string RabbitPass = "newsletter_dev_local_only";
const string ManagementBaseUrl = "http://localhost:15672";

if (args.Length == 0)
{
    Console.WriteLine("Użycie: dotnet run -- <run|inspect>");
    return 1;
}

switch (args[0])
{
    case "run":
        await RunAsync();
        break;
    case "inspect":
        await InspectAsync();
        break;
    case "conflict":
        await ConflictAsync();
        break;
    default:
        Console.WriteLine($"Nieznany tryb: {args[0]}");
        return 1;
}

return 0;

// Startuje konsumentów (deklaruje topologię), publikuje 4 odczyty + 2 alerty, czeka, drukuje tabelkę.
async Task RunAsync()
{
    Console.WriteLine("=== RUN: 4 odczyty (topic) + 2 alerty (direct) ===");
    using var host = BuildHost();
    await host.StartAsync();
    var bus = host.Services.GetRequiredService<IBus>();

    (string Region, string Kind, double Value)[] readings =
    [
        ("eu", "temp", 21.5), ("eu", "humidity", 60), ("us", "temp", 30), ("asia", "pressure", 1013)
    ];
    foreach (var r in readings)
    {
        Console.WriteLine($"publish SensorReading routing key = {r.Region}.{r.Kind}");
        await bus.Publish(new SensorReading(r.Region, r.Kind, r.Value));
    }

    Console.WriteLine("publish Alert routing key = critical");
    await bus.Publish(new Alert("critical", "dysk pełny"));
    Console.WriteLine("publish Alert routing key = info   (nikt nie ma wiązania 'info')");
    await bus.Publish(new Alert("info", "backup zakończony"));

    await Task.Delay(TimeSpan.FromSeconds(2));
    await host.StopAsync();

    Console.WriteLine("--- podsumowanie: kto ile dostał ---");
    foreach (var name in new[] { "eu-all", "temp-anywhere", "audit", "naive-default", "alerts-critical" })
    {
        var n = Tally.Received.TryGetValue(name, out var bag) ? bag.Count : 0;
        Console.WriteLine($"  {name,-16} {n}");
    }
}

// Pokazuje prawdziwą topologię z REST API managementu: typy exchange'y, wiązania z kluczami, statystyki.
async Task InspectAsync()
{
    Console.WriteLine("=== INSPECT: exchange'e i wiązania na brokerze ===");
    using var http = new HttpClient { BaseAddress = new Uri(ManagementBaseUrl) };
    http.DefaultRequestHeaders.Authorization = new AuthenticationHeaderValue("Basic",
        Convert.ToBase64String(Encoding.ASCII.GetBytes($"{RabbitUser}:{RabbitPass}")));

    var exchanges = await GetAsync(http, "/api/exchanges/%2f");
    Console.WriteLine("--- exchange'e wiadomości (MassTransitTopicRouting) ---");
    foreach (var ex in exchanges.EnumerateArray().OrderBy(e => e.GetProperty("name").GetString()))
    {
        var name = ex.GetProperty("name").GetString() ?? "";
        if (!name.StartsWith("MassTransitTopicRouting:")) continue;
        var pubIn = ex.TryGetProperty("message_stats", out var s) && s.TryGetProperty("publish_in", out var pi) ? pi.GetInt32() : 0;
        var pubOut = ex.TryGetProperty("message_stats", out var s2) && s2.TryGetProperty("publish_out", out var po) ? po.GetInt32() : 0;
        Console.WriteLine($"  '{name}'  typ={ex.GetProperty("type").GetString()}  publish_in={pubIn}  publish_out={pubOut}");
    }

    var bindings = await GetAsync(http, "/api/bindings/%2f");
    Console.WriteLine("--- wiązania exchange -> (exchange|kolejka), routing_key ---");
    foreach (var b in bindings.EnumerateArray()
                 .OrderBy(b => b.GetProperty("source").GetString()).ThenBy(b => b.GetProperty("destination").GetString()))
    {
        var src = b.GetProperty("source").GetString() ?? "";
        if (!src.StartsWith("MassTransitTopicRouting:")) continue;
        Console.WriteLine($"  {src}  ->  {b.GetProperty("destination").GetString()} ({b.GetProperty("destination_type").GetString()})  routing_key='{b.GetProperty("routing_key").GetString()}'");
    }
}

// Pułapka: drugi klient "zapomina" ustawić ExchangeType (domyślnie fanout), a exchange
// 'SensorReading' już istnieje jako topic. Exchange'u nie da się zadeklarować ponownie z innym typem.
async Task ConflictAsync()
{
    Console.WriteLine("=== CONFLICT: publikacja SensorReading BEZ cfg.Publish<T>(ExchangeType.Topic) na brokerze, gdzie exchange jest topic ===");
    var builder = Host.CreateApplicationBuilder();
    builder.Logging.SetMinimumLevel(LogLevel.Critical);
    builder.Services.AddMassTransit(x =>
    {
        x.UsingRabbitMq((context, cfg) =>
        {
            cfg.Host(RabbitHost, "/", h => { h.Username(RabbitUser); h.Password(RabbitPass); });
        });
    });
    using var host = builder.Build();
    try
    {
        await host.StartAsync();
        var bus = host.Services.GetRequiredService<IBus>();
        using var cts = new CancellationTokenSource(TimeSpan.FromSeconds(10));
        await bus.Publish(new SensorReading("eu", "temp", 1), cts.Token);
        Console.WriteLine("publish zakończony bez wyjątku");
    }
    catch (Exception ex)
    {
        Console.WriteLine($"WYJĄTEK {ex.GetType().Name}: {ex.Message}");
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

IHost BuildHost()
{
    var builder = Host.CreateApplicationBuilder();
    builder.Logging.SetMinimumLevel(LogLevel.Warning);
    builder.Logging.AddFilter("MassTransit", LogLevel.Critical);

    builder.Services.AddMassTransit(x =>
    {
        x.AddConsumer<EuConsumer>();
        x.AddConsumer<TempConsumer>();
        x.AddConsumer<AuditConsumer>();
        x.AddConsumer<NaiveConsumer>();
        x.AddConsumer<CriticalAlertConsumer>();

        x.UsingRabbitMq((context, cfg) =>
        {
            cfg.Host(RabbitHost, "/", h =>
            {
                h.Username(RabbitUser);
                h.Password(RabbitPass);
            });

            // Strona PUBLIKUJĄCA: exchange typu topic + klucz routingu wyliczany z wiadomości.
            cfg.Publish<SensorReading>(p => p.ExchangeType = ExchangeType.Topic);
            cfg.Send<SensorReading>(s => s.UseRoutingKeyFormatter(ctx => $"{ctx.Message.Region}.{ctx.Message.Kind}"));

            // To samo dla direct: klucz = poziom ważności.
            cfg.Publish<Alert>(p => p.ExchangeType = ExchangeType.Direct);
            cfg.Send<Alert>(s => s.UseRoutingKeyFormatter(ctx => ctx.Message.Severity));

            // Strona KONSUMUJĄCA: wyłączamy domyślną topologię (wiązanie bez klucza)
            // i wiążemy kolejkę ręcznie z własnym wzorcem.
            cfg.ReceiveEndpoint("sensors-eu", e =>
            {
                e.ConfigureConsumeTopology = false;
                e.Bind<SensorReading>(b => { b.ExchangeType = ExchangeType.Topic; b.RoutingKey = "eu.#"; });
                e.ConfigureConsumer<EuConsumer>(context);
            });
            cfg.ReceiveEndpoint("sensors-temp", e =>
            {
                e.ConfigureConsumeTopology = false;
                e.Bind<SensorReading>(b => { b.ExchangeType = ExchangeType.Topic; b.RoutingKey = "*.temp"; });
                e.ConfigureConsumer<TempConsumer>(context);
            });
            cfg.ReceiveEndpoint("sensors-audit", e =>
            {
                e.ConfigureConsumeTopology = false;
                e.Bind<SensorReading>(b => { b.ExchangeType = ExchangeType.Topic; b.RoutingKey = "#"; });
                e.ConfigureConsumer<AuditConsumer>(context);
            });

            // Konsument naiwny: domyślna topologia (ConfigureConsumeTopology = true) - bez własnego klucza.
            cfg.ReceiveEndpoint("sensors-naive", e => e.ConfigureConsumer<NaiveConsumer>(context));

            cfg.ReceiveEndpoint("alerts-critical", e =>
            {
                e.ConfigureConsumeTopology = false;
                e.Bind<Alert>(b => { b.ExchangeType = ExchangeType.Direct; b.RoutingKey = "critical"; });
                e.ConfigureConsumer<CriticalAlertConsumer>(context);
            });
        });
    });

    return builder.Build();
}
