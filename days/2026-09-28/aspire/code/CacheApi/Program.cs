var builder = WebApplication.CreateBuilder(args);

// Zanim AddRedisClient go skonsumuje, zapamiętujemy KSZTAŁT connection stringa
// (nigdy wartość hasła) - żeby w /cache-info uczciwie pokazać, co Aspire naprawdę
// wstrzyknął pod "ConnectionStrings:cache".
var rawConnectionString = builder.Configuration.GetConnectionString("cache");

// Aspire.StackExchange.Redis: rejestruje IConnectionMultiplexer skonfigurowany
// connection stringiem, który Aspire wstrzyknął przez WithReference(cache)
// (klucz konfiguracji "ConnectionStrings:cache" - nazwa musi zgadzać się
// z nazwą zasobu podaną w AddRedis("cache") w AppHost).
builder.AddRedisClient(connectionName: "cache");

var app = builder.Build();

app.MapGet("/health", () => "Healthy");

// Zapis: PUT /cache/{key} z treścią w body (surowy string).
app.MapPut("/cache/{key}", async (string key, HttpRequest req, StackExchange.Redis.IConnectionMultiplexer mux) =>
{
    using var reader = new StreamReader(req.Body);
    var value = await reader.ReadToEndAsync();
    var db = mux.GetDatabase();
    await db.StringSetAsync(key, value);
    return Results.Ok(new { key, written = value.Length });
});

// Odczyt: GET /cache/{key} - zwraca wartość albo 404, jeśli klucza nie ma.
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
        // Kształt connection stringa, który Aspire wstrzyknął - BEZ wartości hasła.
        connectionHasPassword = rawConnectionString?.Contains("password=", StringComparison.OrdinalIgnoreCase) ?? false,
        connectionHasSsl = rawConnectionString?.Contains("ssl=true", StringComparison.OrdinalIgnoreCase) ?? false,
    });
});

app.Run();
