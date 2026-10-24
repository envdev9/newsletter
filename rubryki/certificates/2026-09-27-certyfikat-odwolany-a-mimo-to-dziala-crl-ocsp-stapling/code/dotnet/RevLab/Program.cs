// RevLab - wydanie #4: odwolania (CRL/CDP, OCSP), X509Store, rotacja, pinning SPKI.
// Uzycie:
//   dotnet run --project dotnet/RevLab -- revocation [pki-dir] [crl-file]
//   dotnet run --project dotnet/RevLab -- pinning    [pki-dir]
// pki-dir domyslnie: ./work (wygenerowane przez openssl/setup-pki.sh)

var mode = args.Length > 0 ? args[0] : "revocation";
var pkiDir = Path.GetFullPath(args.Length > 1 ? args[1] : "work");

// BEZPIECZENSTWO: przekierowujemy HOME do katalogu roboczego, zeby .NET trzymal cache CRL
// (~/.dotnet/corefx/crls) i magazyn CurrentUser (~/.dotnet/corefx/cryptography/x509stores) TUTAJ,
// a nie w prawdziwym profilu uzytkownika. Musi nastapic przed pierwszym uzyciem X509.
var fakeHome = Path.Combine(pkiDir, "home");
Directory.CreateDirectory(fakeHome);
Environment.SetEnvironmentVariable("HOME", fakeHome);
Console.WriteLine($"HOME (na potrzeby tego procesu) = {fakeHome}\n");

var pki = new Pki(pkiDir);
switch (mode)
{
    case "revocation":
        RevocationLab.Run(pki, args.Length > 2 ? Path.GetFullPath(args[2]) : Path.Combine(pkiDir, "inter.crl"));
        break;
    case "pinning":
        await PinningLab.Run(pki);
        break;
    default:
        Console.WriteLine("tryby: revocation | pinning");
        break;
}
