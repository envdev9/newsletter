var builder = WebApplication.CreateBuilder(args);

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

app.Run();
