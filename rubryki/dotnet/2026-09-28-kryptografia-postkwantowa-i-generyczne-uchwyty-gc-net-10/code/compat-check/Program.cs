// Ten projekt CELOWO się nie kompiluje na net9.0 - to dowod "przed i po" dla artykulu.
// Domyslnie aktywny jest Dowod 1 (GCHandle<T>). Zeby zobaczyc Dowod 2 (MLDsa),
// zakomentuj blok "Dowod 1" i odkomentuj blok "Dowod 2", potem `dotnet build`.

using System;
using System.Runtime.InteropServices;
// using System.Security.Cryptography;

// --- Dowod 1: GCHandle<T> (generyczny) nie istnieje w .NET 9 ---
// Rzeczywisty błąd (zweryfikowany `dotnet build`, SDK 9.0.316):
// CS0308: The non-generic type 'GCHandle' cannot be used with type arguments
GCHandle<string> typedHandle = new("nowosc .NET 10");
Console.WriteLine(typedHandle.Target);

// --- Dowod 2: MLDsa (kryptografia postkwantowa) nie istnieje w .NET 9 ---
// Rzeczywisty błąd (zweryfikowany `dotnet build`, SDK 9.0.316):
// CS0103: The name 'MLDsa' does not exist in the current context
// Console.WriteLine(MLDsa.IsSupported);
