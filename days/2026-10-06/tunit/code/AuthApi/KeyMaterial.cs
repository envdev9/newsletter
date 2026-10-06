using System.Security.Cryptography;
using Microsoft.IdentityModel.Tokens;

namespace AuthApi;

/// <summary>
/// Para kluczy RSA aplikacji. Domyslnie EFEMERYCZNA (nowa para przy kazdym starcie
/// procesu) -- zadnego klucza prywatnego w repo. W produkcji klucz pochodzi z KMS/HSM/
/// Key Vault; ten kod to demonstracja mechaniki, NIGDY nie wzorzec zarzadzania kluczami.
/// Testy podmieniaja ten singleton na wlasny klucz (patrz AuthTestKit).
/// </summary>
public sealed class KeyMaterial : IDisposable
{
    private readonly RSA _rsa;

    public KeyMaterial() : this(RSA.Create(2048)) { }

    public KeyMaterial(RSA rsa)
    {
        _rsa = rsa;
        // kid = skrot SHA-256 klucza publicznego -- stabilny, deterministyczny identyfikator
        var pub = _rsa.ExportSubjectPublicKeyInfo();
        KeyId = Base64UrlEncoder.Encode(SHA256.HashData(pub))[..16];
    }

    public string KeyId { get; }

    /// <summary>Klucz z czescia PRYWATNA -- uzywany wylacznie do podpisywania (login/refresh).</summary>
    public RsaSecurityKey SigningKey => new(_rsa) { KeyId = KeyId };

    /// <summary>Klucz tylko PUBLICZNY -- tym waliduje JwtBearer. Nie da sie nim niczego podpisac.</summary>
    public RsaSecurityKey ValidationKey => new(_rsa.ExportParameters(includePrivateParameters: false)) { KeyId = KeyId };

    public RSAParameters PublicParameters => _rsa.ExportParameters(includePrivateParameters: false);

    public void Dispose() => _rsa.Dispose();
}
