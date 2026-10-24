using System;
using System.Security.Cryptography;
using System.Text;

Console.WriteLine("--- Wsparcie platformy dla kryptografii postkwantowej (.NET 10) ---");
Console.WriteLine($"MLDsa.IsSupported = {MLDsa.IsSupported}");
Console.WriteLine($"MLKem.IsSupported = {MLKem.IsSupported}");

RunMLDsaDemo();
RunMLKemDemo();

static void RunMLDsaDemo()
{
    Console.WriteLine();
    Console.WriteLine("--- ML-DSA (FIPS 204) - podpis cyfrowy odporny na atak kwantowy ---");
    if (MLDsa.IsSupported)
    {
        using MLDsa key = MLDsa.GenerateKey(MLDsaAlgorithm.MLDsa65);
        byte[] data = Encoding.UTF8.GetBytes("Faktura #2026/09/28, kwota 1234.56 PLN");
        byte[] signature = key.SignData(data, context: Array.Empty<byte>());
        bool ok = key.VerifyData(data, signature, context: Array.Empty<byte>());
        Console.WriteLine($"Podpisano {data.Length} B danych, podpis {signature.Length} B, weryfikacja OK = {ok}");

        data[0] ^= 0xFF; // symulacja podmiany danych po podpisaniu
        bool tampered = key.VerifyData(data, signature, context: Array.Empty<byte>());
        Console.WriteLine($"Po zmodyfikowaniu 1 bajtu danych: weryfikacja OK = {tampered}");
    }
    else
    {
        try
        {
            using MLDsa key = MLDsa.GenerateKey(MLDsaAlgorithm.MLDsa65);
            Console.WriteLine("Klucz wygenerowany (nieoczekiwane na tej maszynie)");
        }
        catch (PlatformNotSupportedException ex)
        {
            Console.WriteLine("MLDsa.GenerateKey rzucil: " + ex.GetType().FullName);
            Console.WriteLine("Komunikat: " + ex.Message);
        }
    }
}

static void RunMLKemDemo()
{
    Console.WriteLine();
    Console.WriteLine("--- ML-KEM (FIPS 203) - uzgadnianie kluczy odporne na atak kwantowy ---");
    if (MLKem.IsSupported)
    {
        using MLKem kem = MLKem.GenerateKey(MLKemAlgorithm.MLKem768);
        kem.Encapsulate(out byte[] ciphertext, out byte[] sharedSecretSender);
        byte[] sharedSecretReceiver = kem.Decapsulate(ciphertext);
        bool match = sharedSecretSender.AsSpan().SequenceEqual(sharedSecretReceiver);
        Console.WriteLine($"Ciphertext {ciphertext.Length} B, wspolny sekret {sharedSecretSender.Length} B, zgodny = {match}");
    }
    else
    {
        try
        {
            using MLKem kem = MLKem.GenerateKey(MLKemAlgorithm.MLKem768);
            Console.WriteLine("Klucz wygenerowany (nieoczekiwane na tej maszynie)");
        }
        catch (PlatformNotSupportedException ex)
        {
            Console.WriteLine("MLKem.GenerateKey rzucil: " + ex.GetType().FullName);
            Console.WriteLine("Komunikat: " + ex.Message);
        }
    }
}
