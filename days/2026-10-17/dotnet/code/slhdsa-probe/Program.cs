using System.Reflection;
using System.Security.Cryptography;

// 1. Powierzchnia API (refleksja - dziala nawet gdy platforma nie wspiera algorytmu)
Console.WriteLine("--- 1. Publiczne API SlhDsa (refleksja) ---");
foreach (var m in typeof(SlhDsa).GetMethods(BindingFlags.Public | BindingFlags.Static | BindingFlags.Instance | BindingFlags.DeclaredOnly)
             .Where(m => !m.IsSpecialName)
             .Select(m => $"{(m.IsStatic ? "static " : "")}{m.Name}({string.Join(", ", m.GetParameters().Select(p => p.ParameterType.Name))})")
             .Distinct().OrderBy(s => s))
    Console.WriteLine(m);

Console.WriteLine("--- 2. Warianty parametrow (SlhDsaAlgorithm) ---");
foreach (var p in typeof(SlhDsaAlgorithm).GetProperties(BindingFlags.Public | BindingFlags.Static))
{
    var a = (SlhDsaAlgorithm)p.GetValue(null)!;
    Console.WriteLine($"{p.Name,-18} {a.Name,-22} podpis={a.SignatureSizeInBytes,6} B  klucz publ.={a.PublicKeySizeInBytes} B  klucz pryw.={a.PrivateKeySizeInBytes} B");
}

// 2. Czy ta maszyna w ogole wspiera algorytm?
Console.WriteLine("--- 3. Wsparcie platformy ---");
Console.WriteLine($"SlhDsa.IsSupported = {SlhDsa.IsSupported}");
Console.WriteLine($"MLDsa.IsSupported  = {MLDsa.IsSupported}");
Console.WriteLine($"MLKem.IsSupported  = {MLKem.IsSupported}");

// 3. Prob realnego uzycia - albo dziala, albo raportujemy wyjatek
Console.WriteLine("--- 4. Proba GenerateKey ---");
if (SlhDsa.IsSupported)
{
    using var key = SlhDsa.GenerateKey(SlhDsaAlgorithm.SlhDsaSha2_128s);
    byte[] data = "prasowka"u8.ToArray();
    byte[] sig = key.SignData(data);
    Console.WriteLine($"podpis {sig.Length} B, VerifyData={key.VerifyData(data, sig)}");
    data[0] ^= 1;
    Console.WriteLine($"po zmianie 1 bitu: VerifyData={key.VerifyData(data, sig)}");
}
else
{
    try
    {
        using var key = SlhDsa.GenerateKey(SlhDsaAlgorithm.SlhDsaSha2_128s);
        Console.WriteLine("niespodziewanie dziala");
    }
    catch (Exception e)
    {
        Console.WriteLine($"RZUCILO {e.GetType().Name}: {e.Message}");
    }
}
