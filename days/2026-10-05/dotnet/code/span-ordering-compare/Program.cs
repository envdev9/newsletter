using System;
using System.Collections.Generic;

Console.WriteLine("--- 1. Problem: stary SequenceCompareTo ma TYLKO porzadek domyslny (ordinal dla byte) ---");
ReadOnlySpan<byte> naglowekA = "Header"u8;
ReadOnlySpan<byte> naglowekB = "header"u8;
int ordinal = naglowekA.SequenceCompareTo(naglowekB); // istnieje od .NET 6, wymaga T : IComparable<T>
Console.WriteLine($"\"Header\".SequenceCompareTo(\"header\") [domyslnie, ordinal]: {ordinal}");
Console.WriteLine("-> wartosc != 0, bo 'H' (72) i 'h' (104) to dla bajtow/ordinal dwie rozne wartosci.");
Console.WriteLine("Dotychczas: zeby posortowac/porownac case-insensitive, trzeba bylo skopiowac do string.");
Console.WriteLine();

Console.WriteLine("--- 2. .NET 10: SequenceCompareTo<T> z IComparer<T> - wlasny porzadek, bez kopiowania ---");
int caseInsensitive = naglowekA.SequenceCompareTo(naglowekB, AsciiCaseInsensitiveByteOrderComparer.Instance);
Console.WriteLine($"\"Header\".SequenceCompareTo(\"header\", ci): {caseInsensitive}");
Console.WriteLine("-> 0: wedlug wlasnego porzadku (ignorujac wielkosc liter) te dwa ciagi sa ROWNE.");
Console.WriteLine();

Console.WriteLine("--- 3. Praktyczny przyklad: sortowanie nazw naglowkow HTTP (surowe bajty) alfabetycznie, case-insensitive ---");
byte[][] headers =
{
    "content-type"u8.ToArray(),
    "Accept"u8.ToArray(),
    "AUTHORIZATION"u8.ToArray(),
    "accept-encoding"u8.ToArray(),
};
Console.WriteLine("Przed sortowaniem: " + string.Join(", ", AsStrings(headers)));
Array.Sort(headers, new ByteArrayCaseInsensitiveComparer());
Console.WriteLine("Po Array.Sort z komparatorem opartym na SequenceCompareTo: " + string.Join(", ", AsStrings(headers)));
Console.WriteLine("-> alfabetycznie, ignorujac wielkosc liter, bez ani jednej konwersji na string do porownania.");
Console.WriteLine();

Console.WriteLine("--- 4. HACZYK A: rozna dlugosc -> regula prefiksu, jak w string.CompareOrdinal ---");
ReadOnlySpan<byte> krotszy = "Head"u8;
ReadOnlySpan<byte> dluzszy = "Header"u8;
int prefiks = krotszy.SequenceCompareTo(dluzszy);
Console.WriteLine($"\"Head\".SequenceCompareTo(\"Header\"): {prefiks}");
Console.WriteLine("-> wartosc ujemna: krotszy ciag, bedacy prefiksem dluzszego, jest 'mniejszy' (tak jak w string).");
Console.WriteLine();

Console.WriteLine("--- 5. HACZYK B: wynik to NIE zawsze -1/0/1, liczy sie tylko ZNAK (umowa jak w IComparable) ---");
Console.WriteLine($"Zmierzona realnie wartosc z sekcji 1 to {ordinal}, nie -1. To zgodne z kontraktem IComparer<T>/");
Console.WriteLine("IComparable<T> - liczy sie TYLKO znak (< 0, == 0, > 0), nigdy konkretna wartosc liczbowa.");

static IEnumerable<string> AsStrings(byte[][] arr)
{
    foreach (var b in arr) yield return System.Text.Encoding.ASCII.GetString(b);
}

class ByteArrayCaseInsensitiveComparer : IComparer<byte[]>
{
    public int Compare(byte[]? x, byte[]? y) =>
        ((ReadOnlySpan<byte>)x!).SequenceCompareTo(y!, AsciiCaseInsensitiveByteOrderComparer.Instance);
}

class AsciiCaseInsensitiveByteOrderComparer : IComparer<byte>
{
    public static readonly AsciiCaseInsensitiveByteOrderComparer Instance = new();
    public int Compare(byte x, byte y) => Upper(x).CompareTo(Upper(y));
    static byte Upper(byte b) => (b >= (byte)'a' && b <= (byte)'z') ? (byte)(b - 32) : b;
}
