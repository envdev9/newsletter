using MassTransit;

namespace MassTransitRoutingDemo;

// --- kontrakty ---
public record GetPrice(string Sku);
public record PriceResult(string Sku, decimal Price);
public record SkuNotFound(string Sku);
public record GetStock(string Sku);            // celowo: nikt tego nie konsumuje
public record Ping(string Text);              // zwykły event do demonstracji filtrów i nazw kolejek

public static class Log
{
    private static readonly System.Diagnostics.Stopwatch Clock = System.Diagnostics.Stopwatch.StartNew();
    public static void Line(string text) => Console.WriteLine($"[{Clock.ElapsedMilliseconds,5} ms] {text}");
}

// --- consumery ---
public class PriceConsumer : IConsumer<GetPrice>
{
    private static readonly Dictionary<string, decimal> Prices = new() { ["ABC-1"] = 42.50m, ["XYZ-9"] = 7m };

    public async Task Consume(ConsumeContext<GetPrice> context)
    {
        Log.Line($"PriceConsumer: kolejka wejściowa = {context.ReceiveContext.InputAddress.AbsolutePath}");
        if (context.Message.Sku == "BOOM")
            throw new InvalidOperationException("baza cen niedostępna");

        if (Prices.TryGetValue(context.Message.Sku, out var price))
            await context.RespondAsync(new PriceResult(context.Message.Sku, price));
        else
            await context.RespondAsync(new SkuNotFound(context.Message.Sku));
    }
}

public class PingConsumer : IConsumer<Ping>
{
    public Task Consume(ConsumeContext<Ping> context)
    {
        Log.Line($"PingConsumer: '{context.Message.Text}', kolejka = {context.ReceiveContext.InputAddress.AbsolutePath}, " +
                 $"nagłówek trace = {context.Headers.Get<string>("x-trace") ?? "(brak)"}");
        return Task.CompletedTask;
    }
}

// Definicja: własna nazwa kolejki i limit współbieżności dla konsumenta
public class PingConsumerDefinition : ConsumerDefinition<PingConsumer>
{
    public PingConsumerDefinition()
    {
        EndpointName = "pings-special";   // formatter dopisze prefiks/kebab tylko do nazw generowanych
        ConcurrentMessageLimit = 1;
    }
}

// --- filtry ---
// Filtr konsumenta: mierzy czas i loguje kolejność wykonania
public class TimingConsumeFilter<T> : IFilter<ConsumeContext<T>> where T : class
{
    public async Task Send(ConsumeContext<T> context, IPipe<ConsumeContext<T>> next)
    {
        Log.Line($"  filtr(consume) PRZED {typeof(T).Name}");
        var sw = System.Diagnostics.Stopwatch.StartNew();
        try { await next.Send(context); }
        finally { Log.Line($"  filtr(consume) PO {typeof(T).Name}, {sw.ElapsedMilliseconds} ms"); }
    }
    public void Probe(ProbeContext context) => context.CreateFilterScope("timing");
}

// Filtr wysyłki: dokleja nagłówek do każdej wiadomości opuszczającej busa
public class TraceSendFilter<T> : IFilter<SendContext<T>> where T : class
{
    public Task Send(SendContext<T> context, IPipe<SendContext<T>> next)
    {
        context.Headers.Set("x-trace", "trace-" + typeof(T).Name);
        return next.Send(context);
    }
    public void Probe(ProbeContext context) => context.CreateFilterScope("trace");
}
