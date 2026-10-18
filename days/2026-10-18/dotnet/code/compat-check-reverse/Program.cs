int[] d = [10, 20, 30];

// C# 13: LINQ (IEnumerable<int>). C# 14 + net9.0: MemoryExtensions.Reverse(Span<int>) zwraca void.
foreach (var x in d.Reverse())
    Console.Write(x + " ");

Console.WriteLine();
