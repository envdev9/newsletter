var builder = DistributedApplication.CreateBuilder(args);

// AppHost sterowany argumentami, żeby probe mógł zmieniać konfigurację zasobu między uruchomieniami:
//   Mark=<tekst>        zmienna środowiskowa LAB_MARK kontenera Redis (zmiana "konfiguracji, która nie dotyczy obrazu")
//   RedisTag=<tag>      tag obrazu Redisa (zmiana obrazu); brak = domyślny tag integracji
//   VolumeName=<nazwa>  jeśli podana: WithDataVolume(nazwa) - dane Redisa na nazwanym woluminie
//   Persistence=true    WithPersistence() - Redis zapisuje snapshot RDB (potrzebne obok WithDataVolume)
//   Persistent=false   kontrola: domyślny ContainerLifetime.Session
var cfg = builder.Configuration;
var persistent = !string.Equals(cfg["Persistent"], "false", StringComparison.OrdinalIgnoreCase);

var cache = builder.AddRedis("cache")
    .WithEnvironment("LAB_MARK", cfg["Mark"] ?? "m0");

if (persistent)
{
    cache.WithLifetime(ContainerLifetime.Persistent);
}
if (!string.IsNullOrEmpty(cfg["RedisTag"]))
{
    cache.WithImageTag(cfg["RedisTag"]!);
}
if (!string.IsNullOrEmpty(cfg["VolumeName"]))
{
    cache.WithDataVolume(cfg["VolumeName"]!);
}
if (string.Equals(cfg["Persistence"], "true", StringComparison.OrdinalIgnoreCase))
{
    // Redis zapisuje snapshot RDB do /data (domyślnie: co 60 s przy >= 1 zmienionym kluczu)
    cache.WithPersistence();
}

builder.AddProject<Projects.CacheApi>("cache-api")
    .WithReference(cache)
    .WaitFor(cache)
    .WithHttpHealthCheck("/health");

builder.Build().Run();
