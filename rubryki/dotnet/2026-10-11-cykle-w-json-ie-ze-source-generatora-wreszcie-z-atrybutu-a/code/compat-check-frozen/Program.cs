using System.Collections.Frozen;

// Na net9.0 FrozenDictionary nie ma statycznego Create(ReadOnlySpan<KeyValuePair<,>>)
// - kompilacja ma sie nie udac (CS0117).
// FrozenSet.Create(ReadOnlySpan<T>) kompiluje sie na net9.0 bez bledu: to NIE jest nowosc .NET 10
// (zmierzone: ta linia nie daje bledu).
var d = FrozenDictionary.Create<string, int>([new("PL", 48)]);
var s = FrozenSet.Create<string>(["a", "b"]);
Console.WriteLine(d.Count + s.Count);
