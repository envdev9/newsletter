using System;
using System.Text.Json;
using System.Text.Json.Nodes;

// Ten projekt celuje w net9.0 i sluzy WYLACZNIE do pokazania, ktore API z artykulu NIE istnieja w .NET 9.
// Oczekiwane bledy kompilatora (dokladnie 5, patrz code/README.md) pochodza z linii oznaczonych "NOWE".
// Linie oznaczone "STARE" musza sie skompilowac - to dowod, ze nowy jest tylko wariant z 'out int'.

var o = new JsonObject { ["a"] = 1 };

// STARE (.NET 9 ma): dostep po indeksie, TryAdd/TryGetPropertyValue bez indeksu
int stary1 = o.IndexOf("a");
var stary2 = o.GetAt(0);
o.Insert(1, "b", 2);
o.SetAt(0, 5);
o.RemoveAt(1);
bool stary3 = o.TryGetPropertyValue("a", out var v0);

// NOWE (.NET 10)
bool n1 = o.TryAdd("c", 3, out int i1);                       // JsonObject.TryAdd z out int
bool n2 = o.TryGetPropertyValue("a", out var v1, out int i2); // TryGetPropertyValue z out int

var w = new Utf8JsonWriter(Stream.Null);
w.WriteStringValueSegment("abc".AsSpan(), false);             // NOWE: char
w.WriteStringValueSegment("abc"u8, true);                     // NOWE: byte
w.WriteBase64StringSegment("abc"u8, true);                    // NOWE: base64
