using System.Security.Cryptography;
using System.Text;

var builder = WebApplication.CreateBuilder(args);
var app = builder.Build();

app.MapGet("/health", () => "Healthy");

// Zwraca to, co Aspire wstrzyknął jako zmienne środowiskowe.
// Sekretów NIGDY nie oddajemy wprost - tylko długość i skrót (do porównania w teście).
app.MapGet("/env", (IConfiguration cfg) =>
{
    static string? Mask(string? s) =>
        s is null ? null : $"len={s.Length};sha256={Convert.ToHexString(SHA256.HashData(Encoding.UTF8.GetBytes(s)))[..8]}";

    var conn = cfg["DB_CONNECTION"];
    return new
    {
        appMode = cfg["APP_MODE"],
        greeting = cfg["GREETING"],
        fixedText = cfg["FIXED_TEXT"],
        runMode = cfg["RUN_MODE"],
        apiKey = Mask(cfg["API_KEY"]),
        // connection string bez hasła: tnie od "Password="
        dbConnectionPrefix = conn?[..conn.IndexOf("Password=", StringComparison.Ordinal)],
        dbConnectionHasPassword = conn is not null && conn.Length > conn.IndexOf("Password=", StringComparison.Ordinal) + 9,
    };
});

app.Run();
