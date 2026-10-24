using MassTransit;
using Microsoft.Extensions.Logging;

// ---------------------------------------------------------------------------
// MESSAGE i CONSUMER żyją w jawnej przestrzeni nazw - MassTransit wymaga, żeby
// typy komunikatów miały namespace (używa go do zbudowania nazwy kolejki i
// adresu), więc "goły" top-level record bez namespace nie zadziała.
// ---------------------------------------------------------------------------
namespace MassTransitInMemoryDemo;

// MESSAGE (kontrakt) - zwykły, niemutowalny rekord. To jedyna rzecz, którą
// dzielą ze sobą Producer i Consumer - żadnej wspólnej klasy bazowej,
// żadnego "serwisu". Tylko kształt danych.
public record OrderPlaced(Guid OrderId, string CustomerName, decimal Amount);

// CONSUMER - klasa, która wie co zrobić, gdy przyjdzie OrderPlaced.
// IConsumer<T> to cały wymagany kontrakt: jedna metoda, Consume.
public class OrderPlacedConsumer : IConsumer<OrderPlaced>
{
    private readonly ILogger<OrderPlacedConsumer> _logger;

    public OrderPlacedConsumer(ILogger<OrderPlacedConsumer> logger)
    {
        _logger = logger;
    }

    public Task Consume(ConsumeContext<OrderPlaced> context)
    {
        var msg = context.Message;
        _logger.LogInformation(
            "Odebrano: zamówienie {OrderId} od {CustomerName} na kwotę {Amount} zł",
            msg.OrderId, msg.CustomerName, msg.Amount);

        Console.WriteLine(
            $"Odebrano: zamówienie {msg.OrderId} od {msg.CustomerName} na kwotę {msg.Amount} zł");

        return Task.CompletedTask;
    }
}
