var builder = DistributedApplication.CreateBuilder(args);

// Ten sam AppHost co w #14, z JEDNĄ zmianą: Redis jest "trwały".
// Domyślnie (ContainerLifetime.Session) kontener ginie razem z AppHostem.
// Persistent = kontener ma PRZEŻYĆ AppHosta i zostać ponownie użyty przy następnym starcie.
// Parametr "persistent" (argument "Persistent=false") pozwala w probe'ie porównać oba tryby.
var persistent = !string.Equals(builder.Configuration["Persistent"], "false", StringComparison.OrdinalIgnoreCase);

var cache = builder.AddRedis("cache");
if (persistent)
{
    cache.WithLifetime(ContainerLifetime.Persistent);
}

builder.AddProject<Projects.CacheApi>("cache-api")
    .WithReference(cache)
    .WaitFor(cache)
    .WithHttpHealthCheck("/health");

builder.Build().Run();
