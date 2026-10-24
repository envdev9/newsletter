using System.Security.Cryptography;
using System.Security.Cryptography.X509Certificates;
using Microsoft.IdentityModel.JsonWebTokens;
using Microsoft.IdentityModel.Tokens;

namespace IssuerApi;

public static class IssuerDefaults
{
    // Issuer jako staly identyfikator (string), nie adres URL -- port serwera w testach jest losowy.
    public const string Issuer = "demo-issuer";
    public const string Audience = "demo-api";
    public static readonly TimeSpan AccessLifetime = TimeSpan.FromMinutes(10);
}

/// <summary>Skad bierze sie identyfikator klucza (kid) w JWKS i naglowku tokenu.</summary>
public enum KidMode
{
    /// <summary>"key-1", "key-2"... -- czytelne, ale dwie instancje wystawcy wygeneruja TE SAME kid.</summary>
    Sequential,
    /// <summary>SHA-256 certyfikatu (base64url), czyli to samo co x5t#S256 -- unikalne miedzy instancjami.</summary>
    Thumbprint,
}

/// <summary>
/// Pierscien kluczy zbudowany na certyfikatach X.509 (samopodpisanych, generowanych w pamieci).
/// Klucz ma trzy niezalezne stany: OPUBLIKOWANY w JWKS, AKTYWNY (tym podpisujemy) i wycofany.
/// Dzieki temu mozna zrobic rotacje z wyprzedzeniem: najpierw Add (publikacja), potem Activate.
/// Zadnego klucza prywatnego w repo -- wszystko powstaje przy starcie procesu.
/// </summary>
public sealed class KeyRing : IDisposable
{
    private sealed record Entry(string Kid, X509Certificate2 Cert);

    private readonly object _gate = new();
    private readonly List<Entry> _keys = [];
    private readonly KidMode _mode;
    private int _counter;
    private string _activeKid = "";
    private int _jwksFetches;

    public KeyRing(KidMode mode = KidMode.Thumbprint)
    {
        _mode = mode;
        var now = DateTimeOffset.UtcNow;
        var kid = Add(now.AddHours(-1), now.AddDays(90));
        Activate(kid);
    }

    /// <summary>Ile razy ktos pobral JWKS (licznik po stronie wystawcy -- dowod ruchu HTTP).</summary>
    public int JwksFetches => Volatile.Read(ref _jwksFetches);

    public string ActiveKid { get { lock (_gate) return _activeKid; } }

    /// <summary>Generuje certyfikat i PUBLIKUJE go w JWKS, ale jeszcze nim nie podpisuje.</summary>
    public string Add(DateTimeOffset notBefore, DateTimeOffset notAfter)
    {
        lock (_gate)
        {
            using var rsa = RSA.Create(2048);
            var req = new CertificateRequest($"CN=demo-issuer-{++_counter}", rsa, HashAlgorithmName.SHA256, RSASignaturePadding.Pkcs1);
            // CreateSelfSigned zwraca certyfikat z dolaczonym kluczem prywatnym (kopia klucza z 'rsa').
            var cert = req.CreateSelfSigned(notBefore, notAfter);
            var kid = _mode == KidMode.Thumbprint
                ? Base64UrlEncoder.Encode(cert.GetCertHash(HashAlgorithmName.SHA256))
                : $"key-{_counter}";
            _keys.Add(new Entry(kid, cert));
            return kid;
        }
    }

    /// <summary>Od teraz tym kluczem podpisujemy nowe tokeny.</summary>
    public void Activate(string kid)
    {
        lock (_gate)
        {
            if (_keys.All(k => k.Kid != kid)) throw new InvalidOperationException($"Nieznany kid {kid}.");
            _activeKid = kid;
        }
    }

    /// <summary>Rotacja "natychmiastowa": publikacja i aktywacja w jednym kroku.</summary>
    public string Rotate()
    {
        var now = DateTimeOffset.UtcNow;
        var kid = Add(now.AddHours(-1), now.AddDays(90));
        Activate(kid);
        return kid;
    }

    /// <summary>Usuwa klucz z JWKS (po tym wystawca juz go nie publikuje).</summary>
    public void Retire(string kid)
    {
        lock (_gate)
        {
            if (kid == _activeKid) throw new InvalidOperationException("Nie wycofuje aktywnego klucza.");
            var e = _keys.Single(k => k.Kid == kid);
            _keys.Remove(e);
            e.Cert.Dispose();
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
                new X509SecurityKey(active.Cert) { KeyId = active.Kid }, SecurityAlgorithms.RsaSha256),
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
                    using var pub = k.Cert.GetRSAPublicKey()!;
                    var p = pub.ExportParameters(includePrivateParameters: false);
                    return new Dictionary<string, object>
                    {
                        ["kty"] = "RSA", ["use"] = "sig", ["alg"] = "RS256", ["kid"] = k.Kid,
                        ["n"] = Base64UrlEncoder.Encode(p.Modulus!),
                        ["e"] = Base64UrlEncoder.Encode(p.Exponent!),
                        // x5c: lancuch certyfikatow (tu jeden, DER w zwyklym base64, NIE base64url).
                        ["x5c"] = new[] { Convert.ToBase64String(k.Cert.RawData) },
                        ["x5t#S256"] = Base64UrlEncoder.Encode(k.Cert.GetCertHash(HashAlgorithmName.SHA256)),
                    };
                }).ToArray(),
            };
        }
    }

    public void Dispose()
    {
        lock (_gate) foreach (var k in _keys) k.Cert.Dispose();
    }
}
