using System.Net.Http.Headers;
using System.Text;
using System.Text.Json;
using MassTransit;
using MassTransit.Courier.Contracts;
using MassTransitRoutingSlipDemo;
using Microsoft.Extensions.DependencyInjection;
using Microsoft.Extensions.Hosting;
using Microsoft.Extensions.Logging;

// Dane dostępowe do brokera uruchomionego lokalnie w Dockerze na potrzeby TEGO wydania (patrz
// wydanie #5 - te same zasady: nie "guest", jednorazowy login deweloperski).
const string RabbitHost = "localhost";
const string RabbitUser = "newsletter_dev";
const string RabbitPass = "newsletter_dev_local_only";
const string ManagementBaseUrl = "http://localhost:15672";

if (args.Length == 0)
{
    Console.WriteLine("Użycie: dotnet run -- <topology|inspect|run ok|run fail>");
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
        await RunScenarioAsync(args.Length > 1 ? args[1] : "ok");
        break;
    default:
        Console.WriteLine($"Nieznany tryb: {args[0]}");
        return 1;
}

return 0;

// --- tryb 1: wystaw wszystkie aktywności + konsumenta zdarzeń, żeby MassTransit zadeklarował
//     kolejki execute/compensate na RabbitMQ, potem zejdź ---
async Task RunTopologyAsync()
{
    Console.WriteLine("=== TOPOLOGY: startuję hosta z aktywnościami Couriera - MassTransit deklaruje kolejki execute/compensate na RabbitMQ ===");
    using var host = BuildHost();
    await host.StartAsync();
    Log.Line("bus wystartował, topologia (2 aktywności + konsument zdarzeń) zadeklarowana na brokerze");
    await Task.Delay(500);
    await host.StopAsync();
    Log.Line("host zatrzymany (proces zaraz się kończy) - kolejki na brokerze ZOSTAJĄ, bo są trwałe");
}

// --- tryb 2: zbuduj i wykonaj routing slip: ReserveInventory -> ChargePayment.
//     scenario == "ok"   -> kwota w limicie, obie aktywności się kończą, RoutingSlipCompleted
//     scenario == "fail" -> kwota nad limitem, ChargePayment rzuca wyjątek, MassTransit automatycznie
//                            KOMPENSUJE ReserveInventory (cofa rezerwację), potem RoutingSlipFaulted ---
async Task RunScenarioAsync(string scenario)
{
    var amount = scenario == "fail" ? 1500m : 250m;
    Console.WriteLine($"=== RUN {scenario.ToUpperInvariant()}: routing slip zamówienia, kwota płatności = {amount:0.00} zł (limit karty = 1000 zł) ===");

    using var host = BuildHost();
    await host.StartAsync();

    var bus = host.Services.GetRequiredService<IBus>();
    var formatter = host.Services.GetRequiredService<IEndpointNameFormatter>();

    // Adresów kolejek execute NIE zgadujemy - pytamy o nie ten sam formatter, którego użyje
    // ConfigureEndpoints przy tworzeniu topologii. To ta sama pułapka co w wydaniu #5 (domyślna
    // nazwa kolejki bywa inna, niż się wydaje) - tu unikamy jej programowo.
    var reserveExecuteAddress = new Uri($"queue:{formatter.ExecuteActivity<ReserveInventoryActivity, ReserveInventoryArguments>()}");
    var chargeExecuteAddress = new Uri($"queue:{formatter.ExecuteActivity<ChargePaymentActivity, ChargePaymentArguments>()}");
    var eventsConsumerAddress = new Uri($"queue:{formatter.Consumer<RoutingSlipEventsConsumer>()}");
    Log.Line($"adres execute ReserveInventory = {reserveExecuteAddress}");
    Log.Line($"adres execute ChargePayment    = {chargeExecuteAddress}");
    Log.Line($"adres konsumenta zdarzeń       = {eventsConsumerAddress}");

    var orderId = Guid.NewGuid().ToString("N")[..8];
    var trackingNumber = Guid.NewGuid();

    var builder = new RoutingSlipBuilder(trackingNumber);
    // Zdarzenia końcowe (Completed/Faulted) wysyłane WPROST do kolejki naszego konsumenta zdarzeń -
    // to zwykły punkt-punkt Send po adresie (jak w wydaniu #4), nie fanout Publish.
    builder.AddSubscription(eventsConsumerAddress, RoutingSlipEvents.Completed | RoutingSlipEvents.Faulted);
    builder.AddActivity("ReserveInventory", reserveExecuteAddress, new { OrderId = orderId, Sku = "ABC-1", Qty = 2 });
    builder.AddActivity("ChargePayment", chargeExecuteAddress, new { OrderId = orderId, Amount = amount });
    var routingSlip = builder.Build();

    Log.Line($"wysyłam routing slip {trackingNumber} dla zamówienia {orderId} (itinerary: ReserveInventory -> ChargePayment)");
    await bus.Execute(routingSlip);

    await Task.Delay(TimeSpan.FromSeconds(3));
    await host.StopAsync();
    Log.Line("koniec okna obserwacji");
}

// --- tryb 3: inspekcja realnej topologii przez REST API management plugin (jak w wydaniu #5) ---
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

IHost BuildHost()
{
    var hostBuilder = Host.CreateApplicationBuilder();
    hostBuilder.Logging.SetMinimumLevel(LogLevel.Warning);
    hostBuilder.Logging.AddFilter("MassTransit", LogLevel.Critical);

    hostBuilder.Services.AddMassTransit(x =>
    {
        x.SetEndpointNameFormatter(KebabCaseEndpointNameFormatter.Instance);

        x.AddConsumer<RoutingSlipEventsConsumer>();
        // Aktywność Z kompensacją: 3 parametry generyczne (aktywność, argumenty, log).
        x.AddActivity<ReserveInventoryActivity, ReserveInventoryArguments, ReserveInventoryLog>();
        // Aktywność BEZ kompensacji: rejestrowana osobną metodą, 2 parametry generyczne.
        x.AddExecuteActivity<ChargePaymentActivity, ChargePaymentArguments>();

        x.UsingRabbitMq((context, cfg) =>
        {
            cfg.Host(RabbitHost, "/", h =>
            {
                h.Username(RabbitUser);
                h.Password(RabbitPass);
            });

            // ConfigureEndpoints tworzy TERAZ nie tylko kolejkę konsumenta zdarzeń, ale też osobną
            // kolejkę execute (i compensate, jeśli aktywność ją ma) dla każdej zarejestrowanej aktywności.
            cfg.ConfigureEndpoints(context);
        });
    });

    return hostBuilder.Build();
}
