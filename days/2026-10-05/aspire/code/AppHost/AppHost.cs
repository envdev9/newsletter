var builder = DistributedApplication.CreateBuilder(args);

// AddRedis: prawdziwy kontener (obraz wg RedisContainerImageTags w Aspire 13.5.2),
// nie atrapa - ten sam wzorzec co w wydaniu #5 (2026-09-28). Dziś temat nie jest
// "jak podłączyć Redisa", ale "jak to przetestować frameworkiem TUnit" - patrz
// Cache.AppHostTests/.
var cache = builder.AddRedis("cache");

var api = builder.AddProject<Projects.CacheApi>("cache-api")
    .WithReference(cache)
    .WaitFor(cache)
    .WithHttpHealthCheck("/health");

builder.Build().Run();
