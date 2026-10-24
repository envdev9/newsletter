// Enumerable.Sequence / Enumerable.InfiniteSequence - nowe w .NET 10 (System.Linq).
// Potwierdzone empirycznie jako nowosc: patrz code/compat-check (CS0117 na net9.0).

Console.WriteLine("--- 1. Stary idiom: Enumerable.Range tylko dla int, krok zawsze 1 ---");
// Range nie umie kroku ani typow innych niz int - trzeba kombinowac z Select:
IEnumerable<int> rangeHack = Enumerable.Range(0, 5).Select(i => i * 2);
Console.WriteLine("Range(0,5).Select(i => i*2): " + string.Join(",", rangeHack));
Console.WriteLine("Dziala, ale: nazwa 'Range' sugeruje liczbe elementow, nie koniec zakresu;");
Console.WriteLine("zejscie w dol (malejaco) albo typ 'double' wymaga wlasnej petli/generatora.");

Console.WriteLine();
Console.WriteLine("--- 2. Enumerable.Sequence<T>(start, endInclusive, step) ---");
IEnumerable<int> rosnaco = Enumerable.Sequence(1, 10, 2);
Console.WriteLine("Sequence(1, 10, 2): " + string.Join(",", rosnaco));

IEnumerable<int> malejaco = Enumerable.Sequence(10, 1, -3);
Console.WriteLine("Sequence(10, 1, -3): " + string.Join(",", malejaco));

// Generyczna matematyka (INumber<T>) - dziala tez na double, nie tylko int:
IEnumerable<double> ulamkowy = Enumerable.Sequence(1.5, 3.5, 0.5);
Console.WriteLine("Sequence(1.5, 3.5, 0.5): " + string.Join(",", ulamkowy));

Console.WriteLine();
Console.WriteLine("--- 3. Enumerable.InfiniteSequence<T>(start, step) + Take/TakeWhile ---");
IEnumerable<int> nieskonczona = Enumerable.InfiniteSequence(0, 5).Take(5);
Console.WriteLine("InfiniteSequence(0, 5).Take(5): " + string.Join(",", nieskonczona));

IEnumerable<int> doProgu = Enumerable.InfiniteSequence(1, 3).TakeWhile(x => x < 20);
Console.WriteLine("InfiniteSequence(1, 3).TakeWhile(x < 20): " + string.Join(",", doProgu));

Console.WriteLine();
Console.WriteLine("--- 4. Praktyczny przyklad: offsety stron do paginacji API ---");
const int totalItems = 95;
const int pageSize = 20;
// Zamiast petli for (int offset = 0; offset < totalItems; offset += pageSize) ...
IEnumerable<int> offsety = Enumerable.Sequence(0, totalItems - 1, pageSize);
Console.WriteLine($"offsety stron (total={totalItems}, pageSize={pageSize}): " + string.Join(",", offsety));

Console.WriteLine();
Console.WriteLine("--- 5. HACZYK: walidacja argumentow jest EAGER, nie leniwa jak reszta LINQ ---");
Console.WriteLine("Wywolanie Enumerable.Sequence(1, 5, 0) (step=0), PRZED jakakolwiek enumeracja:");
try
{
    var zerowyKrok = Enumerable.Sequence(1, 5, 0);
    Console.WriteLine("  nie rzucilo - zaskoczenie, typ: " + zerowyKrok.GetType().Name);
}
catch (ArgumentOutOfRangeException ex)
{
    Console.WriteLine($"  rzucilo NATYCHMIAST przy wywolaniu (eager validation): {ex.GetType().Name} (parametr '{ex.ParamName}')");
}

Console.WriteLine("Wywolanie Enumerable.Sequence(10, 1, 1) (zly kierunek: start > endInclusive, step dodatni):");
try
{
    var zlyKierunek = Enumerable.Sequence(10, 1, 1);
    Console.WriteLine("  count = " + zlyKierunek.Count());
}
catch (ArgumentOutOfRangeException ex)
{
    Console.WriteLine($"  rzucilo NATYCHMIAST przy wywolaniu: {ex.GetType().Name} (parametr '{ex.ParamName}')");
}

Console.WriteLine();
Console.WriteLine("--- 6. Przypadek brzegowy: endInclusive == start -> jeden element ---");
IEnumerable<int> jedenElement = Enumerable.Sequence(5, 5, 1);
Console.WriteLine("Sequence(5, 5, 1): " + string.Join(",", jedenElement));
