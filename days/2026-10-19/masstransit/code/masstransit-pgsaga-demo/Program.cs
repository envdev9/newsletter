using MassTransit;
using MassTransit.EntityFrameworkCoreIntegration;
using Microsoft.EntityFrameworkCore;
using Microsoft.Extensions.DependencyInjection;
using Microsoft.Extensions.Hosting;
using Microsoft.Extensions.Logging;
using EfSagaDemo;

// Uzycie (polaczenie: zmienna MT_PG, domyslnie lokalny kontener z README; dopisany na koncu argument `sql` loguje SQL sagi):
//   reset                                              - czysci tabele sagi
//   submit <orderId>                                   - proces A: publikuje OrderSubmitted, czeka na wiersz, konczy sie
//   pay    <orderId>                                   - NOWY proces: PaymentReceived do sagi z bazy
//   race   <optimistic|pessimistic> <retry|noretry>    - dwa eventy naraz na tej samej sadze
//   show                                               - wypisuje tabele
if (args.Length < 1) { Console.WriteLine("uzycie: reset|submit|pay|race|show ..."); return 1; }
var mode = args[0];
var conn = Environment.GetEnvironmentVariable("MT_PG")
           ?? "Host=127.0.0.1;Port=55432;Username=postgres;Password=demo;Database=postgres;Maximum Pool Size=20";
var logSql = args.Contains("sql");

if (mode == "show") { await PrintRows(conn); return 0; }

var concurrency = ConcurrencyMode.Optimistic;
var retry = false;
if (mode == "race")
{
    concurrency = args[1] == "pessimistic" ? ConcurrencyMode.Pessimistic : ConcurrencyMode.Optimistic;
    retry = args[2] == "retry";
}

var builder = Host.CreateApplicationBuilder();
builder.Logging.SetMinimumLevel(LogLevel.Warning);
builder.Logging.AddFilter("Microsoft.EntityFrameworkCore", LogLevel.None); // bez halasu EF (wyjatek i tak widac w MassTransit)
if (logSql) builder.Logging.AddFilter("Microsoft.EntityFrameworkCore.Database.Command", LogLevel.Information);
OrderStateMap.UseXmin = args.Contains("xmin");
builder.Services.AddOptions<MassTransitHostOptions>().Configure(o => o.WaitUntilStarted = true);
builder.Services.AddDbContext<OrderDbContext>(o => o.UseNpgsql(conn));
builder.Services.AddMassTransit(x =>
{
    x.AddConsumer<FaultPrinter<PaymentReceived>>();
    x.AddConsumer<FaultPrinter<ItemPacked>>();
    x.AddSagaStateMachine<OrderStateMachine, OrderState>()
        .EntityFrameworkRepository(r =>
        {
            r.ConcurrencyMode = concurrency;
            // Pessimistic wymaga dialektu: bez tego MassTransit nie wie, jak zalozyc blokade wiersza.
            r.LockStatementProvider = new PostgresLockStatementProvider();
            if (args.Contains("readcommitted")) r.IsolationLevel = System.Data.IsolationLevel.ReadCommitted;
            r.ExistingDbContext<OrderDbContext>();
        });
    x.UsingInMemory((ctx, cfg) =>
    {
        if (retry) cfg.UseMessageRetry(r => r.Immediate(5));
        cfg.ConfigureEndpoints(ctx);
    });
});

var host = builder.Build();
using (var scope = host.Services.CreateScope())
{
    var db = scope.ServiceProvider.GetRequiredService<OrderDbContext>();
    await db.Database.EnsureCreatedAsync();
    if (mode == "reset") { await db.Database.ExecuteSqlRawAsync("TRUNCATE TABLE \"OrderState\""); Console.WriteLine("tabela wyczyszczona"); return 0; }
}

Console.WriteLine($"pid={Environment.ProcessId} mode={mode} concurrency={concurrency} retry={retry}");
await host.StartAsync();
var bus = host.Services.GetRequiredService<IBus>();

switch (mode)
{
    case "submit":
    {
        var id = Guid.Parse(args[1]);
        await bus.Publish(new OrderSubmitted(id));
        await WaitFor(conn, id, s => s.CurrentState == "Submitted", 5000);
        break;
    }
    case "pay":
    {
        var id = Guid.Parse(args[1]);
        await bus.Publish(new PaymentReceived(id));
        await WaitFor(conn, id, s => s.Paid, 5000);
        break;
    }
    case "race":
    {
        var id = Guid.NewGuid();
        await bus.Publish(new OrderSubmitted(id));
        await WaitFor(conn, id, s => s.CurrentState == "Submitted", 5000);
        Console.WriteLine("--- dwa eventy naraz na tej samej sadze ---");
        await Task.WhenAll(bus.Publish(new PaymentReceived(id)), bus.Publish(new ItemPacked(id)));
        await Task.Delay(4000); // czas na ewentualne retry
        break;
    }
}

await host.StopAsync();
await PrintRows(conn);
return 0;

static async Task WaitFor(string conn, Guid id, Func<OrderState, bool> pred, int timeoutMs)
{
    var until = DateTime.UtcNow.AddMilliseconds(timeoutMs);
    while (DateTime.UtcNow < until)
    {
        await using var ctx = Open(conn);
        var s = await ctx.Set<OrderState>().AsNoTracking().FirstOrDefaultAsync(x => x.CorrelationId == id);
        if (s != null && pred(s)) return;
        await Task.Delay(100);
    }
    Console.WriteLine("TIMEOUT: warunek nie spelniony w " + timeoutMs + " ms");
}

static OrderDbContext Open(string conn) =>
    new(new DbContextOptionsBuilder<OrderDbContext>().UseNpgsql(conn).Options);

static async Task PrintRows(string conn)
{
    await using var ctx = Open(conn);
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
