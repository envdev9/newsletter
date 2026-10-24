delegate int SumAll(params int[] xs);

static class Demo
{
    static void Main()
    {
        // Sprawdzamy, czy 'params' bez typu jest dozwolone w C# 14 (oczekiwany blad).
        SumAll f = (params xs) => xs.Length;
        Console.WriteLine(f(1, 2, 3));
    }
}
