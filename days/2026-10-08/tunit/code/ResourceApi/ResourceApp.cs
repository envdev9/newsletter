using System.Collections.Concurrent;
using Microsoft.AspNetCore.Authentication.JwtBearer;
using Microsoft.AspNetCore.Authorization;
using Microsoft.IdentityModel.Tokens;

namespace ResourceApi;

/// <param name="Authority">Adres wystawcy; z niego pobierane sa metadane i JWKS (po HTTP).</param>
/// <param name="RefreshInterval">Minimalny odstep miedzy WYMUSZONYMI odswiezeniami (RequestRefresh).</param>
/// <param name="EnforceCertificateValidity">
/// Czy walidator sam sprawdza NotBefore/NotAfter certyfikatu, z ktorego pochodzi klucz.
/// false = zachowanie domyslne biblioteki (zmierzone w testach).
/// </param>
public sealed record ResourceOptions(
    string Authority,
    TimeSpan RefreshInterval,
    bool EnforceCertificateValidity = false)
{
    /// <summary>Typy kluczy, ktore walidator faktycznie dostal od biblioteki (sonda pomiarowa do testow).</summary>
    public ConcurrentQueue<string> SeenKeyTypes { get; } = new();
}

public static class ResourceApp
{
    public static WebApplication Build(string[] args, ResourceOptions o)
    {
        var builder = WebApplication.CreateBuilder(args);
        builder.Logging.ClearProviders();

        builder.Services.AddAuthentication(JwtBearerDefaults.AuthenticationScheme)
            .AddJwtBearer(options =>
            {
                options.MetadataAddress = $"{o.Authority}/.well-known/openid-configuration";
                options.RequireHttpsMetadata = false; // demo na http://127.0.0.1; produkcja: ZAWSZE https
                options.MapInboundClaims = false;
                options.RefreshInterval = o.RefreshInterval;
                options.TokenValidationParameters = new TokenValidationParameters
                {
                    ValidateIssuer = true,
                    ValidIssuer = "demo-issuer",
                    ValidateAudience = true,
                    ValidAudience = "demo-api",
                    ValidateIssuerSigningKey = true,
                    RequireSignedTokens = true,
                    ValidAlgorithms = [SecurityAlgorithms.RsaSha256],
                    ValidateLifetime = true,
                    IssuerSigningKeyValidator = (key, _, _) =>
                    {
                        o.SeenKeyTypes.Enqueue(key.GetType().Name);
                        if (o.EnforceCertificateValidity && key is X509SecurityKey x)
                        {
                            var now = DateTime.Now;
                            return now >= x.Certificate.NotBefore && now <= x.Certificate.NotAfter;
                        }
                        return true;
                    },
                    // Klucze NIE sa tu wpisane na stale: bierze je ConfigurationManager z JWKS wystawcy.
                };
            });
        builder.Services.AddAuthorization();

        var app = builder.Build();
        app.UseAuthentication();
        app.UseAuthorization();

        app.MapGet("/secure/profile", [Authorize] (System.Security.Claims.ClaimsPrincipal user) =>
            Results.Ok(new { sub = user.FindFirst("sub")?.Value }));

        return app;
    }
}
