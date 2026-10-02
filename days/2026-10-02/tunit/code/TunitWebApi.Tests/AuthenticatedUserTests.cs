using System.Net;
using System.Net.Http.Json;
using System.Text;
using Microsoft.IdentityModel.Tokens;

namespace TunitWebApi.Tests;

/// <summary>
/// Testy /secure/profile -- endpoint wymagajacy TYLKO poprawnego uwierzytelnienia
/// (zaden konkretny claim roli), [Authorize] bez polityki. Sprawdzamy brzegi: brak
/// tokenu, poprawny token, wygasly token, token podpisany zlym kluczem.
/// </summary>
[ClassDataSource<ApiFixture>(Shared = SharedType.PerClass)]
public class AuthenticatedUserTests(ApiFixture fixture)
{
    [Test]
    public async Task Profil_BezTokenu_Zwraca401()
    {
        var response = await fixture.Client.SendAsync(TestRequests.Get("/secure/profile"));

        await Assert.That(response.StatusCode).IsEqualTo(HttpStatusCode.Unauthorized);
    }

    [Test]
    public async Task Profil_ZWaznymTokenem_ZwracaDaneUzytkownika()
    {
        var token = TokenFactory.CreateToken(subject: "user-42", name: "Jan Kowalski");

        var response = await fixture.Client.SendAsync(TestRequests.Get("/secure/profile", token));

        await Assert.That(response.StatusCode).IsEqualTo(HttpStatusCode.OK);
        var body = await response.Content.ReadFromJsonAsync<ProfileResponse>();
        await Assert.That(body!.Sub).IsEqualTo("user-42");
        await Assert.That(body.Name).IsEqualTo("Jan Kowalski");
    }

    [Test]
    public async Task Profil_ZWygaslymTokenem_Zwraca401()
    {
        var token = TokenFactory.CreateToken(subject: "user-1", name: "X", lifetime: TimeSpan.FromSeconds(-30));

        var response = await fixture.Client.SendAsync(TestRequests.Get("/secure/profile", token));

        await Assert.That(response.StatusCode).IsEqualTo(HttpStatusCode.Unauthorized);
    }

    [Test]
    public async Task Profil_ZTokenemPodpisanymZlymKluczem_Zwraca401()
    {
        var zlyKlucz = new SymmetricSecurityKey(Encoding.UTF8.GetBytes("zupelnie-inny-klucz-tez-min-32-bajty!!"));
        var token = TokenFactory.CreateToken(subject: "user-1", name: "X", signingKeyOverride: zlyKlucz);

        var response = await fixture.Client.SendAsync(TestRequests.Get("/secure/profile", token));

        await Assert.That(response.StatusCode).IsEqualTo(HttpStatusCode.Unauthorized);
    }
}

public record ProfileResponse(string Sub, string? Name, string[] Role);
