using Microsoft.EntityFrameworkCore;

namespace EfDemo;

// Kazda metoda ponizej to jeden antywzorzec EF Core. Skaner scan_ef.py ma je wszystkie wylapac.
public static class BadQueries
{
    // Zapytanie po Email - problem jest w mapowaniu (BadShopContext), nie w LINQ.
    public static IQueryable<Customer> EmailQuery(BadShopContext db, string email)
    {
        return db.Customers.Where(c => c.Email == email);
    }

    // Funkcja na kolumnie w Where -> LOWER([c].[Email]) = ... (nie-sargowalne) + sledzenie encji.
    public static List<Customer> CustomersByEmailLower(BadShopContext db, string email)
    {
        return db.Customers.Where(c => c.Email.ToLower() == email.ToLower()).ToList();
    }

    // N+1: jedno zapytanie o klientow + po jednym COUNT na kazdego.
    public static List<OrderCount> OrderCountsNPlusOne(BadShopContext db)
    {
        var result = new List<OrderCount>();
        foreach (var c in db.Customers.AsNoTracking().ToList())
        {
            var n = db.Orders.Count(o => o.CustomerId == c.Id);
            result.Add(new OrderCount(c.Name, n));
        }
        return result;
    }

    // ToList() przed Where(): cala tabela leci do pamieci, filtr dziala w C#.
    public static int ExpensiveOrdersInMemory(BadShopContext db)
    {
        return db.Orders.AsNoTracking().ToList().Where(o => o.Total > 900m).Count();
    }

    // Dwie kolekcje w jednym zapytaniu -> iloczyn kartezjanski wierszy.
    public static List<Customer> CustomersWithOrdersAndTags(BadShopContext db)
    {
        return db.Customers
            .AsNoTracking()
            .Include(c => c.Orders)
            .Include(c => c.Tags)
            .ToList();
    }

    // Odczyt bez AsNoTracking: encje trafiaja do ChangeTrackera, choc nic nie zapisujemy.
    public static List<Order> AllOrdersTracked(BadShopContext db)
    {
        return db.Orders.Where(o => o.Total > 0m).ToList();
    }

    // SaveChanges w petli: jedna runda do bazy na kazdy wiersz.
    public static void AddOneByOne(BadShopContext db, IEnumerable<string> labels, int customerId)
    {
        foreach (var label in labels)
        {
            db.Tags.Add(new Tag { CustomerId = customerId, Label = label });
            db.SaveChanges();
        }
    }
}
