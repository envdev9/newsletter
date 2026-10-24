using MassTransit;

namespace MassTransitRabbitMqDemo;

// Kontrakt wiadomości - to samo, niezależnie od transportu (in-memory czy RabbitMQ).
public record OrderSubmitted(Guid OrderId, string Sku, int Qty);

public static class Log
{
    private static readonly System.Diagnostics.Stopwatch Clock = System.Diagnostics.Stopwatch.StartNew();
    public static void Line(string text) => Console.WriteLine($"[{Clock.ElapsedMilliseconds,6} ms] {text}");
}

public class OrderConsumer : IConsumer<OrderSubmitted>
{
    // Licznik statyczny - tylko do policzenia, ile wiadomości ten proces faktycznie odebrał.
    public static int Received;

    public Task Consume(ConsumeContext<OrderSubmitted> context)
    {
        Interlocked.Increment(ref Received);
        Log.Line($"OrderConsumer: zamówienie {context.Message.OrderId:N} " +
                 $"({context.Message.Sku} x{context.Message.Qty}), kolejka wejściowa = {context.ReceiveContext.InputAddress.AbsolutePath}");
        return Task.CompletedTask;
    }
}
