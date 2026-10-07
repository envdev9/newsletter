using System.Net;
using System.Security.Cryptography;
using Microsoft.IdentityModel.JsonWebTokens;
using Microsoft.IdentityModel.Tokens;

namespace RotationTests;

[Category("rotation")]
public class KeyRotationTests
{
    private static readonly TimeSpan Long = TimeSpan.FromHours(12);

    [Test]
    [DisplayName("Baza: JWKS pobrany po HTTP raz, kolejne zapytania biora go z pamieci podrecznej")]
    public async Task Baseline_JwksFetchedOnceAndCached()
    {
        await using var env = await Env.StartAsync(Long, TimeSpan.FromMinutes(5));
        var token = (await env.LoginAsync()).AccessToken;

        var s1 = await env.ProfileStatusAsync(token);
        var s2 = await env.ProfileStatusAsync(token);
        var s3 = await env.ProfileStatusAsync(token);

        using (Assert.Multiple())
        {
            await Assert.That(s1).IsEqualTo(HttpStatusCode.OK);
            await Assert.That(s2).IsEqualTo(HttpStatusCode.OK);
            await Assert.That(s3).IsEqualTo(HttpStatusCode.OK);
            await Assert.That(env.Keys.JwksFetches).IsEqualTo(1);
        }
    }

    [Test]
    [DisplayName("Rotacja z oknem nakladania: stary token dziala, pierwszy token z NOWYM kid dostaje 401, drugi 200")]
    public async Task Rotation_OverlapWindow_FirstRequestWithNewKidFails()
    {
        await using var env = await Env.StartAsync(Long, TimeSpan.FromMinutes(5));
        var oldToken = (await env.LoginAsync()).AccessToken;
        await env.ProfileStatusAsync(oldToken); // zasila cache kluczem key-1

        env.Keys.Rotate();                       // key-2 aktywny, key-1 nadal w JWKS
        var newToken = (await env.LoginAsync()).AccessToken;
        var fetchesBefore = env.Keys.JwksFetches;

        var oldAfter = await env.ProfileStatusAsync(oldToken);
        var newFirst = await env.ProfileStatusAsync(newToken);
        var poll = await env.PollUntilAsync(newToken, HttpStatusCode.OK, TimeSpan.FromSeconds(10));

        Console.WriteLine($"[pomiar] stary={oldAfter} nowy-pierwszy={newFirst} proby-do-200={poll.Attempts} " +
                          $"ms={poll.ElapsedMs} pobrania-JWKS: przed={fetchesBefore} po={env.Keys.JwksFetches}");

        using (Assert.Multiple())
        {
            await Assert.That(oldAfter).IsEqualTo(HttpStatusCode.OK);
            await Assert.That(newFirst).IsEqualTo(HttpStatusCode.Unauthorized);
            await Assert.That(poll.Last).IsEqualTo(HttpStatusCode.OK);
            await Assert.That(env.Keys.JwksFetches).IsEqualTo(fetchesBefore + 1);
        }
    }

    [Test]
    [DisplayName("Druga rotacja w oknie RefreshInterval: nowy kid jest odrzucany, dopoki nie minie interwal")]
    public async Task SecondRotation_WithinRefreshInterval_IsThrottled()
    {
        var interval = TimeSpan.FromSeconds(3);
        await using var env = await Env.StartAsync(Long, interval);

        var t1 = (await env.LoginAsync()).AccessToken;
        await env.ProfileStatusAsync(t1);

        env.Keys.Rotate();
        var t2 = (await env.LoginAsync()).AccessToken;
        await env.ProfileStatusAsync(t2); // 401 -> wymusza pierwsze odswiezenie
        await env.PollUntilAsync(t2, HttpStatusCode.OK, TimeSpan.FromSeconds(10));

        env.Keys.Rotate();
        var t3 = (await env.LoginAsync()).AccessToken;
        var fetchesBefore = env.Keys.JwksFetches;
        var poll = await env.PollUntilAsync(t3, HttpStatusCode.OK, TimeSpan.FromSeconds(20));

        Console.WriteLine($"[pomiar] druga rotacja: proby-do-200={poll.Attempts} ms={poll.ElapsedMs} " +
                          $"pobrania-JWKS: przed={fetchesBefore} po={env.Keys.JwksFetches} (interwal {interval.TotalMilliseconds} ms)");

        using (Assert.Multiple())
        {
            await Assert.That(poll.Last).IsEqualTo(HttpStatusCode.OK);
            await Assert.That(poll.Attempts).IsGreaterThan(1); // nie od razu: najpierw odrzucenie
            await Assert.That(env.Keys.JwksFetches).IsEqualTo(fetchesBefore + 1);
        }
    }

    [Test]
    [Arguments(false, HttpStatusCode.OK)]           // domyslne LastKnownGoodLifetime biblioteki
    [Arguments(true, HttpStatusCode.Unauthorized)]  // LastKnownGoodLifetime = 1 s
    [DisplayName("Wycofany klucz po wymuszonym odswiezeniu JWKS (krotkie LastKnownGood: $shortLkg) -> $expected")]
    public async Task RetiredKey_AfterForcedRefresh(bool shortLkg, HttpStatusCode expected)
    {
        await using var env = await Env.StartAsync(Long, TimeSpan.FromSeconds(1),
            lastKnownGood: shortLkg ? TimeSpan.FromSeconds(1) : null);
        var oldToken = (await env.LoginAsync()).AccessToken; // podpisany key-1
        await env.ProfileStatusAsync(oldToken);

        env.Keys.Rotate();
        env.Keys.Retire("key-1");                           // wystawca juz nie publikuje key-1

        var fetchesBefore = env.Keys.JwksFetches;
        var stale = await env.ProfileStatusAsync(oldToken); // cache "nieswiezy": nadal 200

        // Dopiero token z nieznanym kid wymusza odswiezenie JWKS (RequestRefresh)...
        using var evil = RSA.Create(2048);
        await env.ProfileStatusAsync(ForgedWithKid(evil, "wymuszacz-odswiezenia"));
        var poll = await env.PollUntilAsync(oldToken, HttpStatusCode.Unauthorized, TimeSpan.FromSeconds(4));

        Console.WriteLine($"[pomiar] shortLkg={shortLkg}: zaraz po Retire={stale}; po 'wymuszaczu': ostatni={poll.Last} " +
                          $"proby={poll.Attempts} ms={poll.ElapsedMs} pobrania-JWKS: przed={fetchesBefore} po={env.Keys.JwksFetches}");

        using (Assert.Multiple())
        {
            await Assert.That(stale).IsEqualTo(HttpStatusCode.OK);
            await Assert.That(poll.Last).IsEqualTo(expected);
        }
    }

    private static string ForgedWithKid(RSA key, string kid) =>
        new JsonWebTokenHandler().CreateToken(new SecurityTokenDescriptor
        {
            Issuer = "demo-issuer",
            Audience = "demo-api",
            Claims = new Dictionary<string, object> { ["sub"] = "admin" },
            Expires = DateTime.UtcNow.AddMinutes(5),
            SigningCredentials = new SigningCredentials(
                new RsaSecurityKey(key) { KeyId = kid }, SecurityAlgorithms.RsaSha256),
        });

    [Test]
    [DisplayName("Atak: 20 tokenow z nieznanym kid nie powoduje 20 pobran JWKS")]
    public async Task UnknownKidFlood_DoesNotFloodIssuer()
    {
        await using var env = await Env.StartAsync(Long, TimeSpan.FromMinutes(5));
        await env.ProfileStatusAsync((await env.LoginAsync()).AccessToken); // rozgrzewka: 1 pobranie

        using var evil = RSA.Create(2048);
        var statuses = new List<HttpStatusCode>();
        for (var i = 0; i < 20; i++)
        {
            statuses.Add(await env.ProfileStatusAsync(ForgedWithKid(evil, $"evil-{i}")));
        }

        Console.WriteLine($"[pomiar] 20 falszywych kid -> pobrania JWKS lacznie={env.Keys.JwksFetches}");

        using (Assert.Multiple())
        {
            await Assert.That(statuses.All(s => s == HttpStatusCode.Unauthorized)).IsTrue();
            await Assert.That(env.Keys.JwksFetches).IsLessThanOrEqualTo(2);
        }
    }

    [Test]
    [DisplayName("RefreshOnIssuerKeyNotFound=false NIE wylacza odswiezania po nieznanym kid (zmierzone)")]
    public async Task RefreshOnKeyNotFoundDisabled_StillRefreshes()
    {
        await using var env = await Env.StartAsync(Long, TimeSpan.FromSeconds(1), refreshOnKeyNotFound: false);
        await env.ProfileStatusAsync((await env.LoginAsync()).AccessToken);

        env.Keys.Rotate();
        var newToken = (await env.LoginAsync()).AccessToken;
        var poll = await env.PollUntilAsync(newToken, HttpStatusCode.OK, TimeSpan.FromSeconds(3));

        Console.WriteLine($"[pomiar] bez RefreshOnIssuerKeyNotFound: ostatni={poll.Last} proby={poll.Attempts} " +
                          $"pobrania JWKS={env.Keys.JwksFetches}");

        // Wynik jest ZASKAKUJACY (spodziewalem sie 401 przez caly czas) -- opisuje stan faktyczny dla
        // Microsoft.IdentityModel z pakietu JwtBearer 10.0.12; mechanizmu nie badalem.
        using (Assert.Multiple())
        {
            await Assert.That(poll.Last).IsEqualTo(HttpStatusCode.OK);
            await Assert.That(env.Keys.JwksFetches).IsEqualTo(2);
        }
    }
}
