var builder = WebApplication.CreateBuilder(args);

var rawConnectionString = builder.Configuration.GetConnectionString("cache");

builder.AddRedisClient(connectionName: "cache");

var app = builder.Build();

app.MapGet("/health", () => "Healthy");

app.MapPut("/cache/{key}", async (string key, HttpRequest req, StackExchange.Redis.IConnectionMultiplexer mux) =>
{
    using var reader = new StreamReader(req.Body);
    var value = await reader.ReadToEndAsync();
    await mux.GetDatabase().StringSetAsync(key, value);
    return Results.Ok(new { key, written = value.Length });
});

app.MapGet("/cache/{key}", async (string key, StackExchange.Redis.IConnectionMultiplexer mux) =>
{
    var value = await mux.GetDatabase().StringGetAsync(key);
    return value.IsNull ? Results.NotFound() : Results.Ok(new { key, value = (string)value! });
});

// Kształt connection stringa (nigdy wartość hasła) + realne PING-owalne połączenie.
app.MapGet("/cache-info", (StackExchange.Redis.IConnectionMultiplexer mux) =>
{
    var server = mux.GetServer(mux.GetEndPoints().First());
    return Results.Ok(new
    {
        isConnected = mux.IsConnected,
        role = server.IsReplica ? "replica" : "master",
        connectionHasPassword = rawConnectionString?.Contains("password=", StringComparison.OrdinalIgnoreCase) ?? false,
        connectionHasSsl = rawConnectionString?.Contains("ssl=true", StringComparison.OrdinalIgnoreCase) ?? false,
    });
});

app.Run();
