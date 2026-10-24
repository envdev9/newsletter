namespace IssuerApi;

public record LoginRequest(string Username, string Password);
public record RefreshRequest(string RefreshToken);
public record TokenResponse(string AccessToken, string RefreshToken);

public static class IssuerApp
{
    /// <summary>Buduje wystawce. Testy wolaja to z adresem http://127.0.0.1:0 (losowy wolny port).</summary>
    public static WebApplication Build(string[] args)
    {
        var builder = WebApplication.CreateBuilder(args);
        builder.Logging.ClearProviders();

        builder.Services.AddSingleton(TimeProvider.System);
        builder.Services.AddSingleton<KeyRing>();
        builder.Services.AddSingleton<RefreshTokenStore>();

        var app = builder.Build();

        // DEMO: jedyny uzytkownik, haslo jawne w kodzie. NIGDY tak w produkcji.
        app.MapPost("/auth/login", (LoginRequest req, KeyRing keys, TimeProvider time, RefreshTokenStore store) =>
            req is { Username: "alice", Password: "demo-only-password" }
                ? Results.Ok(new TokenResponse(keys.IssueAccessToken("alice", time), store.Create("alice")))
                : Results.Unauthorized());

        app.MapPost("/auth/refresh", (RefreshRequest req, KeyRing keys, TimeProvider time, RefreshTokenStore store) =>
        {
            var r = store.Rotate(req.RefreshToken);
            return r.Status == RotateStatus.Ok
                ? Results.Ok(new TokenResponse(keys.IssueAccessToken(r.User!, time), r.NewToken!))
                : Results.Json(new { error = r.Status.ToString() }, statusCode: StatusCodes.Status401Unauthorized);
        });

        // Minimalny dokument "OpenID Connect discovery" -- tyle wystarczy ConfigurationManager z JwtBearer.
        app.MapGet("/.well-known/openid-configuration", (HttpRequest http) =>
        {
            var self = $"{http.Scheme}://{http.Host}";
            return Results.Json(new { issuer = IssuerDefaults.Issuer, jwks_uri = $"{self}/.well-known/jwks.json" });
        });

        app.MapGet("/.well-known/jwks.json", (KeyRing keys) => Results.Json(keys.Jwks()));

        return app;
    }
}
