using System.Net.Security;

namespace MtlsDemo;

public static class MtlsClient
{
    /// <summary>
    /// Jedno zapytanie GET https://host:port/ z (opcjonalnym) certyfikatem klienta.
    /// Zwraca odpowiedz albo splaszczona liste wyjatkow (Typ: komunikat).
    /// </summary>
    public static async Task<string> CallAsync(Pki pki, int port, string? clientCertName, Action<string> log, string host = "localhost")
    {
        var handler = new SocketsHttpHandler();
        handler.SslOptions.CertificateChainPolicy = pki.TrustPolicy(Pki.ServerAuthOid);
        handler.SslOptions.RemoteCertificateValidationCallback = (_, cert, chain, errors) =>
        {
            log($"[klient] certyfikat serwera: {cert?.Subject} | SslPolicyErrors={errors} | chain: {Pki.Describe(chain)}");
            return errors == SslPolicyErrors.None;
        };
        if (clientCertName is not null)
            handler.SslOptions.ClientCertificateContext = pki.ClientContext(clientCertName);

        using var http = new HttpClient(handler) { Timeout = TimeSpan.FromSeconds(10) };
        try
        {
            using var resp = await http.GetAsync($"https://{host}:{port}/");
            return $"HTTP {(int)resp.StatusCode}: {await resp.Content.ReadAsStringAsync()}";
        }
        catch (Exception ex)
        {
            var lines = new List<string>();
            for (var e = ex; e is not null; e = e.InnerException!)
            {
                lines.Add($"{e.GetType().Name}: {e.Message}");
                if (e.InnerException is null) break;
            }
            return "BLAD -> " + string.Join("\n      -> ", lines);
        }
    }
}
