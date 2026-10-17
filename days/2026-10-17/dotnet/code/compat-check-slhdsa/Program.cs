using System.Security.Cryptography;

Console.WriteLine(SlhDsa.IsSupported);
using var key = SlhDsa.GenerateKey(SlhDsaAlgorithm.SlhDsaSha2_128s);
