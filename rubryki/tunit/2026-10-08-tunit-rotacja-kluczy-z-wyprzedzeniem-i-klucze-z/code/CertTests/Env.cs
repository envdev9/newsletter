using System.Diagnostics;
using System.Net;
using System.Net.Http.Json;
using System.Security.Cryptography;
using IssuerApi;
using Microsoft.AspNetCore.Builder;
using Microsoft.IdentityModel.JsonWebTokens;
using Microsoft.IdentityModel.Tokens;
using Microsoft.Extensions.DependencyInjection;
using ResourceApi;

namespace CertTests;

/// <summary>Prawdziwy serwer Kestrel wystawcy na losowym wolnym porcie 127.0.0.1.</summary>
public sealed class Issuer : IAsyncDisposable
{
    private readonly WebApplication _app;
    private readonly HttpClient _http;

    public KeyRing Keys { get; }
    public string Url { get; }

    private Issuer(WebApplication app)
    {
        _app = app;
        Keys = app.Services.GetRequiredService<KeyRing>();
        Url = app.Urls.First();
        _http = new HttpClient { BaseAddress = new Uri(Url) };
    }

    public static async Task<Issuer> StartAsync(KidMode mode)
    {
        var app = IssuerApp.Build(["--urls", "http://127.0.0.1:0"], mode);
        await app.StartAsync();
        return new Issuer(app);
    }

    public async Task<string> LoginAsync()
    {
        var r = await _http.PostAsJsonAsync("/auth/login", new LoginRequest("alice", "demo-only-password"));
        r.EnsureSuccessStatusCode();
        return (await r.Content.ReadFromJsonAsync<TokenResponse>())!.AccessToken;
    }

    public Task<string> JwksJsonAsync() => _http.GetStringAsync("/.well-known/jwks.json");

    public async ValueTask DisposeAsync()
    {
        _http.Dispose();
        await _app.DisposeAsync();
        Keys.Dispose();
    }
}

/// <summary>Serwis walidujacy tokeny (JwtBearer + ConfigurationManager po HTTP), tez prawdziwy Kestrel.</summary>
public sealed class Validator : IAsyncDisposable
{
    private readonly WebApplication _app;
    private readonly HttpClient _http;

    public ResourceOptions Options { get; }

    private Validator(WebApplication app, ResourceOptions options)
    {
        _app = app;
        Options = options;
        _http = new HttpClient { BaseAddress = new Uri(app.Urls.First()) };
    }

    public static async Task<Validator> StartAsync(Issuer issuer, TimeSpan forcedRefresh, bool enforceCertValidity = false)
    {
        var options = new ResourceOptions(issuer.Url, forcedRefresh, enforceCertValidity);
        var app = ResourceApp.Build(["--urls", "http://127.0.0.1:0"], options);
        await app.StartAsync();
        return new Validator(app, options);
    }

    public async Task<HttpStatusCode> StatusAsync(string accessToken)
    {
        using var req = new HttpRequestMessage(HttpMethod.Get, "/secure/profile");
        req.Headers.Authorization = new("Bearer", accessToken);
        using var res = await _http.SendAsync(req);
        return res.StatusCode;
    }

    /// <summary>
    /// Wymusza w walidatorze odswiezenie JWKS: wysyla tokeny z nieznanym kid (podpisane smieciowym kluczem),
    /// az licznik pobran JWKS po stronie wystawcy wzrosnie. Zwraca true, jesli sie udalo w limicie czasu.
    /// </summary>
    public async Task<bool> ForceJwksRefreshAsync(Issuer issuer, TimeSpan timeout)
    {
        var before = issuer.Keys.JwksFetches;
        var sw = Stopwatch.StartNew();
        while (sw.Elapsed < timeout)
        {
            await StatusAsync(ForgedToken(Guid.NewGuid().ToString("N")));
            if (issuer.Keys.JwksFetches > before) return true;
            await Task.Delay(50);
        }
        return false;
    }

    /// <summary>Token z poprawnymi claimami, ale podpisany SMIECIOWYM kluczem RSA z podanym kid.</summary>
    public static string ForgedToken(string kid)
    {
        using var rsa = RSA.Create(2048);
        var now = DateTime.UtcNow;
        return new JsonWebTokenHandler().CreateToken(new SecurityTokenDescriptor
        {
            Issuer = IssuerDefaults.Issuer,
            Audience = IssuerDefaults.Audience,
            Claims = new Dictionary<string, object> { ["sub"] = "mallory" },
            NotBefore = now,
            Expires = now.AddMinutes(10),
            SigningCredentials = new SigningCredentials(new RsaSecurityKey(rsa.ExportParameters(true)) { KeyId = kid }, SecurityAlgorithms.RsaSha256),
        });
    }

    public async ValueTask DisposeAsync()
    {
        _http.Dispose();
        await _app.DisposeAsync();
    }
}
