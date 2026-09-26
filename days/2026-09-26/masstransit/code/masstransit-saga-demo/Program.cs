using MassTransit;
using MassTransit.Saga;
using MassTransitSagaDemo;
using Microsoft.Extensions.DependencyInjection;
using Microsoft.Extensions.Hosting;
using Microsoft.Extensions.Logging;

var builder = Host.CreateApplicationBuilder(args);
builder.Logging.SetMinimumLevel(LogLevel.Warning);
builder.Logging.AddFilter("MassTransit", LogLevel.Critical);   // wycisza R-FAULT ze stack trace'ami

builder.Services.AddMassTransit(x =>
{
    x.AddDelayedMessageScheduler();                 // scheduler in-memory dla Schedule<,>
    x.AddConsumer<ShipOrderConsumer>();
    x.AddConsumer<OutcomeConsumer>();
    x.AddConsumer<SagaFaultConsumer>();
    x.AddSagaStateMachine<OrderStateMachine, OrderState>()
        .InMemoryRepository();                      // instancje sagi trzymane w pamięci procesu

    x.UsingInMemory((context, cfg) =>
    {
        cfg.UseDelayedMessageScheduler();
        cfg.ConfigureEndpoints(context);
    });
});

using var host = builder.Build();
await host.StartAsync();

var bus = host.Services.GetRequiredService<IBus>();
var repo = host.Services.GetRequiredService<IQuerySagaRepository<OrderState>>();

var loader = host.Services.GetRequiredService<ILoadSagaRepository<OrderState>>();

async Task<string> Snapshot()
{
    var ids = await repo.Find(new SagaQuery<OrderState>(_ => true));
    var list = new List<string>();
    foreach (var id in ids)
    {
        var saga = await loader.Load(id);
        list.Add($"{id.ToString()[..8]}={saga?.CurrentState}");
    }
    return list.Count == 0 ? "(pusto)" : string.Join(", ", list);
}

// --- 1. Szczęśliwa ścieżka; stock przychodzi PRZED płatnością ---
Console.WriteLine("=== 1. Happy path: stock przed płatnością, composite ReadyToShip ===");
var o1 = Guid.NewGuid();
await bus.Publish(new OrderSubmitted(o1, 199.99m));
await Task.Delay(300);
Log.Line($"repozytorium: {await Snapshot()}");
await bus.Publish(new StockReserved(o1));
await Task.Delay(300);
Log.Line($"repozytorium: {await Snapshot()}");
await bus.Publish(new PaymentReceived(o1));
await Task.Delay(600);
Log.Line($"repozytorium po zakończeniu: {await Snapshot()}");

// --- 2. Timeout ---
Console.WriteLine();
Console.WriteLine("=== 2. Timeout: nikt nie płaci (Schedule 1,5 s) ===");
var o2 = Guid.NewGuid();
await bus.Publish(new OrderSubmitted(o2, 49.00m));
await Task.Delay(2200);
Log.Line($"repozytorium: {await Snapshot()}");

// --- 3. Spóźniona płatność po Cancelled ---
Console.WriteLine();
Console.WriteLine("=== 3. Spóźniona płatność w stanie Cancelled (Ignore) ===");
await bus.Publish(new PaymentReceived(o2));
await Task.Delay(500);
Log.Line($"repozytorium: {await Snapshot()}");

// --- 4. Płatność odwołuje timeout ---
Console.WriteLine();
Console.WriteLine("=== 4. Płatność przed upływem czasu odwołuje timeout (Unschedule) ===");
var o3 = Guid.NewGuid();
await bus.Publish(new OrderSubmitted(o3, 10m));
await Task.Delay(200);
await bus.Publish(new PaymentReceived(o3));
await Task.Delay(2200);   // dłużej niż timeout - nic nie powinno się anulować
Log.Line($"repozytorium: {await Snapshot()}");

// --- 5. Event dla nieistniejącej sagi ---
Console.WriteLine();
Console.WriteLine("=== 5. PaymentReceived dla nieznanego zamówienia ===");
await bus.Publish(new PaymentReceived(Guid.NewGuid()));
await Task.Delay(500);
Log.Line($"repozytorium: {await Snapshot()}");

// --- 6. Event w złym stanie: ShipmentDispatched dla zamówienia, które jest tylko Paid ---
Console.WriteLine();
Console.WriteLine("=== 6. ShipmentDispatched w stanie Paid (niezdefiniowane przejście) ===");
await bus.Publish(new ShipmentDispatched(o3));
await Task.Delay(500);
Log.Line($"repozytorium: {await Snapshot()}");

Console.WriteLine();
Console.WriteLine("Koniec.");
await host.StopAsync();
