using MassTransit;
using MassTransit.EntityFrameworkCoreIntegration;

namespace EfSagaDemo;
using Microsoft.EntityFrameworkCore;
using Microsoft.EntityFrameworkCore.Metadata.Builders;

public record OrderSubmitted(Guid OrderId);
public record PaymentReceived(Guid OrderId);
public record ItemPacked(Guid OrderId);

// Stan sagi = wiersz w tabeli. ISagaVersion => MassTransit zarzadza kolumna Version (optymistyczna wspolbieznosc).
public class OrderState : SagaStateMachineInstance, ISagaVersion
{
    public Guid CorrelationId { get; set; }
    public string CurrentState { get; set; } = "";
    public int Version { get; set; }
    public bool Paid { get; set; }
    public bool Packed { get; set; }
    public int EventsApplied { get; set; }   // licznik: kazdy zastosowany event +1 (wykrywa zgubione aktualizacje)
    public string Trail { get; set; } = "";  // slad: ktore eventy zostaly zastosowane
}

public class OrderStateMap : SagaClassMap<OrderState>
{
    public static bool UseXmin;
    protected override void Configure(EntityTypeBuilder<OrderState> entity, ModelBuilder model)
    {
        entity.Property(x => x.CurrentState).HasMaxLength(64);
        entity.Property(x => x.Trail).HasMaxLength(256);
        // Version jest tokenem wspolbieznosci: UPDATE ... WHERE CorrelationId=@id AND Version=@old
        entity.Property(x => x.Version).IsConcurrencyToken();
        // Wariant "xmin": systemowa kolumna PostgreSQL jako prawdziwy token (zmienia sie przy kazdym UPDATE).
        if (UseXmin) entity.Property<uint>("xmin").IsRowVersion();
    }
}

public class OrderDbContext : SagaDbContext
{
    public OrderDbContext(DbContextOptions<OrderDbContext> options) : base(options) { }
    protected override IEnumerable<ISagaClassMap> Configurations { get { yield return new OrderStateMap(); } }
}

public class OrderStateMachine : MassTransitStateMachine<OrderState>
{
    public static int WorkDelayMs = 300; // sztuczna "praca" w handlerze, zeby dwa eventy realnie sie nakladaly

    public State Submitted { get; private set; } = null!;
    public Event<OrderSubmitted> OrderSubmittedEvt { get; private set; } = null!;
    public Event<PaymentReceived> PaymentReceivedEvt { get; private set; } = null!;
    public Event<ItemPacked> ItemPackedEvt { get; private set; } = null!;

    public OrderStateMachine()
    {
        InstanceState(x => x.CurrentState);

        Event(() => OrderSubmittedEvt, e => e.CorrelateById(c => c.Message.OrderId));
        Event(() => PaymentReceivedEvt, e => e.CorrelateById(c => c.Message.OrderId));
        Event(() => ItemPackedEvt, e => e.CorrelateById(c => c.Message.OrderId));

        Initially(
            When(OrderSubmittedEvt)
                .Then(c => { c.Saga.EventsApplied++; c.Saga.Trail += "Submitted;"; })
                .TransitionTo(Submitted));

        During(Submitted,
            When(PaymentReceivedEvt)
                .ThenAsync(async c =>
                {
                    await Task.Delay(WorkDelayMs);
                    c.Saga.Paid = true; c.Saga.EventsApplied++; c.Saga.Trail += "Paid;";
                }),
            When(ItemPackedEvt)
                .ThenAsync(async c =>
                {
                    await Task.Delay(WorkDelayMs);
                    c.Saga.Packed = true; c.Saga.EventsApplied++; c.Saga.Trail += "Packed;";
                }));
    }
}
