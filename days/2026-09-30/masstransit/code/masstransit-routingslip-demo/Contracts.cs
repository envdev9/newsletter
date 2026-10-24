using MassTransit;
using MassTransit.Courier.Contracts;

namespace MassTransitRoutingSlipDemo;

public static class Log
{
    private static readonly System.Diagnostics.Stopwatch Clock = System.Diagnostics.Stopwatch.StartNew();
    public static void Line(string text) => Console.WriteLine($"[{Clock.ElapsedMilliseconds,6} ms] {text}");
}

// --- Kontrakty argumentów/logów aktywności - zwykłe recordy, tak jak wiadomości Publish/Send we
//     wcześniejszych wydaniach. RoutingSlipBuilder.AddActivity przyjmuje obiekt (np. anonimowy),
//     który MassTransit mapuje na TArguments dokładnie tym samym mechanizmem co Send<T>(values). ---
public record ReserveInventoryArguments(string OrderId, string Sku, int Qty);
public record ReserveInventoryLog(string OrderId, string Sku, int Qty);

public record ChargePaymentArguments(string OrderId, decimal Amount);

// --- Aktywność 1: rezerwacja towaru. Ma kompensację (ICompensateActivity<TLog>) - dzięki temu
//     framework wie, jak cofnąć ten krok, jeśli KOLEJNA aktywność w routing slipie zawiedzie. ---
public class ReserveInventoryActivity :
    IActivity<ReserveInventoryArguments, ReserveInventoryLog>
{
    public Task<ExecutionResult> Execute(ExecuteContext<ReserveInventoryArguments> context)
    {
        var a = context.Arguments;
        Log.Line($"[ReserveInventory]  EXECUTE   rezerwuję {a.Qty}x {a.Sku} dla zamówienia {a.OrderId}");

        // W realnym świecie: zapis do magazynu (np. UPDATE stock SET reserved += @qty).
        // Tu symulujemy - ważne jest to, CO trafia do logu kompensacji (poniżej).
        var log = new ReserveInventoryLog(a.OrderId, a.Sku, a.Qty);
        return Task.FromResult(context.Completed(log));
    }

    public Task<CompensationResult> Compensate(CompensateContext<ReserveInventoryLog> context)
    {
        var l = context.Log;
        Log.Line($"[ReserveInventory]  COMPENSATE  zwalniam rezerwację {l.Qty}x {l.Sku} " +
                 $"dla zamówienia {l.OrderId} - dalszy krok routing slipa zawiódł");
        return Task.FromResult(context.Compensated());
    }
}

// --- Aktywność 2: obciążenie płatności. TYLKO IExecuteActivity (bez ICompensateActivity) - nie ma
//     nic do cofnięcia po jej własnej stronie, jeśli zawiedzie ona sama albo coś PO niej. ---
public class ChargePaymentActivity : IExecuteActivity<ChargePaymentArguments>
{
    public Task<ExecutionResult> Execute(ExecuteContext<ChargePaymentArguments> context)
    {
        var a = context.Arguments;
        Log.Line($"[ChargePayment]     EXECUTE   próbuję obciążyć {a.Amount:0.00} zł za zamówienie {a.OrderId}");

        if (a.Amount > 1000m)
        {
            // Wyjątek z aktywności = ta aktywność się nie udała. MassTransit NIE łapie go cicho -
            // routing slip przechodzi w stan faulted i automatycznie kompensuje WCZEŚNIEJSZE aktywności
            // (tu: ReserveInventory), w odwrotnej kolejności niż zostały wykonane.
            Log.Line($"[ChargePayment]     EXECUTE   karta ODRZUCONA (kwota {a.Amount:0.00} zł > limit 1000 zł)");
            throw new InvalidOperationException($"Karta odrzucona dla kwoty {a.Amount:0.00} zł");
        }

        Log.Line("[ChargePayment]     EXECUTE   płatność zaakceptowana");
        return Task.FromResult(context.Completed());
    }
}

// --- Konsument zdarzeń końcowych routing slipa - dokładnie dwa możliwe wyniki całej transakcji. ---
public class RoutingSlipEventsConsumer :
    IConsumer<RoutingSlipCompleted>,
    IConsumer<RoutingSlipFaulted>
{
    public Task Consume(ConsumeContext<RoutingSlipCompleted> context)
    {
        Log.Line($"[EVENTS] RoutingSlipCompleted {context.Message.TrackingNumber} " +
                 $"po {context.Message.Duration.TotalMilliseconds:F0} ms - WSZYSTKIE aktywności ukończone, nic nie kompensowano");
        return Task.CompletedTask;
    }

    public Task Consume(ConsumeContext<RoutingSlipFaulted> context)
    {
        Log.Line($"[EVENTS] RoutingSlipFaulted {context.Message.TrackingNumber} " +
                 $"po {context.Message.Duration.TotalMilliseconds:F0} ms - transakcja NIE powiodła się, " +
                 "kompensacja poprzednich aktywności już wykonana");
        foreach (var ex in context.Message.ActivityExceptions)
            Log.Line($"[EVENTS]   aktywność '{ex.Name}' rzuciła: {ex.ExceptionInfo.ExceptionType}: {ex.ExceptionInfo.Message}");
        return Task.CompletedTask;
    }
}
