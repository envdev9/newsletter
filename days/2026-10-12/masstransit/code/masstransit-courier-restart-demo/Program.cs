using System.Net.Http.Headers;
using System.Text;
using System.Text.Json;
using MassTransit;
using MassTransit.Courier.Contracts;
using MassTransitCourierRestart;
using Microsoft.Extensions.DependencyInjection;
using Microsoft.Extensions.Hosting;
using Microsoft.Extensions.Logging;

// Lokalny broker z Dockera na potrzeby tego wydania (jednorazowy login deweloperski, nie "guest").
const string RabbitHost = "localhost";
const string RabbitUser = "newsletter_dev";
const string RabbitPass = "newsletter_dev_local_only";
const string ManagementBaseUrl = "http://localhost:15672";

if (args.Length == 0)
{
    Console.WriteLine("Uzycie: worker <plik-ksiegi> [slowMs] [idempotent] | start <orderId> | inspect");
    return 1;
}

switch (args[0])
{
    case "worker":
        Ledger.Path = args.Length > 1 ? args[1] : "ledger.log";
        Ledger.SlowMs = args.Length > 2 ? int.Parse(args[2]) : 0;
        Ledger.Idempotent = args.Skip(3).Contains("idempotent");
        Ledger.Crash = args.Skip(3).Contains("crash");
        await RunWorkerAsync();
        break;
    case "start":
        await StartSlipAsync(args.Length > 1 ? args[1] : "ORD-1");
        break;
    case "inspect":
        await InspectAsync();
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
    Console.WriteLine($"WORKER pid={Environment.ProcessId} slowMs={Ledger.SlowMs} idempotent={Ledger.Idempotent} crash={Ledger.Crash} ledger={Ledger.Path}");
    await host.RunAsync();
    Console.WriteLine($"WORKER pid={Environment.ProcessId} zakonczyl RunAsync (graceful shutdown)");
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
    Console.WriteLine($"START pid={Environment.ProcessId} wyslano slip track={track:N} zamowienie={orderId}; proces konczy sie, slip zyje w brokerze");
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

// Stan kolejek z REST API management pluginu (UWAGA: statystyki maja ~5-6 s opoznienia, jak w #5/#7).
async Task InspectAsync()
{
    using var http = new HttpClient { BaseAddress = new Uri(ManagementBaseUrl) };
    var auth = Convert.ToBase64String(Encoding.ASCII.GetBytes($"{RabbitUser}:{RabbitPass}"));
    http.DefaultRequestHeaders.Authorization = new AuthenticationHeaderValue("Basic", auth);
    var json = await http.GetStringAsync("/api/queues/%2f");
    using var doc = JsonDocument.Parse(json);
    Console.WriteLine("--- kolejki (ready / unacked / consumers) ---");
    foreach (var q in doc.RootElement.EnumerateArray().OrderBy(e => e.GetProperty("name").GetString()))
    {
        int Get(string p) => q.TryGetProperty(p, out var v) && v.ValueKind == JsonValueKind.Number ? v.GetInt32() : 0;
        Console.WriteLine($"  {q.GetProperty("name").GetString(),-48} ready={Get("messages_ready")} unacked={Get("messages_unacknowledged")} consumers={Get("consumers")}");
    }
}
