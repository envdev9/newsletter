// C# 14: null-conditional assignment (`a?.b = x`, `a?.b += x`, `a?[i] = x`).

int sideEffects = 0;
int Expensive()
{
    sideEffects++;
    Console.WriteLine("  [Expensive() wywołane]");
    return 42;
}

Console.WriteLine("--- 1. Klasyczne vs C# 14 ---");
Customer? c1 = new() { Name = "Ala" };
Customer? c2 = null;

// Przed C# 14:
if (c1 is not null) c1.Name = "Ala (stare if)";
// Teraz:
c1?.Name = "Ala (nowe ?.)";
c2?.Name = "nigdy nie ustawione";      // brak NRE, brak przypisania
Console.WriteLine($"c1.Name = {c1?.Name}, c2 = {(c2 is null ? "null" : "nie-null")}");

Console.WriteLine("--- 2. Prawa strona jest ewaluowana WARUNKOWO (short-circuit) ---");
c1?.Score = Expensive();
Console.WriteLine($"c1.Score = {c1?.Score}, sideEffects = {sideEffects}");
c2?.Score = Expensive();               // Expensive() NIE zostanie wywołane
Console.WriteLine($"po c2: sideEffects = {sideEffects}");

Console.WriteLine("--- 3. Operatory złożone i indekser ---");
c1?.Score += 8;
Console.WriteLine($"c1.Score = {c1?.Score}");
// c1?.Score++;   // BŁĄD CS1059 - ++/-- NIE są wspierane (sprawdzone kompilatorem)
int[]? arr = new int[3];
int[]? none = null;
arr?[1] = 7;
none?[1] = 7;                          // brak wyjątku
Console.WriteLine($"arr = [{string.Join(",", arr ?? [])}]");

Console.WriteLine("--- 4. Łańcuch: cała reszta pomijana gdy coś w drodze jest null ---");
Order? order = new() { Customer = null };
order?.Customer?.Name = "X";           // Customer == null -> pomijamy
Console.WriteLine($"order.Customer is null: {order?.Customer is null}");
order?.Customer = new() { Name = "Bob" };
order?.Customer?.Name = "Bob II";
Console.WriteLine($"order.Customer.Name = {order?.Customer?.Name}");

Console.WriteLine("--- 5. Jako wyrażenie: typ wyniku staje się nullable ---");
var x = (c1?.Name = "y");     // string? - "y" albo null
var y = (c2?.Name = "z");     // c2 == null -> null
Console.WriteLine($"x = {x ?? "null"}, y = {y ?? "null"}, typ = {x?.GetType().Name}");
var s = (c1?.Score = 5);      // int -> int?
Console.WriteLine($"s = {s}, HasValue = {s.HasValue}");


class Customer { public string Name { get; set; } = ""; public int Score { get; set; } }
class Order { public Customer? Customer { get; set; } }
