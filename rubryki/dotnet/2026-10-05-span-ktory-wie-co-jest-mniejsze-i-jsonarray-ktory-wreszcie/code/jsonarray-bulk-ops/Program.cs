using System;
using System.Text.Json.Nodes;

Console.WriteLine("--- 1. Problem: dotychczas JsonArray nie mial RemoveAll/RemoveRange, tylko RemoveAt(int) ---");
var staroStyl = new JsonArray(1, 2, 3, 4, 5, 6);
Console.WriteLine($"Przed: {Compact(staroStyl)}");
// Stary idiom: usuwanie w PETLI OD TYLU, bo RemoveAt przesuwa indeksy w przod przy iteracji w przod
for (int i = staroStyl.Count - 1; i >= 0; i--)
{
    if (staroStyl[i]!.GetValue<int>() % 2 == 0)
        staroStyl.RemoveAt(i);
}
Console.WriteLine($"Po recznej petli 'od tylu' (usun parzyste): {Compact(staroStyl)}");
Console.WriteLine("-> dziala, ale latwo o blad (iteracja w przod + RemoveAt = pomijanie elementow).");
Console.WriteLine();

Console.WriteLine("--- 2. .NET 10: JsonArray.RemoveAll(predicate) - jedna linia, bez recznej petli ---");
var dane = new JsonArray(1, 2, 3, 4, 5, 6);
int usuniete = dane.RemoveAll(x => x!.GetValue<int>() % 2 == 0);
Console.WriteLine($"RemoveAll(parzyste) usunieto: {usuniete}, zostalo: {Compact(dane)}");
Console.WriteLine();

Console.WriteLine("--- 3. .NET 10: JsonArray.RemoveRange(index, count) - usuwanie SPOJNEGO wycinka ---");
var strona = new JsonArray(10, 20, 30, 40, 50, 60, 70);
Console.WriteLine($"Przed: {Compact(strona)}");
strona.RemoveRange(2, 3); // usuwa indeksy 2,3,4 => 30,40,50
Console.WriteLine($"Po RemoveRange(2, 3): {Compact(strona)}");
Console.WriteLine();

Console.WriteLine("--- 4. Praktyczny przyklad: odfiltrowanie nieprawidlowych wpisow z JSON-a zewnetrznego API ---");
var odpowiedzApi = JsonNode.Parse("""
[
  { "id": 1, "status": "ok" },
  null,
  { "id": 2, "status": "error" },
  { "id": 3, "status": "ok" },
  null
]
""")!.AsArray();
Console.WriteLine($"Surowa odpowiedz: {Compact(odpowiedzApi)}");
// HACZYK: predicate NIE jest null-safe automatycznie - trzeba samemu sprawdzic null
int odfiltrowane = odpowiedzApi.RemoveAll(x => x is null || x["status"]!.GetValue<string>() != "ok");
Console.WriteLine($"RemoveAll (null-safe predicate) usunieto: {odfiltrowane}, zostalo: {Compact(odpowiedzApi)}");
Console.WriteLine();

Console.WriteLine("--- 5. HACZYK A: RemoveAll NIE jest null-safe - predicate bez sprawdzenia 'x is null' rzuca NRE ---");
var zNullem = new JsonArray(JsonValue.Create(1), null, JsonValue.Create(3));
try
{
    zNullem.RemoveAll(x => x!.GetValue<int>() % 2 == 0); // brak sprawdzenia null
    Console.WriteLine("brak wyjatku (nieoczekiwane)");
}
catch (Exception ex)
{
    Console.WriteLine($"Zmierzone realnie: RZUCILO {ex.GetType().Name}: \"{ex.Message}\"");
}
Console.WriteLine();

Console.WriteLine("--- 6. HACZYK B: RemoveRange z count wychodzacym poza granice rzuca ArgumentException ---");
var maly = new JsonArray(1, 2, 3);
try
{
    maly.RemoveRange(1, 10); // za duzy count
    Console.WriteLine("brak wyjatku (nieoczekiwane)");
}
catch (Exception ex)
{
    Console.WriteLine($"Zmierzone realnie: RZUCILO {ex.GetType().Name}: \"{ex.Message}\"");
}

static string Compact(JsonArray arr) => arr.ToJsonString();
