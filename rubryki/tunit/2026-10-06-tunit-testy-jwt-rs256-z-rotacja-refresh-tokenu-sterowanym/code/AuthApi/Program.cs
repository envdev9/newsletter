using AuthApi;
using Microsoft.AspNetCore.Authentication.JwtBearer;
using Microsoft.AspNetCore.Authorization;
using Microsoft.IdentityModel.Tokens;

var builder = WebApplication.CreateBuilder(args);

builder.Services.AddSingleton(TimeProvider.System);
builder.Services.AddSingleton<KeyMaterial>();
builder.Services.AddSingleton<TokenService>();
builder.Services.AddSingleton<RefreshTokenStore>();

builder.Services.AddAuthentication(JwtBearerDefaults.AuthenticationScheme).AddJwtBearer();

// Opcje JwtBearer budowane z DI (KeyMaterial + TimeProvider), a NIE z konfiguracji czytanej
// eagerly w Program.cs -- dzieki temu testy moga podmienic klucz i zegar przez
// ConfigureTestServices, bez zadnych hackow na konfiguracji.
builder.Services.AddOptions<JwtBearerOptions>(JwtBearerDefaults.AuthenticationScheme)
    .Configure<KeyMaterial, TimeProvider>((options, keys, time) =>
    {
        options.MapInboundClaims = false; // lekcja z wydania #9
        options.TokenValidationParameters = new TokenValidationParameters
        {
            ValidateIssuer = true,
            ValidIssuer = JwtDefaults.Issuer,
            ValidateAudience = true,
            ValidAudience = JwtDefaults.Audience,
            ValidateIssuerSigningKey = true,
            IssuerSigningKey = keys.ValidationKey,           // tylko klucz PUBLICZNY
            RequireSignedTokens = true,
            ValidAlgorithms = [SecurityAlgorithms.RsaSha256], // twarda biala lista algorytmow
            ValidateLifetime = true,
            ClockSkew = TimeSpan.Zero,
            LifetimeValidator = (notBefore, expires, _, _) =>
            {
                var now = time.GetUtcNow().UtcDateTime;
                return (notBefore is null || notBefore <= now) && (expires is null || now < expires);
            },
        };
    });
builder.Services.AddAuthorization();

var app = builder.Build();

app.UseAuthentication();
app.UseAuthorization();

// DEMO: jedyny uzytkownik, haslo jawne w kodzie. NIGDY tak w produkcji.
app.MapPost("/auth/login", (LoginRequest req, TokenService tokens, RefreshTokenStore store) =>
{
    if (req.Username != "alice" || req.Password != "demo-only-password")
        return Results.Unauthorized();

    return Results.Ok(new TokenResponse(
        tokens.IssueAccessToken(req.Username),
        store.Create(req.Username),
        (int)JwtDefaults.AccessLifetime.TotalSeconds));
});

app.MapPost("/auth/refresh", (RefreshRequest req, TokenService tokens, RefreshTokenStore store) =>
{
    var result = store.Rotate(req.RefreshToken);
    return result.Status == RotateStatus.Ok
        ? Results.Ok(new TokenResponse(
            tokens.IssueAccessToken(result.User!),
            result.NewToken!,
            (int)JwtDefaults.AccessLifetime.TotalSeconds))
        : Results.Json(new { error = result.Status.ToString() }, statusCode: StatusCodes.Status401Unauthorized);
});

app.MapGet("/secure/profile", [Authorize] (System.Security.Claims.ClaimsPrincipal user) =>
    Results.Ok(new ProfileResponse(user.FindFirst("sub")?.Value ?? "", user.FindFirst("name")?.Value)));

// JWKS: publiczna czesc klucza -- po to jest asymetria; kazdy serwis moze walidowac
// tokeny, a nikt poza wystawca nie moze ich podpisac.
app.MapGet("/.well-known/jwks.json", (KeyMaterial keys) =>
{
    var p = keys.PublicParameters;
    return Results.Json(new
    {
        keys = new[]
        {
            new
            {
                kty = "RSA", use = "sig", alg = "RS256", kid = keys.KeyId,
                n = Base64UrlEncoder.Encode(p.Modulus!),
                e = Base64UrlEncoder.Encode(p.Exponent!),
            },
        },
    });
});

app.Run();

public record LoginRequest(string Username, string Password);
public record RefreshRequest(string RefreshToken);
public record TokenResponse(string AccessToken, string RefreshToken, int ExpiresIn);
public record ProfileResponse(string Sub, string? Name);

public partial class Program;
