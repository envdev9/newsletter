var builder = WebApplication.CreateBuilder(args);

// Zanim AddRedisClient go skonsumuje, zapamiętujemy KSZTAŁT connection stringa
// (nigdy wartość hasła) - to samo, co w wydaniu #5 (2026-09-28), żeby test mógł
// uczciwie sprawdzić, co Aspire naprawdę wstrzyknęło pod "ConnectionStrings:cache".
var rawConnectionString = builder.Configuration.GetConnectionString("cache");

builder.AddRedisClient(connectionName: "cache");

var app = builder.Build();

app.MapGet("/health", () => "Healthy");

app.MapPut("/cache/{key}", async (string key, HttpRequest req, StackExchange.Redis.IConnectionMultiplexer mux) =>
{
    using var reader = new StreamReader(req.Body);
    var value = await reader.ReadToEndAsync();
    var db = mux.GetDatabase();
    await db.StringSetAsync(key, value);
    return Results.Ok(new { key, written = value.Length });
});

app.MapGet("/cache/{key}", async (string key, StackExchange.Redis.IConnectionMultiplexer mux) =>
{
    var db = mux.GetDatabase();
    var value = await db.StringGetAsync(key);
    return value.IsNull ? Results.NotFound() : Results.Ok(new { key, value = (string)value! });
});

// Dowód, że to NAPRAWDĘ Redis, nie atrapa w pamięci: PING przez samego klienta.
app.MapGet("/cache-info", (StackExchange.Redis.IConnectionMultiplexer mux) =>
{
    var endpoint = mux.GetEndPoints().First();
    var server = mux.GetServer(endpoint);
    return Results.Ok(new
    {
        endpoint = server.EndPoint.ToString(),
        isConnected = mux.IsConnected,
        role = server.IsReplica ? "replica" : "master",
        connectionHasPassword = rawConnectionString?.Contains("password=", StringComparison.OrdinalIgnoreCase) ?? false,
        connectionHasSsl = rawConnectionString?.Contains("ssl=true", StringComparison.OrdinalIgnoreCase) ?? false,
    });
});

app.Run();
