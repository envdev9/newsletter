using MassTransit;
using MassTransit.Courier.Contracts;

namespace MassTransitCourierRestart;

// Ksiega skutkow ubocznych: zwykly plik tekstowy, zeby przezyl zabicie procesu.
// W prawdziwym systemie to bylaby operacja u zewnetrznego dostawcy (obciazenie karty, rezerwacja).
public static class Ledger
{
    public static string Path = "ledger.log";
    public static int SlowMs;          // opoznienie AuthorizePayment PO skutku ubocznym, PRZED potwierdzeniem kroku
    public static bool Idempotent;     // czy aktywnosc sprawdza klucz idempotentnosci przed skutkiem
    public static bool Crash;          // czy proces ma sie wywrocic (FailFast) po AuthorizePayment
    private static readonly object Gate = new();

    public static void Write(string text)
    {
        var line = $"{DateTime.Now:HH:mm:ss.fff} pid={Environment.ProcessId,-6} {text}";
        lock (Gate) File.AppendAllText(Path, line + Environment.NewLine);
        Console.WriteLine(line);
    }

    public static bool HasEffect(string key)
    {
        lock (Gate)
            return File.Exists(Path) && File.ReadLines(Path).Any(l => l.Contains($"EFFECT key={key}"));
    }
}

// ReservationId NIE jest w itinerary - dopelnia go zmienna routing slipa z ReserveInventory.
public record StepArgs(string OrderId, string? ReservationId);
public record StepLog(string Step, string OrderId);

public abstract class StepActivity : IActivity<StepArgs, StepLog>
{
    protected abstract string Name { get; }
    protected virtual int ExtraDelayMs => 0;

    public async Task<ExecutionResult> Execute(ExecuteContext<StepArgs> context)
    {
        var redelivered = context.ReceiveContext.Redelivered;
        var key = $"{context.TrackingNumber:N}:{Name}";
        Ledger.Write($"EXECUTE   {Name,-16} redelivered={redelivered} executionId={context.ExecutionId.ToString("N")[20..]}");

        if (Ledger.Idempotent && Ledger.HasEffect(key))
        {
            Ledger.Write($"SKIP      {Name,-16} skutek juz istnieje (klucz idempotentnosci)");
        }
        else
        {
            Ledger.Write($"EFFECT key={key}  <- {Name}: skutek uboczny wykonany");
        }

        if (ExtraDelayMs > 0)
            await Task.Delay(ExtraDelayMs);

        // Symulacja twardej awarii: proces ginie PO skutku ubocznym, PRZED potwierdzeniem kroku
        // (FailFast = brak finalizerow, brak graceful shutdown, polaczenie TCP z brokerem po prostu znika).
        if (Ledger.Crash && ExtraDelayMs > 0 && !redelivered)
        {
            Ledger.Write($"CRASH     {Name,-16} Environment.FailFast - proces ginie bez potwierdzenia");
            Environment.FailFast("symulowana awaria procesu w trakcie slipa");
        }

        Ledger.Write($"COMPLETED {Name,-16} krok potwierdzony");
        return Complete(context);
    }

    protected virtual ExecutionResult Complete(ExecuteContext<StepArgs> context)
        => context.Completed(new StepLog(Name, context.Arguments.OrderId));

    public Task<CompensationResult> Compensate(CompensateContext<StepLog> context)
        => Task.FromResult(context.Compensated());
}

public class ReserveInventoryActivity : StepActivity
{
    protected override string Name => "ReserveInventory";

    protected override ExecutionResult Complete(ExecuteContext<StepArgs> context)
        => context.CompletedWithVariables(
            new StepLog(Name, context.Arguments.OrderId),
            new { ReservationId = "RES-" + context.Arguments.OrderId });
}

public class AuthorizePaymentActivity : StepActivity
{
    protected override string Name => "AuthorizePayment";
    protected override int ExtraDelayMs => Ledger.SlowMs;
}

public class CreateShipmentActivity : StepActivity { protected override string Name => "CreateShipment"; }
public class NotifyCustomerActivity : StepActivity { protected override string Name => "NotifyCustomer"; }

// Zdarzenia slipa trafiaja do TRWALEJ kolejki - ten konsument odbierze je tez po restarcie.
public class SlipEventsConsumer :
    IConsumer<RoutingSlipCompleted>,
    IConsumer<RoutingSlipFaulted>,
    IConsumer<RoutingSlipCompensationFailed>
{
    public Task Consume(ConsumeContext<RoutingSlipCompleted> c)
    { Ledger.Write($"EVENT     RoutingSlipCompleted track={c.Message.TrackingNumber:N}"); return Task.CompletedTask; }

    public Task Consume(ConsumeContext<RoutingSlipFaulted> c)
    { Ledger.Write("EVENT     RoutingSlipFaulted"); return Task.CompletedTask; }

    public Task Consume(ConsumeContext<RoutingSlipCompensationFailed> c)
    { Ledger.Write("EVENT     RoutingSlipCompensationFailed"); return Task.CompletedTask; }
}
