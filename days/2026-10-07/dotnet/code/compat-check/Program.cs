using System.Buffers;

// Ten plik CELOWO nie kompiluje sie na net9.0 - to dowod, ze funkcje sa nowe w .NET 10.

// --- Funkcja 1: MemoryExtensions.CountAny/ReplaceAny/ReplaceAnyExcept z SearchValues<T> ---
SearchValues<char> sv = SearchValues.Create("abc");
char[] buf = "abcdef".ToCharArray();
int n = buf.AsSpan().CountAny(sv);                 // NOWE w .NET 10
buf.AsSpan().ReplaceAny(sv, '_');                  // NOWE w .NET 10
buf.AsSpan().ReplaceAnyExcept(sv, '_');            // NOWE w .NET 10
"abcdef".AsSpan().ReplaceAny(buf, sv, '_');        // NOWE w .NET 10 (source -> destination)

// STARE (kompiluja sie na net9.0): IndexOfAny/ContainsAny/IndexOfAnyExcept z SearchValues
int i1 = buf.AsSpan().IndexOfAny(sv);
bool b1 = buf.AsSpan().ContainsAny(sv);
int i2 = buf.AsSpan().IndexOfAnyExcept(sv);

// --- Funkcja 2: System.Linq.AsyncEnumerable (LINQ na IAsyncEnumerable<T> w BCL) ---
static async IAsyncEnumerable<int> Gen() { await Task.Yield(); yield return 1; }
var l = await Gen().Where(x => x > 0).Select(x => x * 2).ToListAsync();   // NOWE w .NET 10
int c = await Gen().CountAsync();                                          // NOWE w .NET 10
