var builder = DistributedApplication.CreateBuilder(args);

// Ten sam AppHost co w wydaniu #12: jeden Redis (prawdziwy kontener) + CacheApi.
// Dziś temat to nie AppHost, tylko CYKL ŻYCIA jego instancji pod TUnit -
// patrz Cache.AppHostTests/.
var cache = builder.AddRedis("cache");

builder.AddProject<Projects.CacheApi>("cache-api")
    .WithReference(cache)
    .WaitFor(cache)
    .WithHttpHealthCheck("/health");

builder.Build().Run();
