using System;
using System.Collections.Generic;
using System.Text.Json.Nodes;

// Ten projekt celuje w net9.0 (patrz compat-check.csproj) i sluzy WYLACZNIE do pokazania,
// ze dwie funkcje opisane w artykule NIE istnieja w .NET 9 - realny blad kompilatora, nie zalozenie.
//
// Domyslnie aktywny jest DOWOD 1 (MemoryExtensions.SequenceCompareTo z IComparer<T>).
// Zeby zobaczyc DOWOD 2 (JsonArray.RemoveAll/RemoveRange), zakomentuj blok "DOWOD 1"
// i odkomentuj blok "DOWOD 2" (patrz code/README.md).

// ---- DOWOD 1: MemoryExtensions.SequenceCompareTo<T>(ReadOnlySpan<T>, ReadOnlySpan<T>, IComparer<T>) ----
ReadOnlySpan<byte> a = "Header"u8;
ReadOnlySpan<byte> b = "header"u8;
int wynik = a.SequenceCompareTo(b, Comparer<byte>.Default); // CS1501 na net9.0: ten overload nie istnieje
Console.WriteLine(wynik);

// ---- DOWOD 2: JsonArray.RemoveAll / RemoveRange ----
// var arr = new JsonArray(1, 2, 3, 4, 5);
// int removed = arr.RemoveAll(x => x!.GetValue<int>() % 2 == 0); // CS1061 na net9.0
// arr.RemoveRange(0, 1); // CS1061 na net9.0
// Console.WriteLine(removed);
