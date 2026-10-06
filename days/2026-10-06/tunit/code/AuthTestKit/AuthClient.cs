using System.Net.Http.Headers;
using System.Net.Http.Json;
using AuthApi;

namespace AuthTestKit;

/// <summary>Cienkie helpery HTTP -- zeby testy czytaly sie jak scenariusz, nie jak plumbing.</summary>
public static class AuthClient
{
    public static async Task<TokenResponse> LoginAsync(this AuthFixture f)
    {
        var res = await f.Client.PostAsJsonAsync("/auth/login", new LoginRequest("alice", "demo-only-password"));
        res.EnsureSuccessStatusCode();
        return (await res.Content.ReadFromJsonAsync<TokenResponse>())!;
    }

    public static Task<HttpResponseMessage> RefreshAsync(this AuthFixture f, string refreshToken) =>
        f.Client.PostAsJsonAsync("/auth/refresh", new RefreshRequest(refreshToken));

    public static async Task<HttpResponseMessage> GetProfileAsync(this AuthFixture f, string? accessToken)
    {
        using var req = new HttpRequestMessage(HttpMethod.Get, "/secure/profile");
        if (accessToken is not null)
            req.Headers.Authorization = new AuthenticationHeaderValue("Bearer", accessToken);
        return await f.Client.SendAsync(req);
    }
}
