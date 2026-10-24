// C# 14: "first-class Span" - niejawne konwersje T[] -> Span<T> / ReadOnlySpan<T>,
// Span<T> -> ReadOnlySpan<T>, string -> ReadOnlySpan<char>, takze dla odbiornika
// metody rozszerzajacej i w inferencji typow generycznych.

static class SpanExt
{
    // Metoda rozszerzajaca na ReadOnlySpan<char>
    public static bool IsPalindrome(this ReadOnlySpan<char> s)
    {
        for (int i = 0, j = s.Length - 1; i < j; i++, j--)
            if (s[i] != s[j]) return false;
        return true;
    }

    // Generyczna metoda na ReadOnlySpan<T>
    public static int CountEqual<T>(this ReadOnlySpan<T> s, T value) where T : IEquatable<T>
    {
        int c = 0;
        foreach (var x in s) if (x.Equals(value)) c++;
        return c;
    }
}

static class Demo
{
    static int Sum(ReadOnlySpan<int> data)
    {
        int s = 0;
        foreach (var x in data) s += x;
        return s;
    }

    static void Main()
    {
        Console.WriteLine("--- 1. Metoda rozszerzajaca na ReadOnlySpan<char> wolana na string ---");
        // Przed C# 14: "kajak".AsSpan().IsPalindrome() - odbiornik extension methody nie dopuszczal konwersji.
        string word = "kajak";
        Console.WriteLine($"{word} -> {word.IsPalindrome()}");
        Console.WriteLine($"tablica znakow -> {new[] { 'a', 'b', 'a' }.IsPalindrome()}");

        Console.WriteLine("--- 2. Generyk + inferencja T z tablicy ---");
        int[] numbers = [1, 2, 2, 3, 2];
        Console.WriteLine($"ile dwojek: {numbers.CountEqual(2)}");

        Console.WriteLine("--- 3. Span<T> -> ReadOnlySpan<T> i tablica -> ReadOnlySpan<T> w argumencie ---");
        Span<int> span = numbers;
        Console.WriteLine($"Sum(tablica) = {Sum(numbers)}, Sum(span) = {Sum(span)}");

        Console.WriteLine("--- 4. Sprawdzenie znanej pulapki: tablica.Reverse() ---");
        int[] arr = [1, 2, 3];
        // Obawa: czy C# 14 przypnie to do MemoryExtensions.Reverse(Span<T>) (void, w miejscu)?
        var r = arr.Reverse();
        Console.WriteLine($"typ wyniku Reverse(): {r.GetType().Name}");
        Console.WriteLine($"arr po Reverse(): [{string.Join(", ", arr)}]");
    }
}
