using System.Buffers;
using System.Diagnostics;
using System.Text;

Console.WriteLine("--- 1. CountAny: ile znakow ze zbioru (bez petli i bez alokacji) ---");
SearchValues<char> samogloski = SearchValues.Create("aeiouyAEIOUY");
string zdanie = "Ala ma kota, a kot ma Ale";
Console.WriteLine($"CountAny(samogloski) = {zdanie.AsSpan().CountAny(samogloski)}");
// to samo "po staremu":
int stare = 0;
foreach (char c in zdanie) if (samogloski.Contains(c)) stare++;
Console.WriteLine($"petla + Contains     = {stare}");

Console.WriteLine();
Console.WriteLine("--- 2. ReplaceAny / ReplaceAnyExcept: sanityzacja nazwy pliku ---");
SearchValues<char> zabronione = SearchValues.Create("\\/:*?\"<>|");
string nazwa = "raport: Q3/Q4 *final*?.txt";
// wersja "do nowego bufora": source -> destination
char[] bufor = new char[nazwa.Length];
nazwa.AsSpan().ReplaceAny(bufor, zabronione, '_');
Console.WriteLine($"ReplaceAny (src->dst) : {new string(bufor)}");
// wersja "w miejscu" na Span<char>
char[] wMiejscu = nazwa.ToCharArray();
wMiejscu.AsSpan().ReplaceAny(zabronione, '_');
Console.WriteLine($"ReplaceAny (w miejscu): {new string(wMiejscu)}");

// ReplaceAnyExcept = "zostaw tylko dozwolone" (biala lista)
SearchValues<char> dozwolone = SearchValues.Create("abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789.-");
string brudny = "zażółć gęślą jaźń 2026!.txt";
char[] slug = brudny.ToCharArray();
slug.AsSpan().ReplaceAnyExcept(dozwolone, '_');
Console.WriteLine($"ReplaceAnyExcept       : {new string(slug)}");
Console.WriteLine($"CountAnyExcept brak -> uzyj Length - CountAny: {brudny.Length - brudny.AsSpan().CountAny(dozwolone)} znakow zastapionych");

Console.WriteLine();
Console.WriteLine("--- 3. Pomiar: 16M znakow, ReplaceAny vs petla vs lancuch string.Replace (Release) ---");
const int N = 16 * 1024 * 1024;
char[] dane = new char[N];
var rnd = new Random(42);
const string alfabet = "abcdefghij\\/:*?\"<>| klmnopqrstuvwxyz";
for (int i = 0; i < N; i++) dane[i] = alfabet[rnd.Next(alfabet.Length)];

// rozgrzewka
dane.AsSpan(0, 1000).CountAny(zabronione);

var sw = new Stopwatch();
long a0 = GC.GetAllocatedBytesForCurrentThread();
sw.Restart();
int cnt = dane.AsSpan().CountAny(zabronione);
sw.Stop();
long a1 = GC.GetAllocatedBytesForCurrentThread();
Console.WriteLine($"CountAny          : {cnt,9} trafien, alokacje {a1 - a0} B");

int cnt2 = 0;
a0 = GC.GetAllocatedBytesForCurrentThread();
sw.Restart();
foreach (char c in dane) if (zabronione.Contains(c)) cnt2++;
sw.Stop();
a1 = GC.GetAllocatedBytesForCurrentThread();
Console.WriteLine($"petla + Contains  : {cnt2,9} trafien, alokacje {a1 - a0} B (wynik zgodny: {cnt == cnt2})");

char[] kopia1 = (char[])dane.Clone();
a0 = GC.GetAllocatedBytesForCurrentThread();
sw.Restart();
kopia1.AsSpan().ReplaceAny(zabronione, '_');
sw.Stop();
a1 = GC.GetAllocatedBytesForCurrentThread();
Console.WriteLine($"ReplaceAny        : alokacje {a1 - a0} B");

string duzy = new string(dane);
a0 = GC.GetAllocatedBytesForCurrentThread();
string s = duzy;
foreach (char c in "\\/:*?\"<>|") s = s.Replace(c, '_');
a1 = GC.GetAllocatedBytesForCurrentThread();
Console.WriteLine($"9x string.Replace : alokacje {(a1 - a0) / (1024 * 1024)} MB (wynik zgodny: {s == new string(kopia1)})");

// czas: srednia z kilku powtorzen, zeby nie wierzyc jednemu pomiarowi
static double Ms(Action act, int rep = 5)
{
    act();
    var w = Stopwatch.StartNew();
    for (int r = 0; r < rep; r++) act();
    return w.Elapsed.TotalMilliseconds / rep;
}
char[] tmp = new char[N];
Console.WriteLine($"czas (sr. z 5): CountAny {Ms(() => dane.AsSpan().CountAny(zabronione)):F1} ms, " +
    $"petla {Ms(() => { int k = 0; foreach (char c in dane) if (zabronione.Contains(c)) k++; }):F1} ms");
Console.WriteLine($"czas (sr. z 5): ReplaceAny {Ms(() => dane.AsSpan().ReplaceAny(tmp, zabronione, '_')):F1} ms, " +
    $"9x string.Replace {Ms(() => { string x = duzy; foreach (char c in "\\/:*?\"<>|") x = x.Replace(c, '_'); }):F1} ms");

Console.WriteLine();
Console.WriteLine("--- 4. HACZYK A: destination krotszy niz source ---");
try { "abcdef".AsSpan().ReplaceAny(new char[3], SearchValues.Create("a"), '_'); Console.WriteLine("NIE rzucilo"); }
catch (Exception e) { Console.WriteLine($"RZUCILO {e.GetType().Name}: \"{e.Message}\""); }

Console.WriteLine();
Console.WriteLine("--- 5. HACZYK B: znaki spoza BMP (emoji = 2 jednostki UTF-16) ---");
string emoji = "a😀b";
char[] e2 = emoji.ToCharArray();
e2.AsSpan().ReplaceAnyExcept(dozwolone, '_');
Console.WriteLine($"\"{emoji}\" (Length {emoji.Length}) -> \"{new string(e2)}\" (zastapionych: {emoji.Length - emoji.AsSpan().CountAny(dozwolone)})");
Console.WriteLine($"a naprawde znakow tekstowych (Rune): {emoji.EnumerateRunes().Count()}");

Console.WriteLine();
Console.WriteLine("--- 6. HACZYK C: pusty zbior i ReplaceAny z newValue ze zbioru ---");
SearchValues<char> pusty = SearchValues.Create(ReadOnlySpan<char>.Empty);
Console.WriteLine($"CountAny(pusty) = {"abc".AsSpan().CountAny(pusty)}");
char[] p = "abc".ToCharArray();
p.AsSpan().ReplaceAnyExcept(pusty, '#');
Console.WriteLine($"ReplaceAnyExcept(pusty) -> {new string(p)}  (pusty zbior = 'wszystko poza nim' = wszystko)");
char[] q = "a-b-c".ToCharArray();
q.AsSpan().ReplaceAny(SearchValues.Create("-"), '-');
Console.WriteLine($"ReplaceAny('-'->'-') -> {new string(q)} (idempotentne, bez wyjatku)");

Console.WriteLine();
Console.WriteLine("--- 7. Bonus: to samo na bajtach UTF-8 (SearchValues<byte>) ---");
byte[] utf8 = Encoding.UTF8.GetBytes("zażółć 1,2;3");
SearchValues<byte> sep = SearchValues.Create(", ;"u8);
utf8.AsSpan().ReplaceAny(sep, (byte)'_');
Console.WriteLine($"{Encoding.UTF8.GetString(utf8)} (CountAny na bajtach: {Encoding.UTF8.GetBytes("zażółć 1,2;3").AsSpan().CountAny(sep)})");
