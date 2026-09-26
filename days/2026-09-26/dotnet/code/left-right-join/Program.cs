record Customer(int Id, string Name);
record Order(int Id, int CustomerId, decimal Total);

static class Demo
{
    static void Main()
    {
        Customer[] customers =
        [
            new(1, "Ada"), new(2, "Bob"), new(3, "Cyd"),
        ];
        Order[] orders =
        [
            new(100, 1, 50m), new(101, 1, 70m), new(102, 2, 15m),
            new(103, 99, 999m), // sierota: klient 99 nie istnieje
        ];

        Console.WriteLine("--- 1. Stary sposob: GroupJoin + SelectMany + DefaultIfEmpty ---");
        var old = customers
            .GroupJoin(orders, c => c.Id, o => o.CustomerId, (c, os) => new { c, os })
            .SelectMany(x => x.os.DefaultIfEmpty(), (x, o) => (x.c, o));
        foreach (var (c, o) in old)
            Console.WriteLine($"{c.Name,-4} -> {(o is null ? "(brak)" : o.Total.ToString())}");

        Console.WriteLine("--- 2. .NET 10: Enumerable.LeftJoin ---");
        var left = customers.LeftJoin(orders, c => c.Id, o => o.CustomerId,
            (c, o) => (Customer: c, Order: o)); // o jest Order? (null gdy brak)
        foreach (var (c, o) in left)
            Console.WriteLine($"{c.Name,-4} -> {(o is null ? "(brak)" : o.Total.ToString())}");

        Console.WriteLine("--- 3. .NET 10: Enumerable.RightJoin (zamawiajacy moze nie istniec) ---");
        var right = customers.RightJoin(orders, c => c.Id, o => o.CustomerId,
            (c, o) => (Customer: c, Order: o)); // c jest Customer? (null gdy brak)
        foreach (var (c, o) in right)
            Console.WriteLine($"zamowienie {o.Id} -> {c?.Name ?? "(nieznany klient)"}");

        Console.WriteLine("--- 4. Kolejnosc wyniku LeftJoin = kolejnosc outer, potem kolejnosc inner ---");
        Console.WriteLine(string.Join(", ", left.Select(t => $"{t.Customer.Name}/{t.Order?.Id.ToString() ?? "-"}")));

        Console.WriteLine("--- 5. Anti-join: klienci bez zamowien ---");
        var noOrders = customers.LeftJoin(orders, c => c.Id, o => o.CustomerId, (c, o) => (c, o))
            .Where(t => t.o is null).Select(t => t.c.Name);
        Console.WriteLine(string.Join(", ", noOrders));
    }
}
