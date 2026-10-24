using System.Runtime.CompilerServices;

// Zrodlo asynchroniczne: generator, ktory loguje swoj cykl zycia.
static async IAsyncEnumerable<int> Zrodlo(int ile, string nazwa, [EnumeratorCancellation] CancellationToken ct = default)
{
    int oddane = 0;
    Console.WriteLine($"   [{nazwa}] start");
    try
    {
        for (int i = 1; i <= ile; i++)
        {
            await Task.Delay(1, ct);
            oddane++;
            yield return i;
        }
    }
    finally { Console.WriteLine($"   [{nazwa}] dispose (finally), oddanych elementow: {oddane}"); }
}

Console.WriteLine("--- 1. Zapytanie LINQ na IAsyncEnumerable<T> - bez NuGet System.Linq.Async ---");
var wynik = await Zrodlo(10, "A")
    .Where(x => x % 2 == 0)
    .Select(x => x * x)
    .ToListAsync();
Console.WriteLine($"Where+Select+ToListAsync: [{string.Join(", ", wynik)}]");

Console.WriteLine();
Console.WriteLine("--- 2. Agregaty: CountAsync, SumAsync, MaxAsync ---");
Console.WriteLine($"CountAsync = {await Zrodlo(5, "B").CountAsync(x => x > 2)}");
Console.WriteLine($"SumAsync   = {await Zrodlo(5, "C").SumAsync()}");
Console.WriteLine($"MaxAsync   = {await Zrodlo(5, "D").MaxAsync()}");

Console.WriteLine();
Console.WriteLine("--- 3. Lenistwosc i wczesne przerwanie: Take(2) dispose'uje zrodlo ---");
var zapytanie = Zrodlo(100, "E").Take(2);
Console.WriteLine("zapytanie zbudowane - nic sie jeszcze nie wykonalo (brak logu 'start' powyzej)");
var dwa = await zapytanie.ToListAsync();
Console.WriteLine($"wynik: [{string.Join(", ", dwa)}]");

Console.WriteLine();
Console.WriteLine("--- 4. Praktyka: async predykat z CancellationToken (np. sprawdzenie w sieci) ---");
static async ValueTask<bool> CzyDostepny(int id, CancellationToken ct)
{
    await Task.Delay(1, ct);
    return id % 3 != 0;
}
var dostepne = await Zrodlo(6, "F").Where(CzyDostepny).ToListAsync();
Console.WriteLine($"dostepne: [{string.Join(", ", dostepne)}]");

Console.WriteLine();
Console.WriteLine("--- 5. Zwykle IEnumerable -> async: ToAsyncEnumerable ---");
var z = await new[] { 3, 1, 2 }.ToAsyncEnumerable().Order().ToListAsync();
Console.WriteLine($"Order: [{string.Join(", ", z)}]");

Console.WriteLine();
Console.WriteLine("--- 6. HACZYK A: kazda enumeracja uruchamia zrodlo OD NOWA ---");
var lenive = Zrodlo(2, "G").Select(x => x + 100);
Console.WriteLine($"pierwszy raz: {await lenive.CountAsync()}");
Console.WriteLine($"drugi raz   : {await lenive.CountAsync()}");

Console.WriteLine();
Console.WriteLine("--- 7. HACZYK B: anulowanie - token przekazany do ToListAsync plynie do generatora ---");
using (var cts = new CancellationTokenSource(millisecondsDelay: 5))
{
    try
    {
        var wolne = await Zrodlo(1000, "H").Select(x => x).ToListAsync(cts.Token);
        Console.WriteLine($"NIE rzucilo, elementow: {wolne.Count}");
    }
    catch (OperationCanceledException e) { Console.WriteLine($"RZUCILO {e.GetType().Name}"); }
}

Console.WriteLine();
Console.WriteLine("--- 8. HACZYK C: wyjatek w srodku - gdzie wychodzi i czy zrodlo jest posprzatane ---");
var zly = Zrodlo(5, "I").Select(x => x == 3 ? throw new InvalidOperationException("boom na 3") : x);
try { await zly.ToListAsync(); }
catch (Exception e) { Console.WriteLine($"RZUCILO {e.GetType().Name}: {e.Message}"); }

Console.WriteLine();
Console.WriteLine("--- 9. HACZYK D: FirstAsync na pustym i FirstOrDefaultAsync ---");
try { await Zrodlo(0, "J").FirstAsync(); }
catch (Exception e) { Console.WriteLine($"FirstAsync: RZUCILO {e.GetType().Name}: \"{e.Message}\""); }
Console.WriteLine($"FirstOrDefaultAsync: {await Zrodlo(0, "K").FirstOrDefaultAsync()}");
