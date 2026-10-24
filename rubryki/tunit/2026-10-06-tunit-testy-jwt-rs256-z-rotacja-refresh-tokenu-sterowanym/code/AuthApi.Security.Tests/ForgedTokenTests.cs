using System.Net;
using AuthTestKit;

namespace AuthApi.Security.Tests;

/// <summary>
/// Katalog atakow na walidacje JWT. Jeden test parametryzowany po nazwie ataku +
/// test kontrolny (poprawny token PRZECHODZI -- inaczej "401" nic by nie dowodzilo).
/// Fixture wspolny dla calej sesji (PerTestSession): ataki nie zmieniaja stanu serwera.
/// </summary>
[Category("security")]
[ClassDataSource<AuthFixture>(Shared = SharedType.PerTestSession)]
public class ForgedTokenTests(AuthFixture f)
{
    public static IEnumerable<string> Attacks() => Forge.AttackNames;

    [Test]
    [DisplayName("KONTROLA: token podpisany kluczem aplikacji jest akceptowany")]
    public async Task Control_LegitToken_IsAccepted()
    {
        var token = Forge.Rs256(f.TestRsa, f.Time.GetUtcNow());

        var res = await f.GetProfileAsync(token);

        await Assert.That(res.StatusCode).IsEqualTo(HttpStatusCode.OK);
    }

    [Test]
    [MethodDataSource(nameof(Attacks))]
    [DisplayName("Atak $attack -> 401")]
    public async Task ForgedToken_IsRejected(string attack)
    {
        var token = Forge.Build(attack, f);

        var res = await f.GetProfileAsync(token);

        await Assert.That(res.StatusCode).IsEqualTo(HttpStatusCode.Unauthorized);
    }
}
