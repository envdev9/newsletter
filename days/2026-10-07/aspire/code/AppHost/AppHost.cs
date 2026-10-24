var builder = DistributedApplication.CreateBuilder(args);

// Ten sam AppHost co w #12/#13: jeden Redis (prawdziwy kontener) + CacheApi.
// Dziś pytanie brzmi: co zostaje, gdy proces HOSTUJĄCY AppHosta umiera brutalnie
// - patrz Orphan.Probe/.
var cache = builder.AddRedis("cache");

builder.AddProject<Projects.CacheApi>("cache-api")
    .WithReference(cache)
    .WaitFor(cache)
    .WithHttpHealthCheck("/health");

builder.Build().Run();
