using MassTransit;
using MassTransit.Courier.Contracts;

namespace MassTransitCourierItinerary;

public static class Log
{
    private static readonly System.Diagnostics.Stopwatch Clock = System.Diagnostics.Stopwatch.StartNew();
    public static void Line(string text) => Console.WriteLine($"[{Clock.ElapsedMilliseconds,5} ms] {text}");
}

// Wspolne argumenty dla czterech aktywnosci. FailAt / BreakCompensationAt steruja scenariuszem.
// ReservationId NIE jest podawany w itinerary - dopelnia go zmienna routing slipa (patrz ReserveInventory).
public record StepArgs(string OrderId, string FailAt, string BreakCompensationAt, string? ReservationId);

// Kompensacja widzi WYLACZNIE log (CompensateContext<TLog> nie ma Arguments ani Variables),
// wiec wszystko, czego potrzebuje do cofniecia kroku, musi trafic do logu w Execute.
public record StepLog(string Step, string OrderId, bool BreakCompensation);

// Baza: Execute rzuca, gdy FailAt == Name; Compensate zwraca Failed(), gdy BreakCompensationAt == Name.
public abstract class StepActivity : IActivity<StepArgs, StepLog>
{
    protected abstract string Name { get; }

    public virtual Task<ExecutionResult> Execute(ExecuteContext<StepArgs> context)
    {
        var a = context.Arguments;
        Log.Line($"  EXECUTE     {Name,-16} reservationId={a.ReservationId ?? "(null)"}");
        if (a.FailAt == Name)
        {
            Log.Line($"  EXECUTE     {Name,-16} rzuca wyjatek");
            throw new InvalidOperationException($"{Name} nie powiodl sie");
        }
        return Task.FromResult(context.Completed(new StepLog(Name, a.OrderId, a.BreakCompensationAt == Name)));
    }

    public Task<CompensationResult> Compensate(CompensateContext<StepLog> context)
    {
        if (context.Log.BreakCompensation)
        {
            Log.Line($"  COMPENSATE  {Name,-16} ZAWODZI (context.Failed)");
            return Task.FromResult(context.Failed(new InvalidOperationException($"kompensacja {Name} zawiodla")));
        }
        Log.Line($"  COMPENSATE  {Name,-16} ok");
        return Task.FromResult(context.Compensated());
    }
}

public class ReserveInventoryActivity : StepActivity
{
    protected override string Name => "ReserveInventory";

    public override Task<ExecutionResult> Execute(ExecuteContext<StepArgs> context)
    {
        Log.Line($"  EXECUTE     {Name,-16} (produkuje zmienna ReservationId)");
        // Completed(log, variables): zmienne dopisuja sie do routing slipa i widza je KOLEJNE aktywnosci.
        var a = context.Arguments;
        return Task.FromResult(context.CompletedWithVariables(
            new StepLog(Name, a.OrderId, a.BreakCompensationAt == Name),
            new { ReservationId = "RES-" + a.OrderId }));
    }
}

public class AuthorizePaymentActivity : StepActivity { protected override string Name => "AuthorizePayment"; }
public class CreateShipmentActivity : StepActivity { protected override string Name => "CreateShipment"; }
public class NotifyCustomerActivity : StepActivity { protected override string Name => "NotifyCustomer"; }

// Konsument WSZYSTKICH zdarzen routing slipa (subskrypcja RoutingSlipEvents.All).
public class SlipEventsConsumer :
    IConsumer<RoutingSlipActivityCompleted>,
    IConsumer<RoutingSlipActivityFaulted>,
    IConsumer<RoutingSlipActivityCompensated>,
    IConsumer<RoutingSlipActivityCompensationFailed>,
    IConsumer<RoutingSlipCompleted>,
    IConsumer<RoutingSlipFaulted>,
    IConsumer<RoutingSlipCompensationFailed>
{
    public Task Consume(ConsumeContext<RoutingSlipActivityCompleted> c)
    { Log.Line($"  [event] ActivityCompleted           {c.Message.ActivityName}"); return Task.CompletedTask; }

    public Task Consume(ConsumeContext<RoutingSlipActivityFaulted> c)
    { Log.Line($"  [event] ActivityFaulted             {c.Message.ActivityName}: {c.Message.ExceptionInfo.Message}"); return Task.CompletedTask; }

    public Task Consume(ConsumeContext<RoutingSlipActivityCompensated> c)
    { Log.Line($"  [event] ActivityCompensated         {c.Message.ActivityName}"); return Task.CompletedTask; }

    public Task Consume(ConsumeContext<RoutingSlipActivityCompensationFailed> c)
    { Log.Line($"  [event] ActivityCompensationFailed  {c.Message.ActivityName}: {c.Message.ExceptionInfo.Message}"); return Task.CompletedTask; }

    public Task Consume(ConsumeContext<RoutingSlipCompleted> c)
    { Log.Line("  [event] RoutingSlipCompleted"); Outcome.Set("Completed"); return Task.CompletedTask; }

    public Task Consume(ConsumeContext<RoutingSlipFaulted> c)
    { Log.Line("  [event] RoutingSlipFaulted"); Outcome.Set("Faulted"); return Task.CompletedTask; }

    public Task Consume(ConsumeContext<RoutingSlipCompensationFailed> c)
    { Log.Line($"  [event] RoutingSlipCompensationFailed: {c.Message.ExceptionInfo.Message}"); Outcome.Set("CompensationFailed"); return Task.CompletedTask; }
}

public static class Outcome
{
    private static TaskCompletionSource<string> _tcs = new(TaskCreationOptions.RunContinuationsAsynchronously);
    public static void Reset() => _tcs = new(TaskCreationOptions.RunContinuationsAsynchronously);
    public static void Set(string s) => _tcs.TrySetResult(s);
    public static Task<string> Task => _tcs.Task;
}
