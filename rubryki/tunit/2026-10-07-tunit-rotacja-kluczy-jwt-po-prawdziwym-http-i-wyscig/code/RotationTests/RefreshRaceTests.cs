using System.Net;
using System.Net.Http.Json;
using IssuerApi;

namespace RotationTests;

[Category("race")]
public class RefreshRaceTests
{
    private const int Parallel = 32;

    // Ten sam wyscig, ale BEZ HTTP: wprost na magazynie, z barierą na wątkach. Okno wyscigu jest wtedy
    // o rzedy wielkosci wezsze niz przez Kestrel, wiec to ten test (a nie HTTP-owy) ma szanse zlapac brak lock.
    [Test]
    [Repeat(20)]
    [DisplayName("Wyscig na magazynie (bez HTTP): 64 watki, dokladnie jeden Ok")]
    public async Task ConcurrentRotate_OnStore_ExactlyOneWins()
    {
        var store = new RefreshTokenStore(TimeProvider.System);
        var token = store.Create("alice");
        using var barrier = new Barrier(64);

        var results = new RotateStatus[64];
        var threads = Enumerable.Range(0, 64).Select(i => new Thread(() =>
        {
            barrier.SignalAndWait();
            results[i] = store.Rotate(token).Status;
        })).ToList();
        threads.ForEach(t => t.Start());
        threads.ForEach(t => t.Join());

        var ok = results.Count(s => s == RotateStatus.Ok);
        Console.WriteLine($"[pomiar] Ok={ok} ReuseDetected={results.Count(s => s == RotateStatus.ReuseDetected)}");
        await Assert.That(ok).IsEqualTo(1);
    }

    // [Repeat] odpala test N razy -- wyscig, ktory raz sie nie ujawnil, nie dowodzi niczego.
    [Test]
    [Repeat(5)]
    [DisplayName("Wyscig: 32 rownolegle /auth/refresh tym samym tokenem -> dokladnie jedno 200")]
    public async Task ConcurrentRefresh_ExactlyOneWins()
    {
        await using var env = await Env.StartAsync(TimeSpan.FromHours(12), TimeSpan.FromMinutes(5));
        var login = await env.LoginAsync();

        // Bariera: wszystkie zadania startuja "naraz", zeby okno wyscigu bylo jak najwieksze.
        var gate = new TaskCompletionSource();
        var calls = Enumerable.Range(0, Parallel).Select(_ => Task.Run(async () =>
        {
            await gate.Task;
            return await env.RefreshAsync(login.RefreshToken);
        })).ToArray();
        gate.SetResult();
        var responses = await Task.WhenAll(calls);

        var winners = responses.Where(r => r.StatusCode == HttpStatusCode.OK).ToList();
        var losers = responses.Count(r => r.StatusCode == HttpStatusCode.Unauthorized);
        Console.WriteLine($"[pomiar] 200={winners.Count} 401={losers}");

        using (Assert.Multiple())
        {
            await Assert.That(winners.Count).IsEqualTo(1);
            await Assert.That(losers).IsEqualTo(Parallel - 1);
        }

        // Skutek uboczny wyscigu: przegrani przedlozyli ZUZYTY token, wiec rodzina zostala uniewazniona
        // -- takze token, ktory dostal zwyciezca. (Uczciwy klient z "podwojnym kliknieciem" zostaje wylogowany.)
        var winnerToken = (await winners[0].Content.ReadFromJsonAsync<TokenResponse>())!.RefreshToken;
        var winnerNext = await env.RefreshAsync(winnerToken);
        await Assert.That(winnerNext.StatusCode).IsEqualTo(HttpStatusCode.Unauthorized);
    }
}
