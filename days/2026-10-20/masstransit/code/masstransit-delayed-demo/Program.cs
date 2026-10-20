using System.Diagnostics;
using DelayedDemo;
using MassTransit;
using Microsoft.Extensions.DependencyInjection;
using Microsoft.Extensions.Hosting;
using Microsoft.Extensions.Logging;

// Uzycie: dotnet <dll> run <immediate|delayed|delayed-plugin> [intervalSeconds]
//   immediate      - tylko UseMessageRetry(Immediate) (punkt odniesienia)
//   delayed        - UseDelayedRedelivery BEZ pluginu delayed-exchange i bez schedulera
//   delayed-plugin - UseDelayedRedelivery + UseDelayedMessageScheduler (wymaga pluginu rabbitmq_delayed_message_exchange)
//   inspect        - lista kolejek/exchange'y z REST API (do podgladu topologii)
var mode = args.Length > 0 ? args[0] : "run";
var variant = args.Length > 1 ? args[1] : "immediate";
var interval = args.Length > 2 ? int.Parse(args[2]) : 3;

if (mode == "clean")
{
    using var http = new HttpClient { BaseAddress = new Uri("http://127.0.0.1:56722/api/") };
    http.DefaultRequestHeaders.Authorization = new("Basic", Convert.ToBase64String("guest:guest"u8.ToArray()));
    foreach (var q in new[] { "delayed-demo-job", "delayed-demo-job_error", "delayed-demo-job_skipped" })
    {
        var r = await http.DeleteAsync($"queues/%2f/{q}");
        Console.WriteLine($"DELETE {q} -> {(int)r.StatusCode}");
    }
    return;
}

if (mode == "inspect")
{
    using var http = new HttpClient { BaseAddress = new Uri("http://127.0.0.1:56722/api/") };
    http.DefaultRequestHeaders.Authorization = new("Basic", Convert.ToBase64String("guest:guest"u8.ToArray()));
    foreach (var q in new[] { "queues", "exchanges" })
    {
        Console.WriteLine($"--- {q}");
        var json = await http.GetStringAsync(q);
        using var doc = System.Text.Json.JsonDocument.Parse(json);
        foreach (var e in doc.RootElement.EnumerateArray())
        {
            var name = e.GetProperty("name").GetString();
            if (string.IsNullOrEmpty(name) || name.StartsWith("amq.")) continue;
            var extra = q == "queues"
                ? $"ready={e.GetProperty("messages_ready").GetInt32()} consumers={e.GetProperty("consumers").GetInt32()}"
                : $"type={e.GetProperty("type").GetString()}";
            Console.WriteLine($"{name}  {extra}");
        }
    }
    return;
}

var clock = Stopwatch.StartNew();
var done = new TaskCompletionSource<bool>();

var builder = Host.CreateApplicationBuilder();
builder.Logging.SetMinimumLevel(LogLevel.Critical); // bez stack tracow; wlasne linie pokazuja przebieg
builder.Services.AddSingleton(done);
if (args.Length > 3) // 4. argument: HostOptions.ShutdownTimeout w sekundach (domyslnie 30 s w Generic Host)
    builder.Services.Configure<HostOptions>(o => o.ShutdownTimeout = TimeSpan.FromSeconds(int.Parse(args[3])));
builder.Services.AddMassTransit(x =>
{
    x.AddConsumer<FlakyConsumer>(c =>
    {
        if (variant == "interval") c.UseMessageRetry(r => r.Interval(2, TimeSpan.FromSeconds(interval)));
        else c.UseMessageRetry(r => r.Immediate(1));
    });
    x.UsingRabbitMq((ctx, cfg) =>
    {
        cfg.Host("127.0.0.1", 56721, "/", h => { h.Username("guest"); h.Password("guest"); });
        if (variant == "delayed-plugin") cfg.UseDelayedMessageScheduler();
        if (variant != "immediate")
            cfg.UseDelayedRedelivery(r => r.Intervals(TimeSpan.FromSeconds(interval), TimeSpan.FromSeconds(interval * 2)));
        cfg.ReceiveEndpoint("delayed-demo-job", e =>
        {
            e.PrefetchCount = 1;
            e.ConcurrentMessageLimit = 1; // jeden slot - widac, kto blokuje kogo
            e.ConfigureConsumer<FlakyConsumer>(ctx);
        });
    });
});
builder.Services.AddSingleton(clock);

using var host = builder.Build();
Console.WriteLine($"variant={variant} interval={interval}s");
await host.StartAsync();
var bus = host.Services.GetRequiredService<IPublishEndpoint>();
FlakyConsumer.SucceedAtAttempt = variant == "interval" ? 3 : 5;
await bus.Publish(new Job("job-1"));
await bus.Publish(new Job("job-2")); // zdrowa wiadomosc tuz za pechowa
Console.WriteLine($"[{clock.Elapsed.TotalSeconds,5:F1}s] published job-1, job-2");

var winner = await Task.WhenAny(done.Task, Task.Delay(TimeSpan.FromSeconds(30)));
Console.WriteLine(winner == done.Task
    ? $"[{clock.Elapsed.TotalSeconds,5:F1}s] DONE"
    : $"[{clock.Elapsed.TotalSeconds,5:F1}s] TIMEOUT (30s) - job nie zakonczony");
await Task.Delay(1500); // zeby zdazyl sie wypisac job-2, jesli czeka
var stopStart = clock.Elapsed;
await host.StopAsync();
Console.WriteLine($"[{clock.Elapsed.TotalSeconds,5:F1}s] host.StopAsync trwal {(clock.Elapsed - stopStart).TotalSeconds:F1}s");

namespace DelayedDemo
{
public record Job(string Id);

public class FlakyConsumer(Stopwatch clock, TaskCompletionSource<bool> done) : IConsumer<Job>
{
    // job-1 pada do proby SucceedAtAttempt-1, potem przechodzi; job-2 zawsze przechodzi.
    public static int SucceedAtAttempt = 5;
    private static int _attempt;

    public Task Consume(ConsumeContext<Job> context)
    {
        var healthy = context.Message.Id != "job-1";
        var n = healthy ? 1 : Interlocked.Increment(ref _attempt);
        var hdrs = string.Join(",", context.Headers.GetAll().Select(h => h.Key).Where(k => k.StartsWith("MT-Redelivery") || k.StartsWith("MT-Fault")));
        Console.WriteLine($"[{clock.Elapsed.TotalSeconds,5:F1}s] {context.Message.Id} attempt #{n} headers=[{hdrs}]");
        if (!healthy && n < SucceedAtAttempt) throw new InvalidOperationException($"boom #{n}");
        if (!healthy) done.TrySetResult(true);
        return Task.CompletedTask;
    }
}
}
