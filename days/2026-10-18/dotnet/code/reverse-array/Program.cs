// Ten sam zapis `tablica.Reverse()` znaczy co innego zaleznie od (LangVersion, TFM):
//   C# 13 / dowolny TFM  -> Enumerable.Reverse(IEnumerable<T>)  (LINQ, leniwe, NIE zmienia tablicy)
//   C# 14 + net9.0       -> MemoryExtensions.Reverse(Span<T>)    (first-class Span, odwraca W MIEJSCU, zwraca void)
//   C# 14 + net10.0      -> Enumerable.Reverse(TSource[])        (nowe przeciazenie, znowu LINQ)
using System.Reflection;

Console.WriteLine($"Runtime: {System.Runtime.InteropServices.RuntimeInformation.FrameworkDescription}, " +
                  $"TFM-define: {Tfm()}");

Console.WriteLine("--- 1. Instrukcja `a.Reverse();` (wynik wyrzucony) ---");
int[] a = [1, 2, 3, 4, 5];
a.Reverse();
Console.WriteLine($"po a.Reverse(): [{string.Join(", ", a)}]  -> {(a[0] == 5 ? "ODWROCONA w miejscu (Span)" : "bez zmian (LINQ, wynik wyrzucony)")}");

Console.WriteLine("--- 2. Jawne wywolania - zawsze jednoznaczne ---");
int[] b = [1, 2, 3, 4, 5];
var lazy = Enumerable.Reverse(b);
Console.WriteLine($"Enumerable.Reverse(b): [{string.Join(", ", lazy)}], b nadal [{string.Join(", ", b)}]");
b.AsSpan().Reverse();
Console.WriteLine($"b.AsSpan().Reverse(): b = [{string.Join(", ", b)}]");
Array.Reverse(b);
Console.WriteLine($"Array.Reverse(b):     b = [{string.Join(", ", b)}]");

Console.WriteLine("--- 3. Ta sama tablica, inny typ statyczny ---");
int[] c = [1, 2, 3];
IEnumerable<int> asEnumerable = c;
c.Reverse(); // patrz sekcja 1
Console.WriteLine($"c po c.Reverse(): [{string.Join(", ", c)}]");
foreach (var _ in asEnumerable.Reverse()) { } // IEnumerable<int> -> zawsze LINQ
Console.WriteLine($"c po IEnumerable<int>.Reverse(): [{string.Join(", ", c)}] (rzutowanie na IEnumerable<T> zawsze daje LINQ)");

Console.WriteLine("--- 4. Uzycie wyniku: `foreach (var x in a.Reverse())` ---");
#if NET10_0_OR_GREATER
int[] d = [10, 20, 30];
foreach (var x in d.Reverse()) Console.Write(x + " ");
Console.WriteLine("  <- kompiluje sie tylko na net10.0 (na net9.0 + C# 14: CS1579)");
#else
Console.WriteLine("(pominiete na net9.0: `d.Reverse()` zwraca void -> foreach nie skompiluje sie)");
#endif

Console.WriteLine("--- 5. Refleksja: ktora metoda przeslania `Reverse` dla tablicy? ---");
Console.WriteLine("Enumerable.Reverse(TSource[]) istnieje: " +
                  (typeof(Enumerable).GetMethods(BindingFlags.Public | BindingFlags.Static)
                      .Any(m => m.Name == "Reverse" && m.GetParameters()[0].ParameterType.IsArray)));

static string Tfm() =>
#if NET10_0_OR_GREATER
    "NET10_0_OR_GREATER";
#else
    "NET9_0";
#endif
