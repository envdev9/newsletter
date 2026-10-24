using MassTransit;
using Microsoft.Extensions.DependencyInjection;
using Microsoft.Extensions.Hosting;
using MassTransitInMemoryDemo;

// ---------------------------------------------------------------------------
// HOST + BUS - generic host z zarejestrowanym MassTransit, transport
// in-memory (UsingInMemory) - żadnego RabbitMQ, żadnego Dockera.
// ---------------------------------------------------------------------------
var builder = Host.CreateApplicationBuilder(args);

builder.Services.AddMassTransit(x =>
{
    x.AddConsumer<OrderPlacedConsumer>();

    x.UsingInMemory((context, cfg) =>
    {
        // Podłącza konsumenty zarejestrowane wyżej pod kolejki na tym busie.
        cfg.ConfigureEndpoints(context);
    });
});

using IHost host = builder.Build();

await host.StartAsync();

var bus = host.Services.GetRequiredService<IBus>();

// ---------------------------------------------------------------------------
// PRODUCER - Publish wysyła komunikat do WSZYSTKICH subskrybentów typu
// OrderPlaced (tu: jeden, OrderPlacedConsumer). Gdyby chodziło o wysłanie
// komendy do JEDNEGO, konkretnego odbiorcy pod znanym adresem, użylibyśmy
// bus.Send(...) zamiast Publish - różnica opisana w artykule.
// ---------------------------------------------------------------------------
var order = new OrderPlaced(Guid.NewGuid(), "Jan Kowalski", 149.99m);

Console.WriteLine($"Publikuję: zamówienie {order.OrderId} od {order.CustomerName}...");

await bus.Publish(order);

// Konsument działa asynchronicznie na osobnym wątku puli - dajemy mu chwilę
// na realne przetworzenie, zanim zatrzymamy bus i zakończymy proces.
await Task.Delay(500);

await host.StopAsync();

Console.WriteLine("Bus zatrzymany, koniec programu.");
