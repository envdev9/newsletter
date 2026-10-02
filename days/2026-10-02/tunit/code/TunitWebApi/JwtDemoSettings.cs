using System.Text;
using Microsoft.IdentityModel.Tokens;

namespace TunitWebApi;

/// <summary>
/// Ustawienia JWT dla TEGO wydania prasówki -- wylacznie demonstracyjne.
///
/// !!! UWAGA !!! Klucz ponizej jest JAWNY w publicznym repo i celowo trywialny do
/// odczytania. To NIGDY nie jest sposob na przechowywanie sekretu produkcyjnego --
/// prawdziwy klucz podpisujacy JWT nalezy trzymac w menedzerze sekretow (Key Vault,
/// user-secrets, zmienna srodowiskowa wstrzykiwana przez orkiestrator), nigdy w kodzie
/// ani w repo. Ten klucz istnieje tylko po to, zeby kod z tego wydania dalo sie odpalic
/// `dotnet test` bez zadnej zewnetrznej konfiguracji.
/// </summary>
public static class JwtDemoSettings
{
    private const string DemoSigningKeyText =
        "DEMO-ONLY-tunit-prasowka-2026-10-02-nigdy-nie-uzywac-w-produkcji-min-32-bajty!!";

    public const string Issuer = "https://prasowka.local/tunit-demo";
    public const string Audience = "tunit-demo-api";

    public static SymmetricSecurityKey SigningKey { get; } =
        new(Encoding.UTF8.GetBytes(DemoSigningKeyText));
}
