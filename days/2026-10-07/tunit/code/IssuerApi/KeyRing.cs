using System.Security.Cryptography;
using Microsoft.IdentityModel.JsonWebTokens;
using Microsoft.IdentityModel.Tokens;

namespace IssuerApi;

public static class IssuerDefaults
{
    // Issuer jako staly identyfikator (string), nie adres URL -- port serwera w testach jest losowy.
    public const string Issuer = "demo-issuer";
    public const string Audience = "demo-api";
    public static readonly TimeSpan AccessLifetime = TimeSpan.FromMinutes(10);
    public static readonly TimeSpan RefreshLifetime = TimeSpan.FromDays(7);
}

/// <summary>
/// Pierscien kluczy RSA z rotacja: wiele kluczy naraz (kazdy z wlasnym kid), jeden AKTYWNY do
/// podpisywania, wszystkie PUBLIKOWANE w JWKS dopoki ich nie wycofamy (Retire).
/// Klucze sa efemeryczne (w pamieci, tylko demo) -- w repo nie ma zadnego klucza prywatnego.
/// </summary>
public sealed class KeyRing : IDisposable
{
    private sealed record Entry(string Kid, RSA Rsa);

    private readonly object _gate = new();
    private readonly List<Entry> _keys = [];
    private int _counter;
    private string _activeKid = "";
    private int _jwksFetches;

    public KeyRing() => Rotate();

    /// <summary>Ile razy ktos pobral JWKS (licznik po stronie wystawcy -- dowod ruchu HTTP).</summary>
    public int JwksFetches => Volatile.Read(ref _jwksFetches);

    public string ActiveKid { get { lock (_gate) return _activeKid; } }

    /// <summary>Generuje nowy klucz i robi go aktywnym. Stare zostaja w JWKS (okno nakladania).</summary>
    public string Rotate()
    {
        lock (_gate)
        {
            var kid = $"key-{++_counter}";
            _keys.Add(new Entry(kid, RSA.Create(2048)));
            _activeKid = kid;
            return kid;
        }
    }

    /// <summary>Usuwa klucz z JWKS (po tym wystawca juz go nie publikuje).</summary>
    public void Retire(string kid)
    {
        lock (_gate)
        {
            if (kid == _activeKid) throw new InvalidOperationException("Nie wycofuje aktywnego klucza.");
            var e = _keys.Single(k => k.Kid == kid);
            _keys.Remove(e);
            e.Rsa.Dispose();
        }
    }

    public string IssueAccessToken(string user, TimeProvider time)
    {
        Entry active;
        lock (_gate) active = _keys.Single(k => k.Kid == _activeKid);

        var now = time.GetUtcNow().UtcDateTime;
        var descriptor = new SecurityTokenDescriptor
        {
            Issuer = IssuerDefaults.Issuer,
            Audience = IssuerDefaults.Audience,
            Claims = new Dictionary<string, object> { ["sub"] = user },
            IssuedAt = now,
            NotBefore = now,
            Expires = now + IssuerDefaults.AccessLifetime,
            SigningCredentials = new SigningCredentials(
                new RsaSecurityKey(active.Rsa) { KeyId = active.Kid }, SecurityAlgorithms.RsaSha256),
        };
        return new JsonWebTokenHandler().CreateToken(descriptor);
    }

    public object Jwks()
    {
        Interlocked.Increment(ref _jwksFetches);
        lock (_gate)
        {
            return new
            {
                keys = _keys.Select(k =>
                {
                    var p = k.Rsa.ExportParameters(includePrivateParameters: false);
                    return new
                    {
                        kty = "RSA", use = "sig", alg = "RS256", kid = k.Kid,
                        n = Base64UrlEncoder.Encode(p.Modulus!),
                        e = Base64UrlEncoder.Encode(p.Exponent!),
                    };
                }).ToArray(),
            };
        }
    }

    public void Dispose()
    {
        lock (_gate) foreach (var k in _keys) k.Rsa.Dispose();
    }
}
