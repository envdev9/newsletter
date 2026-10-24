using MassTransit;
using MassTransitRetryDemo;
using Microsoft.Extensions.DependencyInjection;
using Microsoft.Extensions.Hosting;
using Microsoft.Extensions.Logging;

var builder = Host.CreateApplicationBuilder(args);

// Wyciszamy szum MassTransit - zostają nasze linie [xxx ms] ...
// MassTransit.ReceiveTransport loguje każdy R-RETRY / R-FAULT ze stack trace'em -
// tu go wyłączamy dla czytelności (w produkcji ZOSTAW włączony).
builder.Logging.SetMinimumLevel(LogLevel.Warning);
builder.Logging.AddFilter("MassTransit.ReceiveTransport", LogLevel.None);

builder.Services.AddMassTransit(x =>
{
    x.AddConsumer<FlakyChargeConsumer>();
    x.AddConsumer<AlwaysFailsIntervalConsumer>();
    x.AddConsumer<AlwaysFailsExponentialConsumer>();
    x.AddConsumer<InvalidInputConsumer>();
    x.AddConsumer<RedeliveryConsumer>();
    x.AddConsumer<ShipOrderConsumer>();
    x.AddConsumer<ShipOrderSafeConsumer>();
    x.AddConsumer<OrderShippedConsumer>();

    x.AddConsumer<FaultLogger<ChargeCardInterval>>();
    x.AddConsumer<FaultLogger<ChargeCardInvalid>>();
    x.AddConsumer<ErrorQueueSpy<ChargeCardInterval>>();
    x.AddConsumer<SkippedSpy>();

    x.UsingInMemory((context, cfg) =>
    {
        cfg.UseDelayedMessageScheduler();        // potrzebne do UseDelayedRedelivery
        cfg.ConnectConsumeObserver(new FaultObserver());

        // 1) Immediate: 3 kolejne próby bez przerwy (łącznie max 4 wywołania)
        cfg.ReceiveEndpoint("flaky-endpoint", e =>
        {
            e.UseMessageRetry(r => r.Immediate(3));
            e.ConfigureConsumer<FlakyChargeConsumer>(context);
        });

        // 2) Interval: stały odstęp 300 ms, 3 ponowienia
        cfg.ReceiveEndpoint("charge-interval", e =>
        {
            e.UseMessageRetry(r => r.Interval(3, TimeSpan.FromMilliseconds(300)));
            e.ConfigureConsumer<AlwaysFailsIntervalConsumer>(context);
        });

        // 3) Exponential: 4 ponowienia, odstępy rosnące od 100 ms do max 2 s
        cfg.ReceiveEndpoint("charge-exponential", e =>
        {
            e.UseMessageRetry(r => r.Exponential(4,
                TimeSpan.FromMilliseconds(100), TimeSpan.FromSeconds(2), TimeSpan.FromMilliseconds(100)));
            e.ConfigureConsumer<AlwaysFailsExponentialConsumer>(context);
        });

        // 4) Filtr wyjątków: ArgumentException nie ma sensu ponawiać
        cfg.ReceiveEndpoint("charge-invalid", e =>
        {
            e.UseMessageRetry(r =>
            {
                r.Ignore<ArgumentException>();
                r.Immediate(5);
            });
            e.ConfigureConsumer<InvalidInputConsumer>(context);
        });

        // 5) Delayed redelivery (drugi poziom) + krótki retry wewnątrz każdego dostarczenia
        cfg.ReceiveEndpoint("charge-redelivery", e =>
        {
            e.UseDelayedRedelivery(r => r.Intervals(TimeSpan.FromMilliseconds(500), TimeSpan.FromSeconds(1)));
            e.UseMessageRetry(r => r.Immediate(1));
            e.ConfigureConsumer<RedeliveryConsumer>(context);
        });

        // 6) Bez outboxa: event opublikowany przed wyjątkiem ucieka na świat
        cfg.ReceiveEndpoint("ship-unsafe", e =>
        {
            e.UseMessageRetry(r => r.Immediate(2));
            e.ConfigureConsumer<ShipOrderConsumer>(context);
        });

        // 7) Z in-memory outboxem: publish jest wstrzymany do udanego końca Consume
        cfg.ReceiveEndpoint("ship-safe", e =>
        {
            e.UseMessageRetry(r => r.Immediate(2));
            e.UseInMemoryOutbox(context);        // MUSI być PO retry (wewnątrz niego)
            e.ConfigureConsumer<ShipOrderSafeConsumer>(context);
        });

        cfg.ReceiveEndpoint("order-shipped", e => e.ConfigureConsumer<OrderShippedConsumer>(context));

        // Fault<T> jako zwykłe wiadomości - subskrybujemy je jak każdy event
        cfg.ReceiveEndpoint("fault-charge-interval", e => e.ConfigureConsumer<FaultLogger<ChargeCardInterval>>(context));
        cfg.ReceiveEndpoint("fault-charge-invalid", e => e.ConfigureConsumer<FaultLogger<ChargeCardInvalid>>(context));

        // "Podsłuch" na kolejkach _error i _skipped (sprawdzamy, czy in-memory je tworzy)
        cfg.ReceiveEndpoint("charge-interval_error", e => e.ConfigureConsumer<ErrorQueueSpy<ChargeCardInterval>>(context));
        cfg.ReceiveEndpoint("flaky-endpoint_skipped", e => e.ConfigureConsumer<SkippedSpy>(context));
    });
});

using IHost host = builder.Build();
await host.StartAsync();
var bus = host.Services.GetRequiredService<IBus>();

static void Section(string title) => Console.WriteLine($"\n=== {title} ===");

Section("1. Immediate(3): błąd nietrwały, sukces na 3. próbie");
await bus.Publish(new ChargeCard(Guid.NewGuid(), "flaky"));
await Task.Delay(500);

Section("2. Interval(3, 300 ms): błąd trwały -> Fault<T> + _error");
// Send (nie Publish!), żeby "podsłuch" na _error nie dostał kopii od razu
var intervalEndpoint = await bus.GetSendEndpoint(new Uri("queue:charge-interval"));
await intervalEndpoint.Send(new ChargeCardInterval(Guid.NewGuid()));
await Task.Delay(2000);

Section("3. Exponential(4, 100 ms..2 s): błąd trwały");
await bus.Publish(new ChargeCardExponential(Guid.NewGuid()));
await Task.Delay(2500);

Section("4. Ignore<ArgumentException>: brak retry, od razu Fault");
await bus.Publish(new ChargeCardInvalid(Guid.NewGuid()));
await Task.Delay(500);

Section("5. Delayed redelivery: 3 dostarczenia, każde z 1 retry");
await bus.Publish(new ChargeCardRedelivery(Guid.NewGuid()));
await Task.Delay(3500);

Section("6. Outbox: bez i z (publish w consumerze + awaria po nim)");
await bus.Publish(new ShipOrder(Guid.NewGuid()));
await bus.Publish(new ShipOrderSafe(Guid.NewGuid()));
await Task.Delay(1000);
Log.Write($"PODSUMOWANIE outbox: OrderShipped bez outboxa = {Counters.ShippedFromUnsafe}, z outboxem = {Counters.ShippedFromSafe}");

Section("7. _skipped: wiadomość, której endpoint nie umie skonsumować");
var endpoint = await bus.GetSendEndpoint(new Uri("queue:flaky-endpoint"));
await endpoint.Send(new NobodyConsumesThis(Guid.NewGuid()));
await Task.Delay(500);

await host.StopAsync();
Console.WriteLine("\nKoniec.");
