var d = new OrderedDictionary<string, int>();

// Dziala na .NET 9 (stare przeciazenia) - ta linia NIE ma dawac bledu:
d.TryAdd("a", 1);
d.TryGetValue("a", out int v0);

// Nowe w .NET 10 - na net9.0 maja dac blad kompilacji:
bool added = d.TryAdd("b", 2, out int idx);
bool found = d.TryGetValue("b", out int v, out int idx2);

Console.WriteLine($"{added} {idx} {found} {v} {idx2} {v0}");
