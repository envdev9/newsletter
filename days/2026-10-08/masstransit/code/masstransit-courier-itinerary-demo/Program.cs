using MassTransit;
using MassTransit.Courier.Contracts;
using MassTransitCourierItinerary;
using Microsoft.Extensions.DependencyInjection;
using Microsoft.Extensions.Hosting;
using Microsoft.Extensions.Logging;

// Uzycie: dotnet run -- <ok|fail|fail-comp>
//   ok        - 4 aktywnosci, wszystkie sie koncza
//   fail      - NotifyCustomer (4.) rzuca; kompensacje 3 poprzednich w odwrotnej kolejnosci
//   fail-comp - NotifyCustomer rzuca, a kompensacja AuthorizePayment (2.) zawodzi
var scenario = args.Length > 0 ? args[0] : "ok";
var failAt = scenario is "fail" or "fail-comp" ? "NotifyCustomer" : "";
var breakCompAt = scenario == "fail-comp" ? "AuthorizePayment" : "";

Console.WriteLine($"=== COURIER {scenario.ToUpperInvariant()}: ReserveInventory -> AuthorizePayment -> CreateShipment -> NotifyCustomer ===");

var builder = Host.CreateApplicationBuilder();
builder.Logging.SetMinimumLevel(LogLevel.Warning);
builder.Logging.AddFilter("MassTransit", LogLevel.Critical);
builder.Services.AddMassTransit(x =>
{
    x.SetEndpointNameFormatter(KebabCaseEndpointNameFormatter.Instance);
    x.AddConsumer<SlipEventsConsumer>();
    x.AddActivity<ReserveInventoryActivity, StepArgs, StepLog>();
    x.AddActivity<AuthorizePaymentActivity, StepArgs, StepLog>();
    x.AddActivity<CreateShipmentActivity, StepArgs, StepLog>();
    x.AddActivity<NotifyCustomerActivity, StepArgs, StepLog>();
    x.UsingInMemory((context, cfg) => cfg.ConfigureEndpoints(context));
});

using var host = builder.Build();
await host.StartAsync();

var bus = host.Services.GetRequiredService<IBus>();
var fmt = host.Services.GetRequiredService<IEndpointNameFormatter>();
Uri Exec<TActivity>() where TActivity : class, IActivity<StepArgs, StepLog>
    => new($"queue:{fmt.ExecuteActivity<TActivity, StepArgs>()}");

var orderId = "ORD-1";
var slip = new RoutingSlipBuilder(Guid.NewGuid());
slip.AddSubscription(new Uri($"queue:{fmt.Consumer<SlipEventsConsumer>()}"), RoutingSlipEvents.All);

// ReservationId celowo POMIJAMY w argumentach - dopelni go zmienna zapisana przez ReserveInventory.
slip.AddActivity("ReserveInventory", Exec<ReserveInventoryActivity>(), new { OrderId = orderId, FailAt = failAt, BreakCompensationAt = breakCompAt });
slip.AddActivity("AuthorizePayment", Exec<AuthorizePaymentActivity>(), new { OrderId = orderId, FailAt = failAt, BreakCompensationAt = breakCompAt });
slip.AddActivity("CreateShipment", Exec<CreateShipmentActivity>(), new { OrderId = orderId, FailAt = failAt, BreakCompensationAt = breakCompAt });
slip.AddActivity("NotifyCustomer", Exec<NotifyCustomerActivity>(), new { OrderId = orderId, FailAt = failAt, BreakCompensationAt = breakCompAt });

Outcome.Reset();
await bus.Execute(slip.Build());

var winner = await Task.WhenAny(Outcome.Task, Task.Delay(TimeSpan.FromSeconds(5)));
Log.Line(winner == Outcome.Task ? $"WYNIK koncowy slipa: {Outcome.Task.Result}" : "WYNIK: brak zdarzenia koncowego w 5 s");
await Task.Delay(500); // zdarzenia ActivityCompensated moga dojsc po koncowym
await host.StopAsync();
