using System.Diagnostics;
using System.Net;
using System.Net.Http.Json;
using IssuerApi;
using Microsoft.AspNetCore.Builder;
using Microsoft.Extensions.DependencyInjection;
using ResourceApi;

namespace RotationTests;

/// <summary>
/// Dwa PRAWDZIWE serwery Kestrel w procesie testu, na losowych wolnych portach 127.0.0.1:
/// wystawca (IssuerApi) i serwis walidujacy tokeny (ResourceApi), ktory pobiera JWKS wystawcy
/// przez HTTP (ConfigurationManager). Zadnego WebApplicationFactory -- ruch idzie przez gniazda TCP.
/// </summary>
public sealed class Env : IAsyncDisposable
{
    private readonly WebApplication _issuer;
    private readonly WebApplication _resource;
    private readonly HttpClient _issuerHttp;
    private readonly HttpClient _resourceHttp;

    public KeyRing Keys { get; }
    public RefreshTokenStore Store { get; }

    private Env(WebApplication issuer, WebApplication resource)
    {
        _issuer = issuer;
        _resource = resource;
        Keys = issuer.Services.GetRequiredService<KeyRing>();
        Store = issuer.Services.GetRequiredService<RefreshTokenStore>();
        _issuerHttp = new HttpClient { BaseAddress = new Uri(issuer.Urls.First()) };
        _resourceHttp = new HttpClient { BaseAddress = new Uri(resource.Urls.First()) };
    }

    public static async Task<Env> StartAsync(TimeSpan automaticRefresh, TimeSpan forcedRefresh, bool refreshOnKeyNotFound = true, TimeSpan? lastKnownGood = null)
    {
        string[] urls = ["--urls", "http://127.0.0.1:0"];
        var issuer = IssuerApp.Build(urls);
        await issuer.StartAsync();

        var resource = ResourceApp.Build(urls,
            new ResourceOptions(issuer.Urls.First(), automaticRefresh, forcedRefresh, refreshOnKeyNotFound, lastKnownGood));
        await resource.StartAsync();

        return new Env(issuer, resource);
    }

    public async Task<TokenResponse> LoginAsync()
    {
        var r = await _issuerHttp.PostAsJsonAsync("/auth/login", new LoginRequest("alice", "demo-only-password"));
        r.EnsureSuccessStatusCode();
        return (await r.Content.ReadFromJsonAsync<TokenResponse>())!;
    }

    public async Task<HttpResponseMessage> RefreshAsync(string refreshToken) =>
        await _issuerHttp.PostAsJsonAsync("/auth/refresh", new RefreshRequest(refreshToken));

    public async Task<HttpStatusCode> ProfileStatusAsync(string accessToken)
    {
        using var req = new HttpRequestMessage(HttpMethod.Get, "/secure/profile");
        req.Headers.Authorization = new("Bearer", accessToken);
        using var res = await _resourceHttp.SendAsync(req);
        return res.StatusCode;
    }

    /// <summary>
    /// Powtarza zapytanie, az dostanie oczekiwany status albo minie limit. Zwraca ile prob i ile ms
    /// zajelo. Zamiast sztywnego Task.Delay: test czeka tylko tyle, ile trzeba, i NIE jest flaky.
    /// </summary>
    public async Task<(int Attempts, long ElapsedMs, HttpStatusCode Last)> PollUntilAsync(
        string accessToken, HttpStatusCode expected, TimeSpan timeout)
    {
        var sw = Stopwatch.StartNew();
        var attempts = 0;
        HttpStatusCode last;
        do
        {
            last = await ProfileStatusAsync(accessToken);
            attempts++;
            if (last == expected) break;
            await Task.Delay(50);
        } while (sw.Elapsed < timeout);
        return (attempts, sw.ElapsedMilliseconds, last);
    }

    public async ValueTask DisposeAsync()
    {
        _issuerHttp.Dispose();
        _resourceHttp.Dispose();
        await _resource.DisposeAsync();
        await _issuer.DisposeAsync();
    }
}
