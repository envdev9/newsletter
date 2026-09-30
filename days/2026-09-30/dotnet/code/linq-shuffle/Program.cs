// Enumerable.Shuffle<T> - nowosc LINQ w .NET 10.
// Potwierdzone empirycznie w tej sesji: na SDK 9.0.316 (net9.0) wywolanie
// `tablica.Shuffle()` daje CS1061 - patrz ../compat-check.

int[] questions = [1, 2, 3, 4, 5, 6, 7, 8, 9, 10];

Console.WriteLine("--- 1. Podstawowe tasowanie ---");
IEnumerable<int> shuffled = questions.Shuffle();
Console.WriteLine("oryginalna tablica: " + string.Join(",", questions));
Console.WriteLine("questions.Shuffle() (zmaterializowane raz): " + string.Join(",", shuffled.ToArray()));
Console.WriteLine("oryginalna tablica po Shuffle() - NIE zmieniona: " + string.Join(",", questions));

Console.WriteLine();
Console.WriteLine("--- 2. HACZYK: Shuffle() jest leniwe i tasuje NA NOWO przy kazdej enumeracji ---");
IEnumerable<int> lazyShuffle = questions.Shuffle();
var pierwszaEnumeracja = lazyShuffle.ToArray();
var drugaEnumeracja = lazyShuffle.ToArray();
Console.WriteLine("1. enumeracja tej samej zmiennej: " + string.Join(",", pierwszaEnumeracja));
Console.WriteLine("2. enumeracja tej samej zmiennej: " + string.Join(",", drugaEnumeracja));
Console.WriteLine("identyczna kolejnosc obu enumeracji? " + pierwszaEnumeracja.SequenceEqual(drugaEnumeracja));
Console.WriteLine("typ zwracany: " + lazyShuffle.GetType().Name + " (deferred execution, jak reszta LINQ)");

Console.WriteLine();
Console.WriteLine("--- 3. Poprawny idiom: zmaterializuj RAZ, jesli kolejnosc ma byc stabilna ---");
int[] stabilnaKolejnosc = questions.Shuffle().ToArray();
Console.WriteLine("stabilna kolejnosc (ta sama przy kazdym odczycie tej tablicy): " + string.Join(",", stabilnaKolejnosc));
Console.WriteLine("odczyt ponowny tej samej tablicy: " + string.Join(",", stabilnaKolejnosc));

Console.WriteLine();
Console.WriteLine("--- 4. Dziala na dowolnym IEnumerable<T>, nie tylko na tablicy ---");
IEnumerable<string> LiterySource()
{
    yield return "A";
    yield return "B";
    yield return "C";
    yield return "D";
}
Console.WriteLine("potasowane litery z lazy source: " + string.Join(",", LiterySource().Shuffle().ToArray()));
