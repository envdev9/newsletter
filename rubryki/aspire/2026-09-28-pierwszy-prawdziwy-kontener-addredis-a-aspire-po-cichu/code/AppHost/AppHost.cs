var builder = DistributedApplication.CreateBuilder(args);

// AddRedis: prawdziwy kontener (obraz "redis:7-alpine" wg RedisContainerImageTags
// w Aspire 13.5.2), nie atrapa. Aspire sam zarządza cyklem życia kontenera
// (start przy StartAsync, zatrzymanie przy Dispose) i wystawia connection string.
var cache = builder.AddRedis("cache");

// WithReference(cache): wstrzykuje "ConnectionStrings:cache" do cache-api.
// WaitFor(cache): cache-api nie wystartuje, dopóki kontener Redis nie jest gotowy
// (to samo WaitFor + WithHttpHealthCheck co w wydaniu #3, tylko cel to kontener,
// nie inny projekt .NET).
var api = builder.AddProject<Projects.CacheApi>("cache-api")
    .WithReference(cache)
    .WaitFor(cache)
    .WithHttpHealthCheck("/health");

builder.Build().Run();
