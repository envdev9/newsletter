// Ten projekt celuje w net9.0 (celowo!) - ma pokazac, ze dwie funkcje opisane w
// dzisiejszym artykule NIE istnieja w .NET 9, czyli sa realna nowoscia .NET 10.
// Domyslnie aktywny jest Dowod 1. Zeby zobaczyc Dowod 2, zakomentuj blok "Dowod 1"
// i odkomentuj blok "Dowod 2" (patrz code/README.md).

// ===== Dowod 1: Enumerable.Sequence nie istnieje w .NET 9 =====
// Oczekiwany blad: CS0117: 'Enumerable' does not contain a definition for 'Sequence'
foreach (var i in Enumerable.Sequence(1, 10, 2))
    Console.Write(i + " ");

// ===== Dowod 2: MemoryExtensions.IndexOf z IEqualityComparer<char> nie istnieje w .NET 9 =====
// Oczekiwany blad: CS1503 - kompilator probuje dopasowac 3. argument do starego
// przeciazenia IndexOf(ReadOnlySpan<char>, ReadOnlySpan<char>, StringComparison)
// i nie potrafi przekonwertowac komparatora na StringComparison.
//
// using System.Collections.Generic;
//
// ReadOnlySpan<char> tekst = "Hello World";
// ReadOnlySpan<char> szukane = "world";
// int idx = tekst.IndexOf(szukane, OrdinalIgnoreCaseCharComparer.Instance);
// Console.WriteLine(idx);
//
// class OrdinalIgnoreCaseCharComparer : IEqualityComparer<char>
// {
//     public static readonly OrdinalIgnoreCaseCharComparer Instance = new();
//     public bool Equals(char x, char y) => char.ToUpperInvariant(x) == char.ToUpperInvariant(y);
//     public int GetHashCode(char obj) => char.ToUpperInvariant(obj).GetHashCode();
// }
