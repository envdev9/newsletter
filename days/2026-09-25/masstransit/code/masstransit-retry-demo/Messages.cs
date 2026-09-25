using System.Diagnostics;
using MassTransit;

namespace MassTransitRetryDemo;

// --- Kontrakty ---------------------------------------------------------------
public record ChargeCard(Guid Id, string Scenario);      // psuje się na 2 pierwsze próby
public record ChargeCardInterval(Guid Id);               // zawsze wybucha - retry Interval
public record ChargeCardExponential(Guid Id);            // zawsze wybucha - retry Exponential
public record ChargeCardInvalid(Guid Id);                // ArgumentException - wykluczony z retry
public record ChargeCardRedelivery(Guid Id);             // Immediate + delayed redelivery
public record ShipOrder(Guid Id);                        // consumer publikuje event i wybucha (bez outboxa)
public record ShipOrderSafe(Guid Id);                    // to samo, ale z in-memory outboxem
public record OrderShipped(Guid Id, string Source);      // event publikowany z consumera
public record NobodyConsumesThis(Guid Id);               // typ bez consumera na docelowym endpointcie

// --- Prosty logger z czasem od startu (widać odstępy między próbami) ---------
public static class Log
{
    private static readonly Stopwatch Clock = Stopwatch.StartNew();
    private static readonly object Gate = new();

    public static void Write(string text)
    {
        lock (Gate)
            Console.WriteLine($"[{Clock.ElapsedMilliseconds,5} ms] {text}");
    }
}

// --- Liczniki (do asercji na końcu) ------------------------------------------
public static class Counters
{
    public static int ShippedFromUnsafe;
    public static int ShippedFromSafe;
}

// --- 1. Nietrwały błąd: 2 pierwsze próby wybuchają, trzecia przechodzi -------
public class FlakyChargeConsumer : IConsumer<ChargeCard>
{
    public Task Consume(ConsumeContext<ChargeCard> context)
    {
        var attempt = context.GetRetryAttempt();      // 0 = pierwsza próba
        Log.Write($"[flaky] próba #{attempt + 1} (GetRetryAttempt={attempt})");
        if (attempt < 2)
            throw new InvalidOperationException($"bramka płatnicza niedostępna (próba {attempt + 1})");
        Log.Write("[flaky] SUKCES");
        return Task.CompletedTask;
    }
}

// --- 2. Błąd trwały - do testu Interval / Exponential / filtrów --------------
public class AlwaysFailsIntervalConsumer : IConsumer<ChargeCardInterval>
{
    public Task Consume(ConsumeContext<ChargeCardInterval> context)
    {
        Log.Write($"[interval] próba #{context.GetRetryAttempt() + 1}");
        throw new InvalidOperationException("zawsze wybucha (interval)");
    }
}

public class AlwaysFailsExponentialConsumer : IConsumer<ChargeCardExponential>
{
    public Task Consume(ConsumeContext<ChargeCardExponential> context)
    {
        Log.Write($"[exponential] próba #{context.GetRetryAttempt() + 1}");
        throw new InvalidOperationException("zawsze wybucha (exponential)");
    }
}

public class InvalidInputConsumer : IConsumer<ChargeCardInvalid>
{
    public Task Consume(ConsumeContext<ChargeCardInvalid> context)
    {
        Log.Write($"[invalid] próba #{context.GetRetryAttempt() + 1}");
        throw new ArgumentException("kwota ujemna - retry nic tu nie pomoże");
    }
}

// --- 3. Redelivery: retry natychmiastowy + odroczone ponowne dostarczenie ----
public class RedeliveryConsumer : IConsumer<ChargeCardRedelivery>
{
    public Task Consume(ConsumeContext<ChargeCardRedelivery> context)
    {
        var redelivery = context.GetRedeliveryCount();
        var retry = context.GetRetryAttempt();
        Log.Write($"[redelivery] dostarczenie #{redelivery + 1}, retry w tym dostarczeniu={retry}");
        if (redelivery < 2)
            throw new InvalidOperationException("baza chwilowo niedostępna");
        Log.Write("[redelivery] SUKCES");
        return Task.CompletedTask;
    }
}

// --- 4. Outbox: consumer publikuje event, po czym pada przy pierwszej próbie -
public class ShipOrderConsumer : IConsumer<ShipOrder>
{
    public async Task Consume(ConsumeContext<ShipOrder> context)
    {
        var attempt = context.GetRetryAttempt();
        await context.Publish(new OrderShipped(context.Message.Id, "bez-outboxa"));
        Log.Write($"[bez outboxa] opublikowano OrderShipped (próba #{attempt + 1})");
        if (attempt == 0)
            throw new InvalidOperationException("awaria PO publikacji eventu");
    }
}

public class ShipOrderSafeConsumer : IConsumer<ShipOrderSafe>
{
    public async Task Consume(ConsumeContext<ShipOrderSafe> context)
    {
        var attempt = context.GetRetryAttempt();
        await context.Publish(new OrderShipped(context.Message.Id, "z-outboxem"));
        Log.Write($"[z outboxem] opublikowano OrderShipped (próba #{attempt + 1})");
        if (attempt == 0)
            throw new InvalidOperationException("awaria PO publikacji eventu");
    }
}

public class OrderShippedConsumer : IConsumer<OrderShipped>
{
    public Task Consume(ConsumeContext<OrderShipped> context)
    {
        if (context.Message.Source == "bez-outboxa") Interlocked.Increment(ref Counters.ShippedFromUnsafe);
        else Interlocked.Increment(ref Counters.ShippedFromSafe);
        Log.Write($"[OrderShipped] odebrano event od: {context.Message.Source}");
        return Task.CompletedTask;
    }
}

// --- 5. Fault<T> - zdarzenie o porażce ---------------------------------------
public class FaultLogger<T> : IConsumer<Fault<T>> where T : class
{
    public Task Consume(ConsumeContext<Fault<T>> context)
    {
        var f = context.Message;
        Log.Write($"[Fault<{typeof(T).Name}>] {f.Exceptions[0].ExceptionType}: {f.Exceptions[0].Message} " +
                  $"(FaultedMessageId: {f.FaultedMessageId != null}, wiadomość: {f.Message.GetType().Name})");
        return Task.CompletedTask;
    }
}

// --- 6. Observer - "consumer faulted" na poziomie busa -----------------------
public class FaultObserver : IConsumeObserver
{
    public Task PreConsume<T>(ConsumeContext<T> context) where T : class => Task.CompletedTask;
    public Task PostConsume<T>(ConsumeContext<T> context) where T : class => Task.CompletedTask;

    public Task ConsumeFault<T>(ConsumeContext<T> context, Exception exception) where T : class
    {
        Log.Write($"[observer] ConsumeFault<{typeof(T).Name}>: {exception.GetType().Name}");
        return Task.CompletedTask;
    }
}

// --- 7. Odbiorca wiadomości "przeniesionej" do _error / _skipped -------------
public class ErrorQueueSpy<T> : IConsumer<T> where T : class
{
    public Task Consume(ConsumeContext<T> context)
    {
        Log.Write($"[SPY {context.ReceiveContext.InputAddress.AbsolutePath}] dotarła {typeof(T).Name}");
        Dump(context);
        return Task.CompletedTask;
    }

    public static void Dump(ConsumeContext context)
    {
        foreach (var (key, value) in context.ReceiveContext.TransportHeaders.GetAll())
            if (key.StartsWith("MT-", StringComparison.Ordinal)
                && !key.StartsWith("MT-Host-", StringComparison.Ordinal)       // szum: maszyna, proces, wersje
                && key != "MT-Fault-StackTrace")                                // za długi na konsolę
                Log.Write($"[SPY]     {key} = {value}");
    }
}

public class SkippedSpy : IConsumer<NobodyConsumesThis>
{
    public Task Consume(ConsumeContext<NobodyConsumesThis> context)
    {
        Log.Write($"[SPY {context.ReceiveContext.InputAddress.AbsolutePath}] dotarła NobodyConsumesThis");
        ErrorQueueSpy<NobodyConsumesThis>.Dump(context);
        return Task.CompletedTask;
    }
}
