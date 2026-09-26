using MassTransit;

namespace MassTransitSagaDemo;

// ---- Kontrakty (eventy i komendy) - wszystkie niosą OrderId jako klucz korelacji ----
public record OrderSubmitted(Guid OrderId, decimal Amount);
public record PaymentReceived(Guid OrderId);
public record StockReserved(Guid OrderId);
public record PaymentExpired(Guid OrderId);          // wiadomość-timeout (Schedule)
public record ShipOrder(Guid OrderId);               // komenda publikowana przez sagę
public record ShipmentDispatched(Guid OrderId);
public record OrderCompleted(Guid OrderId);
public record OrderCancelled(Guid OrderId, string Reason);

// ---- Stan sagi: jeden wiersz na zamówienie ----
public class OrderState : SagaStateMachineInstance
{
    public Guid CorrelationId { get; set; }          // = OrderId
    public string CurrentState { get; set; } = "";   // nazwa stanu (string - najprostsza persystencja)
    public decimal Amount { get; set; }
    public int ReadyFlags { get; set; }              // bitmapa composite eventu
    public Guid? PaymentTimeoutTokenId { get; set; } // token zaplanowanego timeoutu
}

public class OrderStateMachine : MassTransitStateMachine<OrderState>
{
    public OrderStateMachine()
    {
        // Który property instancji trzyma nazwę stanu
        InstanceState(x => x.CurrentState);

        // Korelacja: wiadomość -> instancja sagi (po OrderId)
        Event(() => OrderSubmitted,   e => e.CorrelateById(m => m.Message.OrderId));
        Event(() => PaymentReceived,  e => e.CorrelateById(m => m.Message.OrderId));
        Event(() => StockReserved,    e => e.CorrelateById(m => m.Message.OrderId));
        Event(() => ShipmentDispatched, e => e.CorrelateById(m => m.Message.OrderId));

        // Schedule = timeout jako zaplanowana wiadomość
        Schedule(() => PaymentTimeout, x => x.PaymentTimeoutTokenId, s =>
        {
            s.Delay = TimeSpan.FromSeconds(1.5);
            s.Received = r => r.CorrelateById(m => m.Message.OrderId);
        });

        // Composite: odpali się, gdy wystąpią OBA eventy - w dowolnej kolejności
        CompositeEvent(() => ReadyToShip, x => x.ReadyFlags, PaymentReceived, StockReserved);

        Initially(
            When(OrderSubmitted)
                .Then(c =>
                {
                    c.Saga.Amount = c.Message.Amount;
                    Log.Line($"saga {Short(c.Saga.CorrelationId)}: OrderSubmitted ({c.Message.Amount} zł) -> Submitted, start timeoutu");
                })
                .Schedule(PaymentTimeout, c => new PaymentExpired(c.Saga.CorrelationId))
                .TransitionTo(Submitted));

        During(Submitted,
            When(PaymentReceived)
                .Unschedule(PaymentTimeout)
                .Then(c => Log.Line($"saga {Short(c.Saga.CorrelationId)}: PaymentReceived (stan przed: {c.Saga.CurrentState}), timeout odwołany"))
                // UWAGA: handler składnika composite'u wykonuje się PO tym, jak composite już
                // przeniósł sagę do Shipping - bez tego guardu nadpisalibyśmy Shipping -> Paid.
                .If(c => c.Saga.CurrentState != nameof(Shipping), x => x.TransitionTo(Paid)),
            When(PaymentTimeout.Received)
                .Then(c => Log.Line($"saga {Short(c.Saga.CorrelationId)}: TIMEOUT - brak płatności -> Cancelled"))
                .Publish(c => new OrderCancelled(c.Saga.CorrelationId, "brak płatności w terminie"))
                .TransitionTo(Cancelled));

        // Stock może przyjść przed albo po płatności - obsługujemy w obu stanach
        During(Submitted, Paid,
            When(StockReserved)
                .Then(c => Log.Line($"saga {Short(c.Saga.CorrelationId)}: StockReserved (stan: {c.Saga.CurrentState})")));

        // Composite event: dla obu stanów, w których mogą wpadać jego składniki
        During(Submitted, Paid,
            When(ReadyToShip)
                .Then(c => Log.Line($"saga {Short(c.Saga.CorrelationId)}: composite ReadyToShip (płatność + stock) -> Shipping"))
                .Publish(c => new ShipOrder(c.Saga.CorrelationId))
                .TransitionTo(Shipping));

        During(Shipping,
            When(ShipmentDispatched)
                .Then(c => Log.Line($"saga {Short(c.Saga.CorrelationId)}: ShipmentDispatched -> koniec"))
                .Publish(c => new OrderCompleted(c.Saga.CorrelationId))
                .Finalize());

        // Spóźniona płatność/timeout po anulowaniu: świadomie ignorujemy (bez tego - błąd "event w złym stanie")
        During(Cancelled,
            Ignore(PaymentReceived),
            Ignore(StockReserved));

        // Finally = uruchamia się przy wejściu w stan Final (tu: po Finalize)
        Finally(f => f
            .Then(c => Log.Line($"saga {Short(c.Saga.CorrelationId)}: Finally - sprzątanie")));

        // Usuwamy instancję z repozytorium po zakończeniu
        SetCompletedWhenFinalized();
    }

    static string Short(Guid id) => id.ToString()[..8];

    public State Submitted { get; private set; } = null!;
    public State Paid { get; private set; } = null!;
    public State Shipping { get; private set; } = null!;
    public State Cancelled { get; private set; } = null!;

    public Event<OrderSubmitted> OrderSubmitted { get; private set; } = null!;
    public Event<PaymentReceived> PaymentReceived { get; private set; } = null!;
    public Event<StockReserved> StockReserved { get; private set; } = null!;
    public Event<ShipmentDispatched> ShipmentDispatched { get; private set; } = null!;
    public Event ReadyToShip { get; private set; } = null!;

    public Schedule<OrderState, PaymentExpired> PaymentTimeout { get; private set; } = null!;
}

// Zwykły consumer - "magazyn wysyłkowy", reaguje na komendę z sagi
public class ShipOrderConsumer : IConsumer<ShipOrder>
{
    public async Task Consume(ConsumeContext<ShipOrder> context)
    {
        Log.Line($"magazyn: pakuję i wysyłam {context.Message.OrderId.ToString()[..8]}");
        await context.Publish(new ShipmentDispatched(context.Message.OrderId));
    }
}

// Obserwator eventów wynikowych (żeby zobaczyć, co saga opublikowała)
public class OutcomeConsumer : IConsumer<OrderCompleted>, IConsumer<OrderCancelled>
{
    public Task Consume(ConsumeContext<OrderCompleted> context)
    {
        Log.Line($"[wynik] OrderCompleted {context.Message.OrderId.ToString()[..8]}");
        return Task.CompletedTask;
    }

    public Task Consume(ConsumeContext<OrderCancelled> context)
    {
        Log.Line($"[wynik] OrderCancelled {context.Message.OrderId.ToString()[..8]}: {context.Message.Reason}");
        return Task.CompletedTask;
    }
}

// Saga, która dostaje event w złym stanie, publikuje Fault<T> - jak zwykły consumer
public class SagaFaultConsumer : IConsumer<Fault<ShipmentDispatched>>
{
    public Task Consume(ConsumeContext<Fault<ShipmentDispatched>> context)
    {
        var ex = context.Message.Exceptions.First();
        Log.Line($"[Fault<ShipmentDispatched>] {ex.ExceptionType}: {ex.InnerException?.Message ?? ex.Message}");
        return Task.CompletedTask;
    }
}

public static class Log
{
    static readonly System.Diagnostics.Stopwatch Sw = System.Diagnostics.Stopwatch.StartNew();
    public static void Line(string text) => Console.WriteLine($"[{Sw.ElapsedMilliseconds,5} ms] {text}");
}
