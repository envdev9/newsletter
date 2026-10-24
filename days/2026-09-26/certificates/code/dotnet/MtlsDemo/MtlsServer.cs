using System.Net;
using System.Net.Security;
using System.Security.Cryptography.X509Certificates;
using Microsoft.AspNetCore.Builder;
using Microsoft.AspNetCore.Http;
using Microsoft.AspNetCore.Server.Kestrel.Core;
using Microsoft.AspNetCore.Server.Kestrel.Https;
using Microsoft.Extensions.Logging;

namespace MtlsDemo;

public sealed record ServerOptions(
    Pki Pki,
    int Port,
    string CertName = "server",      // "server" (z SAN) albo "server-nosan"
    bool SendIntermediate = true,    // czy serwer dosyla intermediate w handshake
    bool CheckClientEku = true,      // czy wymagamy EKU clientAuth od klienta
    bool ShowKestrelDebug = false);

public static class MtlsServer
{
    public static async Task<WebApplication> StartAsync(ServerOptions o, Action<string> log)
    {
        var builder = WebApplication.CreateSlimBuilder();
        builder.Logging.ClearProviders();
        if (o.ShowKestrelDebug)
        {
            builder.Logging.AddSimpleConsole(c => c.SingleLine = true);
            builder.Logging.SetMinimumLevel(LogLevel.Warning);
            builder.Logging.AddFilter("Microsoft.AspNetCore.Server.Kestrel", LogLevel.Debug);
        }

        var serverCert = o.Pki.WithKey(o.CertName);
        var intermediate = o.Pki.Intermediate;
        var clientPolicy = o.Pki.TrustPolicy(Pki.ClientAuthOid, o.CheckClientEku);

        builder.WebHost.ConfigureKestrel(kestrel =>
        {
            kestrel.Listen(IPAddress.Loopback, o.Port, listen => listen.UseHttps(https =>
            {
                https.ServerCertificate = serverCert;
                if (o.SendIntermediate)
                    https.ServerCertificateChain = new X509Certificate2Collection(intermediate);

                // mTLS: bez certyfikatu klienta handshake sie nie konczy.
                https.ClientCertificateMode = ClientCertificateMode.RequireCertificate;

                // Walidacja klienta wg NASZEJ polityki (custom root + EKU), nie systemowej.
                https.OnAuthenticate = (_, ssl) => ssl.CertificateChainPolicy = clientPolicy;

                https.ClientCertificateValidation = (cert, chain, errors) =>
                {
                    log($"[serwer] certyfikat klienta: {cert.Subject} | SslPolicyErrors={errors} | chain: {Pki.Describe(chain)}");
                    return errors == SslPolicyErrors.None;
                };
            }));
        });

        var app = builder.Build();
        app.MapGet("/", (HttpContext ctx) =>
        {
            var c = ctx.Connection.ClientCertificate;
            return $"Czesc, {c?.Subject} (wystawca: {c?.Issuer})";
        });

        await app.StartAsync();
        return app;
    }
}
