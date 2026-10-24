using System.Net.Http.Headers;
using System.Text;
using System.Text.Json;
using MassTransit;
using MassTransitRabbitMqDemo;
using Microsoft.Extensions.DependencyInjection;
using Microsoft.Extensions.Hosting;
using Microsoft.Extensions.Logging;

// Dane dostępowe do brokera uruchomionego lokalnie w Dockerze na potrzeby TEGO wydania.
// Użytkownik NIE jest domyślnym "guest" (ten jest ograniczony do połączeń z prawdziwego
// loopbacku, a Docker port-forwarding tego nie spełnia) - to jednorazowy, deweloperski
// login utworzony na czas demo, kontener i tak zostaje usunięty po zakończeniu pracy.
const string RabbitHost = "localhost";
const string RabbitUser = "newsletter_dev";
const string RabbitPass = "newsletter_dev_local_only";
const string ManagementBaseUrl = "http://localhost:15672";

if (args.Length == 0)
{
    Console.WriteLine("Użycie: dotnet run -- <topology|publish N|consume SEKUNDY|inspect>");
    return 1;
}

switch (args[0])
{
    case "topology":
        await RunTopologyAsync();
        break;
    case "publish":
        await RunPublishAsync(args.Length > 1 ? int.Parse(args[1]) : 3);
        break;
    case "consume":
        await RunConsumeAsync(args.Length > 1 ? int.Parse(args[1]) : 3);
        break;
    case "inspect":
        await RunInspectAsync();
        break;
    default:
        Console.WriteLine($"Nieznany tryb: {args[0]}");
        return 1;
}

return 0;

// --- tryb 1: wystaw konsumenta, żeby MassTransit utworzył exchange + kolejkę + binding, potem zejdź ---
async Task RunTopologyAsync()
{
    Console.WriteLine("=== TOPOLOGY: startuję konsumenta, MassTransit deklaruje exchange/kolejkę/binding na RabbitMQ ===");
    using var host = BuildHost(withConsumer: true);
    await host.StartAsync();
    Log.Line("bus wystartował, topologia zadeklarowana na brokerze");
    await Task.Delay(500);
    await host.StopAsync();
    Log.Line("host zatrzymany (proces zaraz się kończy) - kolejka na brokerze ZOSTAJE, bo jest trwała");
}

// --- tryb 2: proces BEZ konsumenta - tylko publikuje N wiadomości i kończy działanie ---
async Task RunPublishAsync(int count)
{
    Console.WriteLine($"=== PUBLISH: proces bez konsumenta publikuje {count} wiadomości i kończy się ===");
    using var host = BuildHost(withConsumer: false);
    await host.StartAsync();
    var publishEndpoint = host.Services.GetRequiredService<IPublishEndpoint>();

    for (var i = 0; i < count; i++)
    {
        var order = new OrderSubmitted(Guid.NewGuid(), i % 2 == 0 ? "ABC-1" : "XYZ-9", i + 1);
        await publishEndpoint.Publish(order);
        Log.Line($"opublikowano zamówienie {order.OrderId:N} ({order.Sku} x{order.Qty})");
    }

    await host.StopAsync();
    Log.Line("proces publikujący KOŃCZY SIĘ (Environment.Exit) - żaden konsument w tym demie jeszcze nie działał");
}

// --- tryb 3: nowy proces ze świeżym bus/konsumentem - odbiera to, co czekało na brokerze ---
async Task RunConsumeAsync(int seconds)
{
    Console.WriteLine($"=== CONSUME: nowy proces startuje konsumenta i przez {seconds}s odbiera zaległe wiadomości ===");
    using var host = BuildHost(withConsumer: true);
    await host.StartAsync();
    Log.Line("bus wystartował - zaraz zacznie odbierać to, co leżało w kolejce, zanim ten proces w ogóle istniał");
    await Task.Delay(TimeSpan.FromSeconds(seconds));
    await host.StopAsync();
    Log.Line($"koniec okna odbioru - ten proces odebrał łącznie {OrderConsumer.Received} wiadomości");
}

// --- tryb 4: inspekcja realnej topologii przez REST API management plugin ---
async Task RunInspectAsync()
{
    Console.WriteLine("=== INSPECT: co MassTransit naprawdę utworzył na brokerze (REST API management plugin) ===");
    using var http = new HttpClient { BaseAddress = new Uri(ManagementBaseUrl) };
    var basicAuth = Convert.ToBase64String(Encoding.ASCII.GetBytes($"{RabbitUser}:{RabbitPass}"));
    http.DefaultRequestHeaders.Authorization = new AuthenticationHeaderValue("Basic", basicAuth);

    Console.WriteLine("--- exchange'y (bez wbudowanych amq.*) ---");
    var exchanges = await GetJsonAsync(http, "/api/exchanges/%2f");
    foreach (var ex in exchanges!.EnumerateArray())
    {
        var name = ex.GetProperty("name").GetString() ?? "";
        if (name.StartsWith("amq.") || name.Length == 0) continue;
        Console.WriteLine($"  exchange '{name}'  typ={ex.GetProperty("type").GetString()}  durable={ex.GetProperty("durable").GetBoolean()}");
    }

    Console.WriteLine("--- kolejki ---");
    var queues = await GetJsonAsync(http, "/api/queues/%2f");
    foreach (var q in queues!.EnumerateArray())
    {
        var name = q.GetProperty("name").GetString();
        var durable = q.GetProperty("durable").GetBoolean();
        var ready = q.TryGetProperty("messages_ready", out var r) ? r.GetInt32() : 0;
        var unacked = q.TryGetProperty("messages_unacknowledged", out var u) ? u.GetInt32() : 0;
        var consumers = q.TryGetProperty("consumers", out var c) ? c.GetInt32() : 0;
        Console.WriteLine($"  kolejka '{name}'  durable={durable}  messages_ready={ready}  unacked={unacked}  consumers={consumers}");
    }

    Console.WriteLine("--- bindingi (exchange -> kolejka), bez amq.* ---");
    var bindings = await GetJsonAsync(http, "/api/bindings/%2f");
    foreach (var b in bindings!.EnumerateArray())
    {
        var source = b.GetProperty("source").GetString() ?? "";
        if (source.Length == 0 || source.StartsWith("amq.")) continue;
        var destination = b.GetProperty("destination").GetString();
        var destinationType = b.GetProperty("destination_type").GetString();
        var routingKey = b.GetProperty("routing_key").GetString();
        Console.WriteLine($"  '{source}' --[routing_key='{routingKey}']--> {destinationType} '{destination}'");
    }
}

static async Task<JsonElement> GetJsonAsync(HttpClient http, string path)
{
    var response = await http.GetAsync(path);
    response.EnsureSuccessStatusCode();
    var stream = await response.Content.ReadAsStreamAsync();
    var doc = await JsonDocument.ParseAsync(stream);
    return doc.RootElement.Clone();
}

IHost BuildHost(bool withConsumer)
{
    var builder = Host.CreateApplicationBuilder();
    builder.Logging.SetMinimumLevel(LogLevel.Warning);
    builder.Logging.AddFilter("MassTransit", LogLevel.Critical);

    builder.Services.AddMassTransit(x =>
    {
        if (withConsumer)
            x.AddConsumer<OrderConsumer>();

        x.UsingRabbitMq((context, cfg) =>
        {
            cfg.Host(RabbitHost, "/", h =>
            {
                h.Username(RabbitUser);
                h.Password(RabbitPass);
            });

            // ConfigureEndpoints tworzy kolejkę TYLKO jeśli w tym procesie jest zarejestrowany
            // jakiś konsument - proces "publish" nie ma konsumenta, więc nie zakłada żadnej kolejki.
            if (withConsumer)
                cfg.ConfigureEndpoints(context);
        });
    });

    return builder.Build();
}
