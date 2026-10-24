using Microsoft.AspNetCore.Authentication.JwtBearer;
using Microsoft.AspNetCore.Authorization;
using Microsoft.IdentityModel.Protocols;
using Microsoft.IdentityModel.Protocols.OpenIdConnect;
using Microsoft.IdentityModel.Tokens;

namespace ResourceApi;

/// <param name="Authority">Adres wystawcy; z niego pobierane sa metadane i JWKS (po HTTP).</param>
/// <param name="AutomaticRefreshInterval">Jak czesto ConfigurationManager odswieza metadane sam z siebie.</param>
/// <param name="RefreshInterval">Minimalny odstep miedzy WYMUSZONYMI odswiezeniami (RequestRefresh).</param>
/// <param name="RefreshOnIssuerKeyNotFound">Czy nieznany kid ma wymuszac odswiezenie JWKS.</param>
/// <param name="LastKnownGoodLifetime">null = domyslne ustawienie biblioteki; wartosc = wlasny ConfigurationManager.</param>
public sealed record ResourceOptions(
    string Authority,
    TimeSpan AutomaticRefreshInterval,
    TimeSpan RefreshInterval,
    bool RefreshOnIssuerKeyNotFound = true,
    TimeSpan? LastKnownGoodLifetime = null);

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
                options.AutomaticRefreshInterval = o.AutomaticRefreshInterval;
                options.RefreshInterval = o.RefreshInterval;
                if (o.LastKnownGoodLifetime is { } lkg)
                {
                    // Wlasny ConfigurationManager -- tylko po to, by ustawic LastKnownGoodLifetime
                    // (JwtBearerOptions nie ma na to wlasciwosci).
                    options.ConfigurationManager = new ConfigurationManager<OpenIdConnectConfiguration>(
                        options.MetadataAddress,
                        new OpenIdConnectConfigurationRetriever(),
                        new HttpDocumentRetriever { RequireHttps = false })
                    {
                        AutomaticRefreshInterval = o.AutomaticRefreshInterval,
                        RefreshInterval = o.RefreshInterval,
                        LastKnownGoodLifetime = lkg,
                    };
                }
                options.RefreshOnIssuerKeyNotFound = o.RefreshOnIssuerKeyNotFound;
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
