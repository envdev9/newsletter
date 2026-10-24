using System.Security.Claims;
using Microsoft.IdentityModel.JsonWebTokens;
using Microsoft.IdentityModel.Tokens;

namespace AuthApi;

public static class JwtDefaults
{
    public const string Issuer = "tunit-demo-issuer";
    public const string Audience = "tunit-demo-api";
    public static readonly TimeSpan AccessLifetime = TimeSpan.FromSeconds(60);
    public static readonly TimeSpan RefreshLifetime = TimeSpan.FromDays(7);
}

/// <summary>Wystawia access tokeny RS256. Czas bierze z TimeProvider -- testy go kontroluja.</summary>
public sealed class TokenService(KeyMaterial keys, TimeProvider time)
{
    public string IssueAccessToken(string username)
    {
        var now = time.GetUtcNow().UtcDateTime;
        var descriptor = new SecurityTokenDescriptor
        {
            Issuer = JwtDefaults.Issuer,
            Audience = JwtDefaults.Audience,
            Subject = new ClaimsIdentity([new Claim("sub", username), new Claim("name", username)]),
            IssuedAt = now,
            NotBefore = now,
            Expires = now + JwtDefaults.AccessLifetime,
            SigningCredentials = new SigningCredentials(keys.SigningKey, SecurityAlgorithms.RsaSha256),
        };
        return new JsonWebTokenHandler().CreateToken(descriptor);
    }
}
