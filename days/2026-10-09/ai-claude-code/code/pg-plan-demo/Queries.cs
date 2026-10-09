using Microsoft.EntityFrameworkCore;

namespace PgPlanDemo;

/// <summary>Zapytania mierzone w demo. Kazde zwraca liczbe wierszy (materializacja, zeby zapytanie na pewno poszlo do bazy).</summary>
public static class Queries
{
    public static int Equals(ShopContext db, string email)
        => Rows(db.Customers.Where(c => c.Email == email));

    public static int StartsWith(ShopContext db, string prefix)
        => Rows(db.Customers.Where(c => c.Email.StartsWith(prefix)));

    public static int Contains(ShopContext db, string term)
        => Rows(db.Customers.Where(c => c.Email.Contains(term)));

    public static int EndsWith(ShopContext db, string suffix)
        => Rows(db.Customers.Where(c => c.Email.EndsWith(suffix)));

    public static int ByIds(ShopContext db, List<int> ids)
        => Rows(db.Customers.Where(c => ids.Contains(c.Id)));

    // materializacja zapytania i policzenie wierszy po stronie C# - celowo w osobnej metodzie (zapytanie jest juz zawezone)
    private static int Rows(IQueryable<Customer> q)
    {
        var list = q.AsNoTracking().ToList();
        return list.Count;
    }

    // "spill" w Postgresie: hash join i sortowanie przy malym work_mem
    public static int SelfJoinCount(ShopContext db)
        => (from a in db.Customers
            join b in db.Customers on a.Email equals b.Email
            select a.Id).Count();

    public static int SortAll(ShopContext db)
        => Rows(db.Customers.OrderBy(c => c.Email));
}
