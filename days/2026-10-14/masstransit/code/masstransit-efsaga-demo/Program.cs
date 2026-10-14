using MassTransit;
using Microsoft.EntityFrameworkCore;
using Microsoft.Extensions.DependencyInjection;
using Microsoft.Extensions.Hosting;
using Microsoft.Extensions.Logging;
using EfSagaDemo;

// Uzycie:
//   submit <db> <orderId>                       - proces A: publikuje OrderSubmitted, czeka na wiersz w bazie, konczy sie
//   pay    <db> <orderId>                       - proces B (NOWY proces): publikuje PaymentReceived do sagi z bazy
//   race   <db> <optimistic|pessimistic> <retry|noretry> - dwa eventy naraz na tej samej sadze
//   show   <db>                                 - wypisuje tabele OrderState
if (args.Length < 2) { Console.WriteLine("uzycie: submit|pay|race|show <db> ..."); return 1; }
var mode = args[0];
var dbPath = Path.GetFullPath(args[1]);

if (mode == "show") { await PrintRows(dbPath); return 0; }

var concurrency = ConcurrencyMode.Optimistic;
var retry = false;
if (mode == "race")
{
    concurrency = args[2] == "pessimistic" ? ConcurrencyMode.Pessimistic : ConcurrencyMode.Optimistic;
    retry = args[3] == "retry";
}

var builder = Host.CreateApplicationBuilder();
builder.Logging.SetMinimumLevel(LogLevel.Warning);
builder.Services.AddOptions<MassTransitHostOptions>().Configure(o => o.WaitUntilStarted = true);
builder.Services.AddDbContext<OrderDbContext>(o => o.UseSqlite($"Data Source={dbPath}"));
builder.Services.AddMassTransit(x =>
{
    x.AddConsumer<FaultPrinter<PaymentReceived>>();
    x.AddConsumer<FaultPrinter<ItemPacked>>();
    x.AddSagaStateMachine<OrderStateMachine, OrderState>()
        .EntityFrameworkRepository(r =>
        {
            r.ConcurrencyMode = concurrency;
            r.ExistingDbContext<OrderDbContext>();
            // Pessimistic na SQLite: patrz ARTICLE.md - wynik zmierzony tam.
        });
    x.UsingInMemory((ctx, cfg) =>
    {
        if (retry) cfg.UseMessageRetry(r => r.Immediate(5));
        cfg.ConfigureEndpoints(ctx);
    });
});

var host = builder.Build();
using (var scope = host.Services.CreateScope())
    await scope.ServiceProvider.GetRequiredService<OrderDbContext>().Database.EnsureCreatedAsync();

Console.WriteLine($"pid={Environment.ProcessId} mode={mode} concurrency={concurrency} retry={retry}");
await host.StartAsync();
var bus = host.Services.GetRequiredService<IBus>();

switch (mode)
{
    case "submit":
    {
        var id = Guid.Parse(args[2]);
        await bus.Publish(new OrderSubmitted(id));
        await WaitFor(dbPath, id, s => s.CurrentState == "Submitted", 5000);
        break;
    }
    case "pay":
    {
        var id = Guid.Parse(args[2]);
        await bus.Publish(new PaymentReceived(id));
        await WaitFor(dbPath, id, s => s.Paid, 5000);
        break;
    }
    case "race":
    {
        var id = Guid.NewGuid();
        await bus.Publish(new OrderSubmitted(id));
        await WaitFor(dbPath, id, s => s.CurrentState == "Submitted", 5000);
        Console.WriteLine("--- dwa eventy naraz na tej samej sadze ---");
        await Task.WhenAll(bus.Publish(new PaymentReceived(id)), bus.Publish(new ItemPacked(id)));
        await Task.Delay(4000); // czas na ewentualne retry
        break;
    }
}

await host.StopAsync();
await PrintRows(dbPath);
return 0;

static async Task WaitFor(string db, Guid id, Func<OrderState, bool> pred, int timeoutMs)
{
    var until = DateTime.UtcNow.AddMilliseconds(timeoutMs);
    while (DateTime.UtcNow < until)
    {
        await using var ctx = Open(db);
        var s = await ctx.Set<OrderState>().AsNoTracking().FirstOrDefaultAsync(x => x.CorrelationId == id);
        if (s != null && pred(s)) return;
        await Task.Delay(100);
    }
    Console.WriteLine("TIMEOUT: warunek nie spelniony w " + timeoutMs + " ms");
}

static OrderDbContext Open(string db) =>
    new(new DbContextOptionsBuilder<OrderDbContext>().UseSqlite($"Data Source={db}").Options);

static async Task PrintRows(string db)
{
    await using var ctx = Open(db);
    Console.WriteLine("OrderState w bazie:");
    foreach (var s in await ctx.Set<OrderState>().AsNoTracking().ToListAsync())
        Console.WriteLine($"  {s.CorrelationId.ToString()[..8]} state={s.CurrentState} version={s.Version} paid={s.Paid} packed={s.Packed} eventsApplied={s.EventsApplied} trail={s.Trail}");
}

public class FaultPrinter<T> : IConsumer<Fault<T>> where T : class
{
    public Task Consume(ConsumeContext<Fault<T>> context)
    {
        var e = context.Message.Exceptions.FirstOrDefault();
        Console.WriteLine($"FAULT<{typeof(T).Name}>: {e?.ExceptionType} ; {Short(e?.Message)}");
        return Task.CompletedTask;
    }
    static string Short(string? s) => s is null ? "" : (s.Length > 140 ? s[..140] + "..." : s);
}
