using System.Net.Http.Headers;
using System.Text;
using System.Text.Json;
using MassTransit;
using MassTransit.Courier.Contracts;
using MassTransitCourierRedelivery;
using Microsoft.Extensions.DependencyInjection;
using Microsoft.Extensions.Hosting;
using Microsoft.Extensions.Logging;

// Lokalny broker z Dockera (jednorazowy login deweloperski, nie "guest").
const string RabbitHost = "localhost";
const string RabbitUser = "newsletter_dev";
const string RabbitPass = "newsletter_dev_local_only";
const string ManagementBaseUrl = "http://localhost:15672";

if (args.Length == 0)
{
    Console.WriteLine("Uzycie: worker <plik-ksiegi> [slowMs] [idempotent] | start <orderId> | inspect | peek <kolejka>");
    return 1;
}

switch (args[0])
{
    case "worker":
        Ledger.Path = args.Length > 1 ? args[1] : "ledger.log";
        Ledger.SlowMs = args.Length > 2 ? int.Parse(args[2]) : 0;
        Ledger.Idempotent = args.Skip(3).Contains("idempotent");
        await RunWorkerAsync();
        break;
    case "start":
        await StartSlipAsync(args.Length > 1 ? args[1] : "ORD-1");
        break;
    case "inspect":
        await InspectAsync();
        break;
    case "peek":
        await PeekAsync(args.Length > 1 ? args[1] : "authorize-payment_execute");
        break;
    default:
        Console.WriteLine($"Nieznany tryb: {args[0]}");
        return 1;
}

return 0;

// Proces roboczy: cztery aktywnosci + konsument zdarzen. Dziala az do SIGINT/SIGTERM (albo kill -9).
async Task RunWorkerAsync()
{
    var host = BuildWorkerHost();
    Console.WriteLine($"WORKER pid={Environment.ProcessId} slowMs={Ledger.SlowMs} idempotent={Ledger.Idempotent} ledger={Ledger.Path}");
    var sw = System.Diagnostics.Stopwatch.StartNew();
    host.Services.GetRequiredService<IHostApplicationLifetime>().ApplicationStopping.Register(
        () => Ledger.Write("LIFETIME  ApplicationStopping (SIGTERM/SIGINT odebrany)"));
    // Opcjonalnie: sam zatrzymaj host po N ms (to ta sama sciezka co SIGTERM: StopApplication) - powtarzalny graceful shutdown.
    var stopArg = Environment.GetCommandLineArgs().FirstOrDefault(a => a.StartsWith("stopafter="));
    if (stopArg is not null)
    {
        var ms = int.Parse(stopArg["stopafter=".Length..]);
        var lifetime = host.Services.GetRequiredService<IHostApplicationLifetime>();
        _ = Task.Run(async () => { await Task.Delay(ms); Ledger.Write($"STOPAFTER StopApplication() po {ms} ms"); lifetime.StopApplication(); });
    }
    await host.RunAsync();
    Ledger.Write($"WORKER    RunAsync zakonczony po {sw.Elapsed.TotalSeconds:F1} s od startu (graceful shutdown)");
}

// Osobny proces TYLKO wysyla slip i konczy dzialanie - nie ma konsumentow, wiec nie podkrada pracy workerowi.
async Task StartSlipAsync(string orderId)
{
    var builder = Host.CreateApplicationBuilder();
    builder.Logging.SetMinimumLevel(LogLevel.Warning);
    builder.Logging.AddFilter("MassTransit", LogLevel.Critical);
    builder.Services.AddMassTransit(x =>
    {
        x.SetEndpointNameFormatter(KebabCaseEndpointNameFormatter.Instance);
        x.UsingRabbitMq((ctx, cfg) => cfg.Host(RabbitHost, "/", h => { h.Username(RabbitUser); h.Password(RabbitPass); }));
    });
    using var host = builder.Build();
    await host.StartAsync();
    var bus = host.Services.GetRequiredService<IBus>();

    var f = KebabCaseEndpointNameFormatter.Instance;
    Uri Exec<TA>() where TA : class, IExecuteActivity<StepArgs>, new()
        => new($"queue:{f.ExecuteActivity<TA, StepArgs>()}");

    var track = Guid.NewGuid();
    var slip = new RoutingSlipBuilder(track);
    slip.AddSubscription(new Uri($"queue:{f.Consumer<SlipEventsConsumer>()}"),
        RoutingSlipEvents.Completed | RoutingSlipEvents.Faulted | RoutingSlipEvents.CompensationFailed);
    slip.AddActivity("ReserveInventory", Exec<ReserveInventoryActivity>(), new { OrderId = orderId });
    slip.AddActivity("AuthorizePayment", Exec<AuthorizePaymentActivity>(), new { OrderId = orderId });
    slip.AddActivity("CreateShipment", Exec<CreateShipmentActivity>(), new { OrderId = orderId });
    slip.AddActivity("NotifyCustomer", Exec<NotifyCustomerActivity>(), new { OrderId = orderId });
    await bus.Execute(slip.Build());
    Console.WriteLine($"START pid={Environment.ProcessId} wyslano slip track={track.ToString("N")[..8]} zamowienie={orderId}");
    await host.StopAsync();
}

IHost BuildWorkerHost()
{
    var hostBuilder = Host.CreateApplicationBuilder();
    hostBuilder.Logging.SetMinimumLevel(LogLevel.Warning);
    hostBuilder.Logging.AddFilter("MassTransit", LogLevel.Error);

    hostBuilder.Services.AddMassTransit(x =>
    {
        x.SetEndpointNameFormatter(KebabCaseEndpointNameFormatter.Instance);
        x.AddConsumer<SlipEventsConsumer>();
        x.AddActivity<ReserveInventoryActivity, StepArgs, StepLog>();
        x.AddActivity<AuthorizePaymentActivity, StepArgs, StepLog>();
        x.AddActivity<CreateShipmentActivity, StepArgs, StepLog>();
        x.AddActivity<NotifyCustomerActivity, StepArgs, StepLog>();

        x.UsingRabbitMq((context, cfg) =>
        {
            cfg.Host(RabbitHost, "/", h => { h.Username(RabbitUser); h.Password(RabbitPass); });
            cfg.ConfigureEndpoints(context);
        });
    });
    return hostBuilder.Build();
}

HttpClient ManagementClient()
{
    var http = new HttpClient { BaseAddress = new Uri(ManagementBaseUrl) };
    var auth = Convert.ToBase64String(Encoding.ASCII.GetBytes($"{RabbitUser}:{RabbitPass}"));
    http.DefaultRequestHeaders.Authorization = new AuthenticationHeaderValue("Basic", auth);
    return http;
}

// Stan kolejek z REST API management (UWAGA: statystyki maja ~5-6 s opoznienia; po awarii prawde mowi rabbitmqctl).
async Task InspectAsync()
{
    using var http = ManagementClient();
    var json = await http.GetStringAsync("/api/queues/%2f");
    using var doc = JsonDocument.Parse(json);
    Console.WriteLine("--- kolejki (ready / unacked / consumers) ---");
    foreach (var q in doc.RootElement.EnumerateArray().OrderBy(e => e.GetProperty("name").GetString()))
    {
        int Get(string p) => q.TryGetProperty(p, out var v) && v.ValueKind == JsonValueKind.Number ? v.GetInt32() : 0;
        Console.WriteLine($"  {q.GetProperty("name").GetString(),-34} ready={Get("messages_ready")} unacked={Get("messages_unacknowledged")} consumers={Get("consumers")}");
    }
}

// Podglad wiadomosci BEZ konsumowania (ack_requeue_true). UWAGA: sam podglad wiadomosc zwraca do kolejki,
// a broker oznacza ja wtedy jako redelivered=true.
async Task PeekAsync(string queue)
{
    using var http = ManagementClient();
    var body = JsonSerializer.Serialize(new { count = 1, ackmode = "ack_requeue_true", encoding = "auto" });
    var resp = await http.PostAsync($"/api/queues/%2f/{queue}/get", new StringContent(body, Encoding.UTF8, "application/json"));
    var text = await resp.Content.ReadAsStringAsync();
    using var doc = JsonDocument.Parse(text);
    if (doc.RootElement.GetArrayLength() == 0) { Console.WriteLine($"{queue}: pusta"); return; }
    var m = doc.RootElement[0];
    Console.WriteLine($"{queue}: redelivered(broker)={m.GetProperty("redelivered").GetBoolean()} routing_key={m.GetProperty("routing_key").GetString()}");
    using var payload = JsonDocument.Parse(m.GetProperty("payload").GetString()!);
    var msg = payload.RootElement.GetProperty("message");
    Console.WriteLine("  itinerary:   " + string.Join(", ", msg.GetProperty("itinerary").EnumerateArray().Select(a => a.GetProperty("name").GetString())));
    Console.WriteLine("  pola slipa:  " + string.Join(", ", msg.EnumerateObject().Select(p => p.Name)));
    if (msg.TryGetProperty("activityLogs", out var logs))
        Console.WriteLine("  activityLogs: " + string.Join(", ", logs.EnumerateArray().Select(a => a.GetProperty("name").GetString())));
    if (msg.TryGetProperty("variables", out var vars))
        Console.WriteLine("  variables:    " + vars.GetRawText());
}
