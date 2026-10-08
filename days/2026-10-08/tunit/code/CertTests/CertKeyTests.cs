using System.Net;
using System.Security.Cryptography;
using System.Security.Cryptography.X509Certificates;
using System.Text.Json;
using IssuerApi;
using Microsoft.IdentityModel.JsonWebTokens;
using Microsoft.IdentityModel.Tokens;

namespace CertTests;

public class CertKeyTests
{
    private static readonly TimeSpan Forced = TimeSpan.FromSeconds(1);

    // ---------------------------------------------------------------- 1. rotacja z wyprzedzeniem

    [Test]
    [Arguments(false, HttpStatusCode.Unauthorized)] // opublikowany i od razu aktywny: pierwszy token pada
    [Arguments(true, HttpStatusCode.OK)]            // najpierw publikacja + odswiezenie walidatora, potem aktywacja
    [DisplayName("Rotacja: walidator odswiezyl JWKS przed aktywacja=$refreshBeforeActivate -> pierwszy token z nowym kluczem: $expectedFirst")]
    public async Task PrePublish_FirstTokenWithNewKey(bool refreshBeforeActivate, HttpStatusCode expectedFirst)
    {
        await using var issuer = await Issuer.StartAsync(KidMode.Thumbprint);
        await using var validator = await Validator.StartAsync(issuer, Forced);

        await Assert.That(await validator.StatusAsync(await issuer.LoginAsync())).IsEqualTo(HttpStatusCode.OK); // cache walidatora ma stary klucz

        var kid2 = issuer.Keys.Add(DateTimeOffset.UtcNow.AddHours(-1), DateTimeOffset.UtcNow.AddDays(90)); // tylko publikacja
        var refreshed = true;
        if (refreshBeforeActivate)
            refreshed = await validator.ForceJwksRefreshAsync(issuer, TimeSpan.FromSeconds(5));
        var fetchesBeforeActivation = issuer.Keys.JwksFetches;

        issuer.Keys.Activate(kid2);
        var token = await issuer.LoginAsync();
        var first = await validator.StatusAsync(token);
        Console.WriteLine($"[pomiar] odswiezenie-przed-aktywacja={refreshBeforeActivate} (udane={refreshed}) pierwszy-status={(int)first} pobrania-JWKS: przed-aktywacja={fetchesBeforeActivation} po-pierwszym-zadaniu={issuer.Keys.JwksFetches}");

        await Assert.That(first).IsEqualTo(expectedFirst);
        if (expectedFirst == HttpStatusCode.OK)
        {
            // Rotacja z wyprzedzeniem: sama aktywacja nie kosztuje wystawcy ani jednego dodatkowego pobrania JWKS.
            await Assert.That(issuer.Keys.JwksFetches).IsEqualTo(fetchesBeforeActivation);
        }
    }

    // ---------------------------------------------------------------- 2. co faktycznie jest w JWKS i w tokenie

    [Test]
    public async Task Jwks_CarriesCertificate_AndNoPrivateMaterial()
    {
        await using var issuer = await Issuer.StartAsync(KidMode.Thumbprint);
        var json = await issuer.JwksJsonAsync();
        using var doc = JsonDocument.Parse(json);
        var key = doc.RootElement.GetProperty("keys").EnumerateArray().Single();

        var kid = key.GetProperty("kid").GetString()!;
        var x5tS256 = key.GetProperty("x5t#S256").GetString()!;
        var der = Convert.FromBase64String(key.GetProperty("x5c").EnumerateArray().Single().GetString()!);
        using var cert = X509CertificateLoader.LoadCertificate(der);
        var certHash = Base64UrlEncoder.Encode(cert.GetCertHash(HashAlgorithmName.SHA256));

        var names = string.Join(",", key.EnumerateObject().Select(p => p.Name));
        Console.WriteLine($"[pomiar] pola JWKS: {names}");
        Console.WriteLine($"[pomiar] kid==x5t#S256: {kid == x5tS256}; cert.Subject={cert.Subject}; HasPrivateKey(z DER)={cert.HasPrivateKey}");

        using (Assert.Multiple())
        {
            await Assert.That(kid).IsEqualTo(x5tS256);          // kid = odcisk SHA-256 certyfikatu
            await Assert.That(certHash).IsEqualTo(x5tS256);     // odcisk z x5c zgadza sie z deklarowanym
            await Assert.That(cert.HasPrivateKey).IsFalse();    // x5c to sam certyfikat publiczny
            foreach (var priv in new[] { "d", "p", "q", "dp", "dq", "qi" })
                await Assert.That(key.TryGetProperty(priv, out _)).IsFalse();
        }
    }

    [Test]
    public async Task Token_Header_ForCertificateKey()
    {
        await using var issuer = await Issuer.StartAsync(KidMode.Thumbprint);
        var jwt = new JsonWebToken(await issuer.LoginAsync());
        var headerJson = Base64UrlEncoder.Decode(jwt.EncodedHeader);
        Console.WriteLine($"[pomiar] naglowek tokenu: {headerJson}");

        await Assert.That(jwt.Alg).IsEqualTo("RS256");
        await Assert.That(jwt.Kid).IsEqualTo(issuer.Keys.ActiveKid);
    }

    // ---------------------------------------------------------------- 3. waznosc certyfikatu: kto ja egzekwuje?

    [Test]
    [Arguments("expired", false)]
    [Arguments("expired", true)]
    [Arguments("not-yet-valid", false)]
    [Arguments("not-yet-valid", true)]
    [DisplayName("Certyfikat $which, walidator egzekwuje waznosc=$enforce")]
    public async Task CertificateValidity_IsEnforcedOnlyIfWeDoIt(string which, bool enforce)
    {
        await using var issuer = await Issuer.StartAsync(KidMode.Thumbprint);
        await using var validator = await Validator.StartAsync(issuer, Forced, enforceCertValidity: enforce);

        var now = DateTimeOffset.UtcNow;
        var kid = which == "expired"
            ? issuer.Keys.Add(now.AddDays(-30), now.AddDays(-1))      // wygasl wczoraj
            : issuer.Keys.Add(now.AddDays(1), now.AddDays(90));       // zacznie sie jutro
        issuer.Keys.Activate(kid);

        var token = await issuer.LoginAsync(); // sam token jest swiezy i poprawny -- zly jest tylko certyfikat
        var status = await validator.StatusAsync(token);
        var types = string.Join(",", validator.Options.SeenKeyTypes.Distinct());
        Console.WriteLine($"[pomiar] cert={which} egzekwowanie={enforce} -> status={(int)status} typy-kluczy-w-walidatorze={types}");

        await Assert.That(status).IsEqualTo(enforce ? HttpStatusCode.Unauthorized : HttpStatusCode.OK);
    }

    // ---------------------------------------------------------------- 4. dwie instancje wystawcy

    [Test]
    [Arguments(KidMode.Sequential)]
    [Arguments(KidMode.Thumbprint)]
    [DisplayName("Dwie instancje wystawcy, kid=$mode: token instancji B u walidatora zaufanego A")]
    public async Task TwoIssuerInstances_TokenFromOtherInstance(KidMode mode)
    {
        await using var a = await Issuer.StartAsync(mode);
        await using var b = await Issuer.StartAsync(mode);
        await using var validatorOfA = await Validator.StartAsync(a, Forced);

        var kidA = a.Keys.ActiveKid;
        var kidB = b.Keys.ActiveKid;
        await Assert.That(await validatorOfA.StatusAsync(await a.LoginAsync())).IsEqualTo(HttpStatusCode.OK); // warmup, 1 pobranie

        var fetchesBefore = a.Keys.JwksFetches;
        var statusB = await validatorOfA.StatusAsync(await b.LoginAsync());
        await Task.Delay(300); // ewentualne odswiezenie w tle
        var fetchesAfter = a.Keys.JwksFetches;
        Console.WriteLine($"[pomiar] kid={mode}: kidA==kidB: {kidA == kidB}; token B u walidatora A -> {(int)statusB}; pobrania JWKS u A: {fetchesBefore} -> {fetchesAfter}");

        await Assert.That(statusB).IsEqualTo(HttpStatusCode.Unauthorized); // w obu trybach: klucz B nigdy nie jest w JWKS A
        await Assert.That(kidA == kidB).IsEqualTo(mode == KidMode.Sequential);
    }
}
