// Ten projekt CELOWO sie nie kompiluje na net9.0 - to dowod "przed i po" dla artykulu.
// Domyslnie aktywny jest Dowod 1 (Enumerable.Shuffle). Zeby zobaczyc Dowod 2
// (JsonSerializerOptions.Strict), zakomentuj blok "Dowod 1" i odkomentuj "Dowod 2".

using System;
// using System.Text.Json;

// --- Dowod 1: Enumerable.Shuffle<T> nie istnieje w .NET 9 ---
// Rzeczywisty blad (zweryfikowany `dotnet build`, SDK 9.0.316):
// CS1061: 'int[]' does not contain a definition for 'Shuffle' and no accessible
//         extension method 'Shuffle' accepting a first argument of type 'int[]'
//         could be found (are you missing a using directive or an assembly reference?)
int[] data = [1, 2, 3];
var shuffled = data.Shuffle();
Console.WriteLine(string.Join(",", shuffled));

// --- Dowod 2: JsonSerializerOptions.Strict nie istnieje w .NET 9 ---
// Rzeczywisty blad (zweryfikowany `dotnet build`, SDK 9.0.316):
// CS0117: 'JsonSerializerOptions' does not contain a definition for 'Strict'
// var opts = JsonSerializerOptions.Strict;
// Console.WriteLine(opts);
