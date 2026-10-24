using Microsoft.IdentityModel.JsonWebTokens;
using Microsoft.IdentityModel.Tokens;
using TunitWebApi;

namespace TunitWebApi.Tests;

/// <summary>
/// Generuje tokeny JWT podpisane TYM SAMYM kluczem demo co aplikacja pod testem
/// (TunitWebApi.JwtDemoSettings) -- tak jak w realnym projekcie: testy integracyjne nie
/// zgaduja formatu tokenu ani nie trzymaja wlasnej kopii konfiguracji, tylko uzywaja
/// dokladnie tych samych stalych (Issuer/Audience/SigningKey), co startup API.
/// </summary>
public static class TokenFactory
{
    private static readonly JsonWebTokenHandler Handler = new();

    public static string CreateToken(
        string subject,
        string name,
        string[]? roles = null,
        TimeSpan? lifetime = null,
        SymmetricSecurityKey? signingKeyOverride = null)
    {
        var claims = new Dictionary<string, object>
        {
            [JwtRegisteredClaimNames.Sub] = subject,
            ["name"] = name,
        };

        if (roles is { Length: > 0 })
        {
            // Wiecej niz jedna rola -> tablica JSON w claimie "role" (JsonWebTokenHandler
            // serializuje IEnumerable<string> jako tablice, nie jako jeden string z przecinkami).
            claims["role"] = roles.Length == 1 ? roles[0] : roles;
        }

        var descriptor = new SecurityTokenDescriptor
        {
            Issuer = JwtDemoSettings.Issuer,
            Audience = JwtDemoSettings.Audience,
            Claims = claims,
            Expires = DateTime.UtcNow.Add(lifetime ?? TimeSpan.FromMinutes(5)),
            SigningCredentials = new SigningCredentials(
                signingKeyOverride ?? JwtDemoSettings.SigningKey,
                SecurityAlgorithms.HmacSha256)
        };

        return Handler.CreateToken(descriptor);
    }
}
