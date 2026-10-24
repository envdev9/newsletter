using System.Net.Http.Headers;
using System.Net.Http.Json;
using System.Text;
using System.Text.Json;
using MassTransit;
using MassTransitRetryErrorDemo;
using Microsoft.Extensions.DependencyInjection;
using Microsoft.Extensions.Hosting;
using Microsoft.Extensions.Logging;

// Dane dostępowe do brokera uruchomionego lokalnie w Dockerze na potrzeby TEGO wydania (patrz
// wydanie #5 - te same zasady: nie "guest", jednorazowy login deweloperski, nie produkcyjny sekret).
const string RabbitHost = "localhost";
const string RabbitUser = "newsletter_dev";
const string RabbitPass = "newsletter_dev_local_only";
const string ManagementBaseUrl = "http://localhost:15672";

if (args.Length == 0)
{
    Console.WriteLine("Użycie: dotnet run -- <topology|inspect|run flaky|run fail|run skip|run orphan|peek <kolejka>>");
    return 1;
}

switch (args[0])
{
    case "topology":
        await RunTopologyAsync();
        break;
    case "inspect":
        await RunInspectAsync();
        break;
    case "run":
        await RunScenarioAsync(args.Length > 1 ? args[1] : "flaky");
        break;
    case "peek":
        await PeekQueueAsync(args.Length > 1 ? args[1] : throw new ArgumentException("podaj nazwę kolejki"));
        break;
    default:
        Console.WriteLine($"Nieznany tryb: {args[0]}");
        return 1;
}

return 0;

// --- tryb 1: wystaw wszystkich 3 konsumentów, żeby MassTransit zadeklarował na RabbitMQ ich
//     kolejki główne. UWAGA (zweryfikowane empirycznie, nie przypuszczenie): kolejki _error/_skipped
//     NIE są deklarowane z góry - MassTransit tworzy je LENIWIE, dopiero gdy faktycznie potrzebuje
//     tam coś odłożyć. `inspect` zaraz po `topology` pokazuje TYLKO 3 kolejki główne. ---
async Task RunTopologyAsync()
{
    Console.WriteLine("=== TOPOLOGY: startuję hosta - MassTransit deklaruje kolejki GŁÓWNE na RabbitMQ (_error/_skipped powstają leniwie) ===");
    using var host = BuildHost();
    await host.StartAsync();
    Log.Line("bus wystartował, topologia (3 konsumentów) zadeklarowana na brokerze");
    await Task.Delay(500);
    await host.StopAsync();
    Log.Line("host zatrzymany - kolejki NA BROKERZE zostają, bo są trwałe (durable)");
}

// --- tryb 2: wyślij jedną wiadomość do wybranego scenariusza i obserwuj zachowanie retry. Proces
//     kończy się (host.StopAsync) PO scenariuszu - symulujemy zamknięcie klienta, żeby w kolejnym,
//     NIEZALEŻNYM procesie (`inspect`/`peek`) sprawdzić, co broker naprawdę zapamiętał. ---
async Task RunScenarioAsync(string scenario)
{
    using var host = BuildHost();
    await host.StartAsync();
    var bus = host.Services.GetRequiredService<IBus>();
    var id = Guid.NewGuid().ToString("N")[..8];

    switch (scenario)
    {
        case "flaky":
            Console.WriteLine($"=== RUN FLAKY: {id} zawiedzie 2 razy, uda się przy 3. próbie (UseMessageRetry.Interval) ===");
            await bus.Publish(new FlakyOperation(id, FailUntilAttempt: 3));
            await Task.Delay(TimeSpan.FromSeconds(2));
            break;

        case "fail":
            Console.WriteLine($"=== RUN FAIL: {id} zawiedzie TRWALE - po 2 retry MassTransit przenosi wiadomość do kolejki _error ===");
            await bus.Publish(new PermanentFailure(id));
            await Task.Delay(TimeSpan.FromSeconds(2));
            break;

        case "skip":
            Console.WriteLine($"=== RUN SKIP: {id} to znane-złe dane (Ignore<KnownBadDataException>) - BEZ retry, ale wciąż do _error ===");
            await bus.Publish(new KnownBadData(id));
            await Task.Delay(TimeSpan.FromSeconds(1));
            break;

        case "orphan":
            Console.WriteLine($"=== RUN ORPHAN: {id} - wysyłam NobodyConsumesThis WPROST na kolejkę 'flaky', która go nie konsumuje -> prawdziwa kolejka _skipped na RabbitMQ ===");
            var flakyQueue = await bus.GetSendEndpoint(new Uri("queue:flaky"));
            await flakyQueue.Send(new NobodyConsumesThis(id));
            await Task.Delay(TimeSpan.FromSeconds(1));
            break;

        default:
            Console.WriteLine($"Nieznany scenariusz: {scenario}");
            break;
    }

    await host.StopAsync();
    Log.Line("host ZATRZYMANY (proces się kończy) - żaden konsument już nie jest podłączony do brokera");
}

// --- tryb 3: inspekcja realnej topologii + liczników kolejek przez REST API management plugin
//     (jak w wydaniu #5/#7) - odpalany jako NOWY, niezależny proces, często PO tym, jak proces z
//     `run` już się zakończył. To jest clou dzisiejszego wydania: broker pamięta, proces nie musi. ---
async Task RunInspectAsync()
{
    Console.WriteLine("=== INSPECT: co broker naprawdę ma w kolejkach _error/_skipped - BEZ ŻADNEGO podłączonego konsumenta ===");
    using var http = BuildManagementClient();

    Console.WriteLine("--- kolejki (główne + _error/_skipped) ---");
    var queues = await GetJsonAsync(http, "/api/queues/%2f");
    foreach (var q in queues!.EnumerateArray().OrderBy(q => q.GetProperty("name").GetString()))
    {
        var name = q.GetProperty("name").GetString();
        var durable = q.GetProperty("durable").GetBoolean();
        var ready = q.TryGetProperty("messages_ready", out var r) ? r.GetInt32() : 0;
        var unacked = q.TryGetProperty("messages_unacknowledged", out var u) ? u.GetInt32() : 0;
        var consumers = q.TryGetProperty("consumers", out var c) ? c.GetInt32() : 0;
        Console.WriteLine($"  kolejka '{name}'  durable={durable}  messages_ready={ready}  unacked={unacked}  consumers={consumers}");
    }

    Console.WriteLine("--- exchange'y związane z błędami/retry (Fault, bez wbudowanych amq.*) ---");
    var exchanges = await GetJsonAsync(http, "/api/exchanges/%2f");
    foreach (var ex in exchanges!.EnumerateArray())
    {
        var name = ex.GetProperty("name").GetString() ?? "";
        if (name.StartsWith("amq.") || name.Length == 0) continue;
        if (!name.Contains("Fault", StringComparison.Ordinal)) continue;
        Console.WriteLine($"  exchange '{name}'  typ={ex.GetProperty("type").GetString()}  durable={ex.GetProperty("durable").GetBoolean()}");
    }
}

// --- tryb 4: zajrzyj do kolejki przez REST API (POST /api/queues/.../get, ackmode=ack_requeue_true)
//     - czyta WIADOMOŚĆ, ale zostawia ją w kolejce (requeue). Dowód, że to NAPRAWDĘ ta sama
//     wiadomość, nie tylko licznik - łącznie z jej treścią i nagłówkami MassTransit. ---
async Task PeekQueueAsync(string queueName)
{
    Console.WriteLine($"=== PEEK: zaglądam do kolejki '{queueName}' przez REST API (requeue=true, nic nie usuwam) ===");
    using var http = BuildManagementClient();

    var body = JsonSerializer.Serialize(new { count = 5, ackmode = "ack_requeue_true", encoding = "auto" });
    var response = await http.PostAsync($"/api/queues/%2f/{queueName}/get",
        new StringContent(body, Encoding.UTF8, "application/json"));
    response.EnsureSuccessStatusCode();
    var json = await response.Content.ReadFromJsonAsync<JsonElement>();

    var count = 0;
    foreach (var msg in json.EnumerateArray())
    {
        count++;
        var payload = msg.GetProperty("payload").GetString();
        Console.WriteLine($"  wiadomość #{count} (payload, pierwsze 200 znaków): {payload?[..Math.Min(200, payload.Length)]}");
        if (msg.TryGetProperty("properties", out var props) && props.TryGetProperty("headers", out var headers))
        {
            foreach (var h in headers.EnumerateObject())
            {
                if (h.Name.StartsWith("MT-", StringComparison.Ordinal))
                    Console.WriteLine($"    header {h.Name} = {h.Value}");
            }
        }
    }
    if (count == 0) Console.WriteLine("  (kolejka pusta)");
}

static async Task<JsonElement> GetJsonAsync(HttpClient http, string path)
{
    var response = await http.GetAsync(path);
    response.EnsureSuccessStatusCode();
    var stream = await response.Content.ReadAsStreamAsync();
    var doc = await JsonDocument.ParseAsync(stream);
    return doc.RootElement.Clone();
}

HttpClient BuildManagementClient()
{
    var http = new HttpClient { BaseAddress = new Uri(ManagementBaseUrl) };
    var basicAuth = Convert.ToBase64String(Encoding.ASCII.GetBytes($"{RabbitUser}:{RabbitPass}"));
    http.DefaultRequestHeaders.Authorization = new AuthenticationHeaderValue("Basic", basicAuth);
    return http;
}

IHost BuildHost()
{
    var hostBuilder = Host.CreateApplicationBuilder();
    hostBuilder.Logging.SetMinimumLevel(LogLevel.Warning);
    hostBuilder.Logging.AddFilter("MassTransit", LogLevel.Critical);

    hostBuilder.Services.AddMassTransit(x =>
    {
        x.SetEndpointNameFormatter(KebabCaseEndpointNameFormatter.Instance);

        x.AddConsumer<FlakyConsumer, FlakyConsumerDefinition>();
        x.AddConsumer<AlwaysFailingConsumer, AlwaysFailingConsumerDefinition>();
        x.AddConsumer<SkippableConsumer, SkippableConsumerDefinition>();

        x.UsingRabbitMq((context, cfg) =>
        {
            cfg.Host(RabbitHost, "/", h =>
            {
                h.Username(RabbitUser);
                h.Password(RabbitPass);
            });

            cfg.ConfigureEndpoints(context);
        });
    });

    return hostBuilder.Build();
}
