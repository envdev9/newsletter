using System.Security.Claims;
using System.Security.Cryptography;
using System.Text;
using AuthApi;
using Microsoft.IdentityModel.JsonWebTokens;
using Microsoft.IdentityModel.Tokens;

namespace AuthTestKit;

/// <summary>
/// Fabryka tokenow dla testow -- w tym FALSZYWYCH. Kazdy wariant ataku ma nazwe, zeby
/// jeden test parametryzowany ([Arguments]) przechodzil po calej liscie.
/// </summary>
public static class Forge
{
    public static readonly string[] AttackNames =
    [
        "attacker-rsa-key",
        "alg-none",
        "hs256-public-key-der-as-secret",
        "hs256-public-key-pem-as-secret",
        "wrong-audience",
        "wrong-issuer",
        "tampered-payload",
        "expired-1s-ago",
    ];

    /// <summary>Poprawny RS256 podpisany kluczem <paramref name="key"/>; reszta parametrow do psucia.</summary>
    public static string Rs256(
        RSA key, DateTimeOffset now, string sub = "alice",
        string issuer = JwtDefaults.Issuer, string audience = JwtDefaults.Audience,
        TimeSpan? lifetime = null)
    {
        var life = lifetime ?? JwtDefaults.AccessLifetime;
        var nowUtc = now.UtcDateTime;
        return new JsonWebTokenHandler().CreateToken(new SecurityTokenDescriptor
        {
            Issuer = issuer,
            Audience = audience,
            Subject = new ClaimsIdentity([new Claim("sub", sub), new Claim("name", sub)]),
            IssuedAt = nowUtc.AddMinutes(-1),
            NotBefore = nowUtc.AddMinutes(-1),
            Expires = nowUtc + life,
            SigningCredentials = new SigningCredentials(new RsaSecurityKey(key), SecurityAlgorithms.RsaSha256),
        });
    }

    public static string Build(string attack, AuthFixture f)
    {
        var now = f.Time.GetUtcNow();
        switch (attack)
        {
            case "attacker-rsa-key":
                using (var attackerKey = RSA.Create(2048))
                    return Rs256(attackerKey, now);

            case "alg-none":
                return Unsigned(now);

            case "hs256-public-key-der-as-secret":
                return Hs256(f.TestRsa.ExportSubjectPublicKeyInfo(), now);

            case "hs256-public-key-pem-as-secret":
                return Hs256(Encoding.UTF8.GetBytes(f.TestRsa.ExportSubjectPublicKeyInfoPem()), now);

            case "wrong-audience":
                return Rs256(f.TestRsa, now, audience: "inne-api");

            case "wrong-issuer":
                return Rs256(f.TestRsa, now, issuer: "obcy-issuer");

            case "tampered-payload":
                var valid = Rs256(f.TestRsa, now, sub: "alice");
                var parts = valid.Split('.');
                var evil = Base64UrlEncoder.Encode(Encoding.UTF8.GetBytes(
                    $$"""{"sub":"admin","name":"admin","iss":"{{JwtDefaults.Issuer}}","aud":"{{JwtDefaults.Audience}}","exp":{{now.AddHours(1).ToUnixTimeSeconds()}}}"""));
                return $"{parts[0]}.{evil}.{parts[2]}"; // stary podpis, nowy payload

            case "expired-1s-ago":
                // poprawny podpis i claimy, ale exp = teraz - 1s (kontrola: czas jest walidowany)
                return Rs256(f.TestRsa, now, lifetime: TimeSpan.FromSeconds(-1));

            default:
                throw new ArgumentOutOfRangeException(nameof(attack), attack, null);
        }
    }

    private static string Hs256(byte[] secret, DateTimeOffset now)
    {
        var nowUtc = now.UtcDateTime;
        return new JsonWebTokenHandler().CreateToken(new SecurityTokenDescriptor
        {
            Issuer = JwtDefaults.Issuer,
            Audience = JwtDefaults.Audience,
            Subject = new ClaimsIdentity([new Claim("sub", "admin"), new Claim("name", "admin")]),
            NotBefore = nowUtc.AddMinutes(-1),
            Expires = nowUtc.AddMinutes(5),
            SigningCredentials = new SigningCredentials(new SymmetricSecurityKey(secret), SecurityAlgorithms.HmacSha256),
        });
    }

    private static string Unsigned(DateTimeOffset now)
    {
        var header = Base64UrlEncoder.Encode(Encoding.UTF8.GetBytes("""{"alg":"none","typ":"JWT"}"""));
        var payload = Base64UrlEncoder.Encode(Encoding.UTF8.GetBytes(
            $$"""{"sub":"admin","name":"admin","iss":"{{JwtDefaults.Issuer}}","aud":"{{JwtDefaults.Audience}}","exp":{{now.AddHours(1).ToUnixTimeSeconds()}}}"""));
        return $"{header}.{payload}.";
    }
}
