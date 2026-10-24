using System.Net;
using System.Net.Http.Json;
using System.Text.Json;
using AuthApi;
using AuthTestKit;
using Microsoft.IdentityModel.JsonWebTokens;

namespace AuthApi.Tests;

/// <summary>
/// Cykl zycia tokenow: RS256, wygasanie (zegar sterowany z testu), rotacja refresh tokenu
/// i wykrywanie jego ponownego uzycia. Kazdy test dostaje SWOJ host (SharedType.None) --
/// bo testy przesuwaja zegar, a wspolny zegar to wspolny stan = flaky.
/// </summary>
[Category("lifecycle")]
[ClassDataSource<AuthFixture>(Shared = SharedType.None)]
public class TokenLifecycleTests(AuthFixture f)
{
    [Test]
    [DisplayName("Login wystawia access token RS256 z kid, a profil go akceptuje")]
    public async Task Login_IssuesRs256Token_AndProfileAcceptsIt()
    {
        var tokens = await f.LoginAsync();
        var jwt = new JsonWebToken(tokens.AccessToken);

        var profile = await f.GetProfileAsync(tokens.AccessToken);

        using (Assert.Multiple())
        {
            await Assert.That(jwt.Alg).IsEqualTo("RS256");
            await Assert.That(jwt.Kid).IsNotNullOrEmpty();
            await Assert.That(profile.StatusCode).IsEqualTo(HttpStatusCode.OK);
        }
    }

    [Test]
    [DisplayName("JWKS publikuje klucz publiczny i NIE zawiera skladowych prywatnych")]
    public async Task Jwks_ExposesOnlyPublicKey()
    {
        var json = await f.Client.GetStringAsync("/.well-known/jwks.json");
        using var doc = JsonDocument.Parse(json);
        var key = doc.RootElement.GetProperty("keys")[0];

        using (Assert.Multiple())
        {
            await Assert.That(key.GetProperty("kty").GetString()).IsEqualTo("RSA");
            await Assert.That(key.TryGetProperty("n", out _)).IsTrue();
            await Assert.That(key.TryGetProperty("e", out _)).IsTrue();
            // d, p, q, dp, dq, qi to skladowe prywatne RSA -- nie moga wyciec
            foreach (var priv in new[] { "d", "p", "q", "dp", "dq", "qi" })
                await Assert.That(key.TryGetProperty(priv, out _)).IsFalse();
        }
    }

    [Test]
    [DisplayName("Access token zyje 60 s: 59 s OK, 61 s -> 401 (bez Thread.Sleep)")]
    public async Task AccessToken_ExpiresAfterSixtySeconds()
    {
        var tokens = await f.LoginAsync();

        f.Time.Advance(TimeSpan.FromSeconds(59));
        var before = await f.GetProfileAsync(tokens.AccessToken);

        f.Time.Advance(TimeSpan.FromSeconds(2));
        var after = await f.GetProfileAsync(tokens.AccessToken);

        using (Assert.Multiple())
        {
            await Assert.That(before.StatusCode).IsEqualTo(HttpStatusCode.OK);
            await Assert.That(after.StatusCode).IsEqualTo(HttpStatusCode.Unauthorized);
        }
    }

    [Test]
    [DisplayName("Odswiezanie: po wygasnieciu access tokenu refresh daje nowa, dzialajaca pare")]
    public async Task Refresh_AfterAccessExpiry_GivesWorkingPair()
    {
        var first = await f.LoginAsync();
        f.Time.Advance(TimeSpan.FromSeconds(61));
        var expired = await f.GetProfileAsync(first.AccessToken);

        var refreshed = await f.RefreshAsync(first.RefreshToken);
        var second = (await refreshed.Content.ReadFromJsonAsync<TokenResponse>())!;
        var again = await f.GetProfileAsync(second.AccessToken);

        using (Assert.Multiple())
        {
            await Assert.That(expired.StatusCode).IsEqualTo(HttpStatusCode.Unauthorized);
            await Assert.That(refreshed.StatusCode).IsEqualTo(HttpStatusCode.OK);
            await Assert.That(second.RefreshToken).IsNotEqualTo(first.RefreshToken); // rotacja
            await Assert.That(again.StatusCode).IsEqualTo(HttpStatusCode.OK);
        }
    }

    [Test]
    [DisplayName("Reuse detection: ponowne uzycie zuzytego refresh tokenu uniewaznia CALA rodzine")]
    public async Task Refresh_Reuse_RevokesWholeFamily()
    {
        var r1 = (await f.LoginAsync()).RefreshToken;

        var rotate = await f.RefreshAsync(r1);                  // r1 -> r2 (legalnie)
        var r2 = (await rotate.Content.ReadFromJsonAsync<TokenResponse>())!.RefreshToken;

        var replay = await f.RefreshAsync(r1);                  // zlodziej probuje zuzytego r1
        var victim = await f.RefreshAsync(r2);                  // legalny klient z NAJNOWSZYM r2

        using (Assert.Multiple())
        {
            await Assert.That(rotate.StatusCode).IsEqualTo(HttpStatusCode.OK);
            await Assert.That(replay.StatusCode).IsEqualTo(HttpStatusCode.Unauthorized);
            await Assert.That(victim.StatusCode).IsEqualTo(HttpStatusCode.Unauthorized); // r2 tez martwy
        }
    }

    [Test]
    [DisplayName("Refresh token wygasa po 7 dniach")]
    public async Task Refresh_ExpiresAfterSevenDays()
    {
        var tokens = await f.LoginAsync();

        f.Time.Advance(TimeSpan.FromDays(7) - TimeSpan.FromSeconds(1));
        var stillOk = await f.RefreshAsync(tokens.RefreshToken);
        var next = (await stillOk.Content.ReadFromJsonAsync<TokenResponse>())!;

        f.Time.Advance(TimeSpan.FromDays(7) + TimeSpan.FromSeconds(1));
        var tooLate = await f.RefreshAsync(next.RefreshToken);

        using (Assert.Multiple())
        {
            await Assert.That(stillOk.StatusCode).IsEqualTo(HttpStatusCode.OK);
            await Assert.That(tooLate.StatusCode).IsEqualTo(HttpStatusCode.Unauthorized);
        }
    }
}
