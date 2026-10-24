using Microsoft.EntityFrameworkCore;

namespace EfDemo;

// Poprawione odpowiedniki z BadQueries - skaner ma tu milczec.
public static class GoodQueries
{
    public static IQueryable<Customer> EmailQuery(GoodShopContext db, string email)
    {
        return db.Customers.Where(c => c.Email == email);
    }

    // Porownanie bez funkcji na kolumnie (kolacja SQL Server i tak jest case-insensitive).
    public static List<Customer> CustomersByEmail(GoodShopContext db, string email)
    {
        return db.Customers.AsNoTracking().Where(c => c.Email == email).ToList();
    }

    // Jedno zapytanie z GROUP BY zamiast N+1.
    public static List<OrderCount> OrderCounts(GoodShopContext db)
    {
        return db.Customers
            .Select(c => new OrderCount(c.Name, c.Orders.Count))
            .ToList();
    }

    // Filtr w SQL, do aplikacji wraca jedna liczba.
    public static int ExpensiveOrders(GoodShopContext db)
    {
        return db.Orders.Count(o => o.Total > 900m);
    }

    // Split query: osobne zapytanie na kazda kolekcje, bez mnozenia wierszy.
    public static List<Customer> CustomersWithOrdersAndTags(GoodShopContext db)
    {
        return db.Customers
            .AsNoTracking()
            .Include(c => c.Orders)
            .Include(c => c.Tags)
            .AsSplitQuery()
            .ToList();
    }

    public static List<Order> AllOrders(GoodShopContext db)
    {
        return db.Orders.AsNoTracking().Where(o => o.Total > 0m).ToList();
    }

    // Jeden SaveChanges na paczke.
    public static void AddBatch(GoodShopContext db, IEnumerable<string> labels, int customerId)
    {
        foreach (var label in labels)
        {
            db.Tags.Add(new Tag { CustomerId = customerId, Label = label });
        }
        db.SaveChanges();
    }
}
