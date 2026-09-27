using MassTransit;
using MassTransitRoutingDemo;
using Microsoft.Extensions.DependencyInjection;
using Microsoft.Extensions.Hosting;
using Microsoft.Extensions.Logging;

var builder = Host.CreateApplicationBuilder(args);
builder.Logging.SetMinimumLevel(LogLevel.Warning);
builder.Logging.AddFilter("MassTransit", LogLevel.Critical);

builder.Services.AddScoped(typeof(TimingConsumeFilter<>));
builder.Services.AddScoped(typeof(TraceSendFilter<>));

builder.Services.AddMassTransit(x =>
{
    // Konwencja nazw kolejek: kebab-case z prefiksem "dev"
    x.SetEndpointNameFormatter(new KebabCaseEndpointNameFormatter("dev", includeNamespace: false));

    x.AddConsumer<PriceConsumer>();
    x.AddConsumer<PingConsumer, PingConsumerDefinition>();

    x.UsingInMemory((context, cfg) =>
    {
        cfg.UseSendFilter(typeof(TraceSendFilter<>), context);
        cfg.UseConsumeFilter(typeof(TimingConsumeFilter<>), context);
        cfg.ConfigureEndpoints(context);
    });
});

using var host = builder.Build();
await host.StartAsync();

var bus = host.Services.GetRequiredService<IBus>();

// --- 1. Topologia: jak ConfigureEndpoints nazwał kolejki ---
Console.WriteLine("=== 1. Nazwy kolejek wg EndpointNameFormatter / ConsumerDefinition ===");
var fmt = new KebabCaseEndpointNameFormatter("dev", false);
Log.Line($"formatter dla PriceConsumer -> {fmt.Consumer<PriceConsumer>()}");
Log.Line($"formatter dla PingConsumer  -> {fmt.Consumer<PingConsumer>()} (ale definicja nadpisuje nazwę)");
await bus.Publish(new Ping("cześć"));
await Task.Delay(300);

// --- 2. Request/Response ---
Console.WriteLine();
Console.WriteLine("=== 2. Request/Response: dwa typy odpowiedzi (Response<A, B>) ===");
var client = host.Services.CreateScope().ServiceProvider.GetRequiredService<IRequestClient<GetPrice>>();
foreach (var sku in new[] { "ABC-1", "NOPE" })
{
    var (ok, notFound) = await client.GetResponse<PriceResult, SkuNotFound>(new GetPrice(sku));
    if (ok.IsCompletedSuccessfully)
        Log.Line($"odpowiedź: {(await ok).Message.Sku} kosztuje {(await ok).Message.Price} zł");
    else
        Log.Line($"odpowiedź: SkuNotFound {(await notFound).Message.Sku}");
}

// --- 3. Wyjątek w konsumencie -> RequestFaultException po stronie klienta ---
Console.WriteLine();
Console.WriteLine("=== 3. Wyjątek w konsumencie propaguje się do klienta ===");
try
{
    await client.GetResponse<PriceResult>(new GetPrice("BOOM"));
}
catch (RequestFaultException ex)
{
    Log.Line($"klient złapał {ex.GetType().Name}: {ex.Fault?.Exceptions.FirstOrDefault()?.Message}");
}

// --- 4. Brak konsumenta -> timeout ---
Console.WriteLine();
Console.WriteLine("=== 4. Brak konsumenta: RequestTimeoutException ===");
var stockClient = bus.CreateRequestClient<GetStock>(RequestTimeout.After(s: 1));
try
{
    await stockClient.GetResponse<PriceResult>(new GetStock("ABC-1"));
}
catch (RequestTimeoutException ex)
{
    Log.Line($"klient złapał {ex.GetType().Name}");
}

// --- 5. Send do kolejki po adresie ---
Console.WriteLine();
Console.WriteLine("=== 5. Send po adresie: kolejka pod nazwą z ConsumerDefinition; filtr Send widzi wiadomość ===");
var ep = await bus.GetSendEndpoint(new Uri("queue:pings-special"));
await ep.Send(new Ping("prosto do pings-special"));
await Task.Delay(300);

Console.WriteLine();
Console.WriteLine("Koniec.");
await host.StopAsync();
