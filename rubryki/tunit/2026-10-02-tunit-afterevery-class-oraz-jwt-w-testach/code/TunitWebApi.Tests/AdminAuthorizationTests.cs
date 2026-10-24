using System.Net;

namespace TunitWebApi.Tests;

/// <summary>
/// Testy /secure/admin-report -- endpoint z polityka [Authorize(Policy = "AdminOnly")]
/// (RequireRole("admin")). Druga, niezalezna klasa testowa z WLASNYM
/// [ClassDataSource&lt;ApiFixture&gt;(Shared = SharedType.PerClass)] -- razem z
/// AuthenticatedUserTests daje dwie instancje ApiFixture i dwa wywolania
/// [AfterEvery(Class)] do zaobserwowania w ClassHooks.cs.
/// </summary>
[ClassDataSource<ApiFixture>(Shared = SharedType.PerClass)]
public class AdminAuthorizationTests(ApiFixture fixture)
{
    [Test]
    public async Task AdminRaport_BezTokenu_Zwraca401()
    {
        var response = await fixture.Client.SendAsync(TestRequests.Get("/secure/admin-report"));

        // Pulapka do zapamietania: brak uwierzytelnienia to 401 (Unauthorized), NIE 403.
        // 403 (Forbidden) jest zarezerwowane dla "jestes zalogowany, ale nie masz tej roli".
        await Assert.That(response.StatusCode).IsEqualTo(HttpStatusCode.Unauthorized);
    }

    [Test]
    public async Task AdminRaport_ZTokenemZwyklegoUzytkownika_Zwraca403()
    {
        var token = TokenFactory.CreateToken(subject: "user-1", name: "Zwykly User", roles: ["user"]);

        var response = await fixture.Client.SendAsync(TestRequests.Get("/secure/admin-report", token));

        await Assert.That(response.StatusCode).IsEqualTo(HttpStatusCode.Forbidden);
    }

    [Test]
    public async Task AdminRaport_ZTokenemAdmina_Zwraca200()
    {
        var token = TokenFactory.CreateToken(subject: "admin-1", name: "Pani Admin", roles: ["admin"]);

        var response = await fixture.Client.SendAsync(TestRequests.Get("/secure/admin-report", token));

        await Assert.That(response.StatusCode).IsEqualTo(HttpStatusCode.OK);
    }

    [Test]
    public async Task AdminRaport_ZTokenemZWieluRolami_DajeDostep()
    {
        var token = TokenFactory.CreateToken(subject: "poweruser-1", name: "Power User", roles: ["user", "admin"]);

        var response = await fixture.Client.SendAsync(TestRequests.Get("/secure/admin-report", token));

        await Assert.That(response.StatusCode).IsEqualTo(HttpStatusCode.OK);
    }
}
