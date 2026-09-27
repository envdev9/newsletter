// C# 14: "simple lambda parameters with modifiers".
// Modyfikatory ref/out/in/scoped/ref readonly na parametrach lambdy BEZ podawania typow.

// Delegaty z out/ref/in - tu musimy je zdefiniowac sami.
delegate bool TryParser<T>(string text, out T result);
delegate void Doubler(ref int value);
delegate int Summer(in Big big);

readonly record struct Big(long A, long B, long C, long D);

static class Demo
{
    public static void Main()
    {
        Console.WriteLine("--- 1. out bez typow (C# 14) ---");
        // Przed C# 14: TryParser<int> p = (string text, out int result) => int.TryParse(text, out result);
        TryParser<int> parse = (text, out result) => int.TryParse(text, out result);
        foreach (var s in new[] { "42", "abc" })
            Console.WriteLine($"{s,-4} -> ok={parse(s, out var n)}, n={n}");

        Console.WriteLine("--- 2. ref bez typow ---");
        Doubler dbl = (ref v) => v *= 2;
        int x = 21;
        dbl(ref x);
        Console.WriteLine($"x po Doubler = {x}");

        Console.WriteLine("--- 3. in bez typow ---");
        Summer sum = (in b) => (int)(b.A + b.B + b.C + b.D);
        var big = new Big(1, 2, 3, 4);
        Console.WriteLine($"suma = {sum(in big)}");

        Console.WriteLine("--- 4. scoped bez typow ---");
        // scoped dla parametru typu ref struct (Span) - tez bez typu
        SpanCounter count = (scoped span) => span.Length;
        Console.WriteLine($"dlugosc = {count(stackalloc int[5])}");

        // Ograniczenie: (params xs) => ... NIE kompiluje sie (CS9272) - patrz ../compat-check.
    }
}

delegate int SpanCounter(scoped Span<int> span);
