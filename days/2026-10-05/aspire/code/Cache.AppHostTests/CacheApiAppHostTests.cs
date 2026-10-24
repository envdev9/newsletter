using System.Collections.Concurrent;
using System.Net;
using System.Text.Json;
using TUnit.Core.Interfaces;

namespace Cache.AppHostTests;

/// <summary>
/// Dziennik startu/końca każdego testu tej klasy - żeby ZMIERZYĆ (nie zgadywać), czy
/// TUnit faktycznie odpala te testy równolegle na JEDNYM, współdzielonym kontenerze
/// Redis (fixture z SharedType.PerClass), czy sekwencyjnie.
/// </summary>
internal static class Timeline
{
    public static readonly ConcurrentBag<(string Test, DateTime Start, DateTime End)> Entries = new();
}

/// <summary>
/// Test AppHosta w TUnit, nie w gołym runnerze testowym (jak Cache.Verify z wydania #5).
/// [ClassDataSource&lt;RedisAppHostFixture&gt;(Shared = SharedType.PerClass)] to ten sam
/// mechanizm co w wydaniu #3/#5/#7 TUnit (WebApplicationFactory jako fixture) -
/// RedisAppHostFixture.InitializeAsync() startuje AppHost + kontener Redis RAZ dla
/// całej klasy, a nie raz na test. Wszystkie testy w klasie dzielą jeden żywy
/// DistributedApplication.
/// </summary>
[ClassDataSource<RedisAppHostFixture>(Shared = SharedType.PerClass)]
public class CacheApiAppHostTests(RedisAppHostFixture fixture)
{
    private RedisAppHostFixture Fixture => fixture;

    private static async Task<T> Timed<T>(string name, Func<Task<T>> action)
    {
        var start = DateTime.UtcNow;
        var result = await action();
        var end = DateTime.UtcNow;
        Timeline.Entries.Add((name, start, end));
        return result;
    }

    [Test]
    public async Task Health_Endpoint_Returns_Healthy()
    {
        var body = await Timed(nameof(Health_Endpoint_Returns_Healthy), async () =>
        {
            using var http = Fixture.CreateHttpClient();
            return await http.GetStringAsync("/health");
        });

        await Assert.That(body).IsEqualTo("Healthy");
    }

    [Test]
    public async Task Put_Then_Get_Roundtrips_Through_Real_Redis()
    {
        var value = await Timed(nameof(Put_Then_Get_Roundtrips_Through_Real_Redis), async () =>
        {
            using var http = Fixture.CreateHttpClient();

            // Klucz unikalny per test - tak, żeby WIELE testów mogło bezpiecznie
            // równolegle pisać/czytać do JEDNEGO wspólnego kontenera Redis, bez
            // wzajemnego nadpisywania danych.
            var key = "tunit:" + Guid.NewGuid().ToString("N")[..8];
            var written = "wpis-" + Guid.NewGuid().ToString("N")[..8];

            var put = await http.PutAsync($"/cache/{key}", new StringContent(written));
            if (!put.IsSuccessStatusCode)
            {
                throw new InvalidOperationException($"PUT nie powiodło się: {put.StatusCode}");
            }

            var getBody = await http.GetStringAsync($"/cache/{key}");
            var json = JsonDocument.Parse(getBody).RootElement;
            return (written, read: json.GetProperty("value").GetString());
        });

        await Assert.That(value.read).IsEqualTo(value.written);
    }

    [Test]
    public async Task Connection_String_Has_Password_And_Ssl()
    {
        var info = await Timed(nameof(Connection_String_Has_Password_And_Ssl), async () =>
        {
            using var http = Fixture.CreateHttpClient();
            var body = await http.GetStringAsync("/cache-info");
            return JsonDocument.Parse(body).RootElement.Clone();
        });

        // AddRedis bez żadnej dodatkowej konfiguracji generuje losowe hasło + TLS
        // (zmierzone już w wydaniu #5) - tu tylko potwierdzamy, że to przeżyło
        // przejście przez TUnit + ClassDataSource.
        await Assert.That(info.GetProperty("connectionHasPassword").GetBoolean()).IsTrue();
        await Assert.That(info.GetProperty("connectionHasSsl").GetBoolean()).IsTrue();
        await Assert.That(info.GetProperty("isConnected").GetBoolean()).IsTrue();
    }

    [Test]
    public async Task Missing_Key_Returns_404()
    {
        var status = await Timed(nameof(Missing_Key_Returns_404), async () =>
        {
            using var http = Fixture.CreateHttpClient();
            var resp = await http.GetAsync("/cache/nieistniejacy-" + Guid.NewGuid().ToString("N"));
            return resp.StatusCode;
        });

        await Assert.That(status).IsEqualTo(HttpStatusCode.NotFound);
    }

    /// <summary>
    /// Odpala się RAZ po wszystkich testach TEJ klasy (ten sam hak co TUnit #9,
    /// 2026-10-02) - tu wykorzystany do zmierzenia dwóch rzeczy naraz:
    /// 1) że fixture faktycznie wystartował AppHost RAZ, nie 4 razy;
    /// 2) czy testy, które dzieliły jeden kontener Redis, nakładały się w czasie.
    /// </summary>
    [After(Class)]
    public static void ReportTimelineAndInitializeCount(ClassHookContext context)
    {
        // [After(Class)] jest STATYCZNY (patrz TUnit #9, 2026-10-02) - nie ma więc
        // bezpośredniego dostępu do konkretnej, współdzielonej instancji fixture'a
        // wstrzykiwanej przez ClassDataSource do pola instancyjnego Fixture. Haczyk
        // zmierzony dziś: żeby i tak przeczytać jej stan (InitializeCount) w haku
        // klasowym, trzeba go najpierw "przemycić" przez statyczne pole w [Before(Test)]
        // (CaptureInitializeCount poniżej) - inaczej hak klasowy nie widzi fixture'a wprost.
        Console.WriteLine($"=== RedisAppHostFixture.InitializeCount = {CapturedInitializeCount} ===");

        var entries = Timeline.Entries.OrderBy(e => e.Start).ToList();
        Console.WriteLine("=== Linia czasu testów na WSPÓLNYM kontenerze Redis ===");
        foreach (var e in entries)
        {
            Console.WriteLine($"{e.Test}: {e.Start:HH:mm:ss.fff} -> {e.End:HH:mm:ss.fff}");
        }

        var overlapping = new List<(string, string)>();
        for (var i = 0; i < entries.Count; i++)
        {
            for (var j = i + 1; j < entries.Count; j++)
            {
                if (entries[i].Start < entries[j].End && entries[j].Start < entries[i].End)
                {
                    overlapping.Add((entries[i].Test, entries[j].Test));
                }
            }
        }

        Console.WriteLine(overlapping.Count > 0
            ? $"ZMIERZONE: {overlapping.Count} par testów nakładało się w czasie na TYM SAMYM kontenerze Redis ({string.Join(", ", overlapping.Select(p => $"{p.Item1}~{p.Item2}"))})."
            : "ZMIERZONE: testy wykonały się sekwencyjnie - brak nakładania w czasie.");
    }

    [Before(Test)]
    public void CaptureInitializeCount()
    {
        CapturedInitializeCount = Fixture.InitializeCount;
    }

    private static int CapturedInitializeCount;
}
