// MemoryExtensions: IndexOf/Contains/StartsWith/EndsWith/Count z IEqualityComparer<T>
// Nowe w .NET 10 (System.MemoryExtensions, System.Private.CoreLib).
// Potwierdzone empirycznie jako nowosc: patrz code/compat-check (CS1503 na net9.0 -
// kompilator probuje dopasowac trzeci argument do starego parametru StringComparison).

using System.Text;

Console.WriteLine("--- 1. Problem: domyslne IndexOf na Span<char> to ORDINAL, bez uwzgledniania wielkosci liter ---");
ReadOnlySpan<char> tekst = "Hello World, wonderful World";
ReadOnlySpan<char> szukane = "world";
Console.WriteLine($"tekst: \"{tekst}\"");
Console.WriteLine($"tekst.IndexOf(\"world\") [domyslnie, ordinal]: {tekst.IndexOf(szukane)}");
Console.WriteLine("-> -1: dokladne dopasowanie wielkosci liter nie znalazlo 'world' (jest 'World').");
Console.WriteLine("Dotychczas: trzeba bylo tekst.ToString().IndexOf(szukane, StringComparison.OrdinalIgnoreCase)");
Console.WriteLine("- czyli skopiowac caly span do stringa tylko po to, zeby poszukac podciagu.");

Console.WriteLine();
Console.WriteLine("--- 2. .NET 10: IndexOf/Contains/StartsWith z IEqualityComparer<T> - bez kopiowania do string ---");
int idxCi = tekst.IndexOf(szukane, OrdinalIgnoreCaseCharComparer.Instance);
Console.WriteLine($"tekst.IndexOf(\"world\", OrdinalIgnoreCaseCharComparer): {idxCi}");

bool containsCi = tekst.Contains('w', OrdinalIgnoreCaseCharComparer.Instance);
Console.WriteLine($"tekst.Contains('w', ci): {containsCi}");

bool startsCi = tekst.StartsWith("HELLO", OrdinalIgnoreCaseCharComparer.Instance);
Console.WriteLine($"tekst.StartsWith(\"HELLO\", ci): {startsCi}");

bool endsCi = tekst.EndsWith("WORLD", OrdinalIgnoreCaseCharComparer.Instance);
Console.WriteLine($"tekst.EndsWith(\"WORLD\", ci): {endsCi}");

int countCi = tekst.Count('o', OrdinalIgnoreCaseCharComparer.Instance);
Console.WriteLine($"tekst.Count('o', ci) (liczy 'o' i 'O'): {countCi}");

Console.WriteLine();
Console.WriteLine("--- 3. Kluczowa roznica vs StringComparison: dziala na DOWOLNYM T, nie tylko char/string ---");
Console.WriteLine("Realny przypadek: naglowek HTTP przychodzi jako surowe bajty z socketu (ReadOnlySpan<byte>),");
Console.WriteLine("nazwy naglowkow sa case-insensitive wg RFC, ale konwersja calego bufora na string na kazdy");
Console.WriteLine("naglowek to niepotrzebna alokacja w kodzie na sciezce krytycznej (np. middleware Kestrela).");

ReadOnlySpan<byte> surowyNaglowek = "Content-Type: application/json; charset=utf-8"u8;
ReadOnlySpan<byte> nazwaSzukana = "content-type"u8;

int idxBajtowyDefault = surowyNaglowek.IndexOf(nazwaSzukana); // ordinal, bez komparatora
int idxBajtowyCi = surowyNaglowek.IndexOf(nazwaSzukana, AsciiCaseInsensitiveByteComparer.Instance);

Console.WriteLine($"surowyNaglowek (bajty): \"{Encoding.ASCII.GetString(surowyNaglowek)}\"");
Console.WriteLine($"IndexOf(\"content-type\"u8) [domyslnie, ordinal]: {idxBajtowyDefault}");
Console.WriteLine($"IndexOf(\"content-type\"u8, AsciiCaseInsensitiveByteComparer): {idxBajtowyCi}");
Console.WriteLine("-> znalezione na poziomie bajtow, bez konwersji calego bufora na string.");

// Uwaga: Contains(ReadOnlySpan<T>, ReadOnlySpan<T>, IEqualityComparer<T>) NIE istnieje -
// nowy przeciazony Contains z komparatorem dziala tylko dla POJEDYNCZEGO elementu T.
// Do sprawdzenia "czy podciag wystepuje" uzywamy IndexOf (zwraca -1, jesli brak):
bool zawieraJson = surowyNaglowek.IndexOf("APPLICATION/JSON"u8, AsciiCaseInsensitiveByteComparer.Instance) >= 0;
Console.WriteLine($"IndexOf(\"APPLICATION/JSON\"u8, ci) >= 0: {zawieraJson}");

Console.WriteLine();
Console.WriteLine("--- 4. Przypadek 'nie tylko case-insensitivity': wlasna logika rownosci ---");
Console.WriteLine("Komparator traktujacy KAZDA cyfre jako rowna kazdej innej cyfrze - szukanie wzorca");
Console.WriteLine("'pole_N' niezaleznie od konkretnej cyfry N, bez wyrazen regularnych:");
ReadOnlySpan<char> identyfikatory = "pole_1, pole_7, inne_x, pole_9";
ReadOnlySpan<char> wzorzec = "pole_0"; // '0' jako reprezentant "dowolnej cyfry"
int idxWzorca = identyfikatory.IndexOf(wzorzec, AnyDigitEqualsAnyDigitComparer.Instance);
Console.WriteLine($"identyfikatory.IndexOf(\"pole_0\", AnyDigitEqualsAnyDigitComparer): {idxWzorca}");
Console.WriteLine("-> znalazlo pierwsze wystapienie 'pole_<cyfra>' (tu: 'pole_1' na indeksie " + idxWzorca + "),");
Console.WriteLine("   mimo ze szukany wzorzec mial literalnie '0'. To pokazuje, ze te API to NIE jest");
Console.WriteLine("   'StringComparison z dodatkowym rozszerzeniem' - to dowolna logika rownosci elementow.");

class OrdinalIgnoreCaseCharComparer : IEqualityComparer<char>
{
    public static readonly OrdinalIgnoreCaseCharComparer Instance = new();
    public bool Equals(char x, char y) => char.ToUpperInvariant(x) == char.ToUpperInvariant(y);
    public int GetHashCode(char obj) => char.ToUpperInvariant(obj).GetHashCode();
}

class AsciiCaseInsensitiveByteComparer : IEqualityComparer<byte>
{
    public static readonly AsciiCaseInsensitiveByteComparer Instance = new();
    public bool Equals(byte x, byte y) => ToLowerAscii(x) == ToLowerAscii(y);
    public int GetHashCode(byte obj) => ToLowerAscii(obj);
    private static byte ToLowerAscii(byte b) => (b >= (byte)'A' && b <= (byte)'Z') ? (byte)(b + 32) : b;
}

class AnyDigitEqualsAnyDigitComparer : IEqualityComparer<char>
{
    public static readonly AnyDigitEqualsAnyDigitComparer Instance = new();
    public bool Equals(char x, char y) => (char.IsDigit(x) && char.IsDigit(y)) || x == y;
    public int GetHashCode(char obj) => char.IsDigit(obj) ? 0 : obj.GetHashCode();
}
