using System.Collections.Concurrent;
using System.Text.Json;

namespace Cache.AppHostTests;

/// <summary>Zbiera obserwacje z wielu klas testowych, żeby podsumować je RAZ na końcu sesji.</summary>
internal static class Observations
{
    public static readonly ConcurrentBag<(string Class, string FixtureId)> FixtureIds = new();
    public static readonly ConcurrentBag<(string Test, string[] Containers)> ContainerSamples = new();

    public static void Sample(string test) =>
        ContainerSamples.Add((test, RedisAppHostFixture.RunningRedisContainers()));
}

// Dwie RÓŻNE klasy, ten sam typ fixture'a, SharedType.PerTestSession =>
// TUnit ma dać im JEDNĄ instancję (jeden AppHost, jeden kontener Redis).
[ClassDataSource<RedisAppHostFixture>(Shared = SharedType.PerTestSession)]
public class SessionWriteTests(RedisAppHostFixture fixture)
{
    [Test]
    public async Task Put_Then_Get_Roundtrips()
    {
        Observations.FixtureIds.Add((nameof(SessionWriteTests), fixture.Id));
        Observations.Sample(nameof(Put_Then_Get_Roundtrips));

        using var http = fixture.CreateHttpClient();
        var key = "session:" + Guid.NewGuid().ToString("N")[..8];
        var written = "wpis-" + Guid.NewGuid().ToString("N")[..8];

        await http.PutAsync($"/cache/{key}", new StringContent(written));
        var body = await http.GetStringAsync($"/cache/{key}");
        var read = JsonDocument.Parse(body).RootElement.GetProperty("value").GetString();

        await Assert.That(read).IsEqualTo(written);
    }
}

[ClassDataSource<RedisAppHostFixture>(Shared = SharedType.PerTestSession)]
public class SessionInfoTests(RedisAppHostFixture fixture)
{
    [Test]
    public async Task Redis_Is_Connected_Master()
    {
        Observations.FixtureIds.Add((nameof(SessionInfoTests), fixture.Id));
        Observations.Sample(nameof(Redis_Is_Connected_Master));

        using var http = fixture.CreateHttpClient();
        var info = JsonDocument.Parse(await http.GetStringAsync("/cache-info")).RootElement;

        await Assert.That(info.GetProperty("isConnected").GetBoolean()).IsTrue();
        await Assert.That(info.GetProperty("role").GetString()).IsEqualTo("master");
    }
}

// Ten sam typ fixture'a, ale PerClass => TUnit tworzy OSOBNĄ instancję, czyli
// DRUGI AppHost z TĄ SAMĄ nazwą zasobu "cache", żywy równolegle z tym z sesji.
[ClassDataSource<RedisAppHostFixture>(Shared = SharedType.PerClass)]
public class OwnFixtureTests(RedisAppHostFixture fixture)
{
    [Test]
    public async Task Health_On_Own_AppHost()
    {
        Observations.FixtureIds.Add((nameof(OwnFixtureTests), fixture.Id));

        using var http = fixture.CreateHttpClient();
        var body = await http.GetStringAsync("/health");

        // Przytrzymujemy test chwilę, żeby okno życia obu AppHostów się na pewno nałożyło.
        await Task.Delay(TimeSpan.FromSeconds(3));
        Observations.Sample(nameof(Health_On_Own_AppHost));

        await Assert.That(body).IsEqualTo("Healthy");
    }
}

public static class SessionSummary
{
    [After(TestSession)]
    public static void Report(TestSessionContext context)
    {
        Console.WriteLine($"=== Fixture.Starts = {RedisAppHostFixture.Starts} (Disposes dotąd: {RedisAppHostFixture.Disposes}) ===");
        foreach (var g in Observations.FixtureIds.GroupBy(x => x.FixtureId))
        {
            Console.WriteLine($"fixture {g.Key}: używany przez {string.Join(", ", g.Select(x => x.Class).Distinct())}");
        }

        var max = Observations.ContainerSamples.Select(s => s.Containers.Length).DefaultIfEmpty(0).Max();
        Console.WriteLine($"=== Maks. liczba kontenerów 'cache-*' widzianych naraz w docker ps: {max} ===");
        foreach (var s in Observations.ContainerSamples.OrderBy(s => s.Test))
        {
            Console.WriteLine($"{s.Test}: {s.Containers.Length} kontener(y): {string.Join(", ", s.Containers)}");
        }
    }
}
