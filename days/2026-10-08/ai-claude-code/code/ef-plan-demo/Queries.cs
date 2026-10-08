using Microsoft.EntityFrameworkCore;

namespace EfPlanDemo;

// Zapytania mierzone w Program.cs. Skaner scan_ef.py (v2) ma oznaczyc dokladnie te, ktore sa kosztowne:
// EmailContains / EmailEndsWith (LIKE-LEADING-WILDCARD), ByIdsConstant (CONTAINS-CONSTANT),
// a ByIds dostaje tylko informacje (CONTAINS-LIST). Reszta ma byc czysta.
public static class Queries
{
    // sargowalne: Seek po indeksie
    public static IQueryable<Customer> EmailEquals(ShopContext db, string email)
        => db.Customers.AsNoTracking().Where(c => c.Email == email);

    // LIKE 'prefix%' - tez Seek (zakres w indeksie)
    public static IQueryable<Customer> EmailStartsWith(ShopContext db, string prefix)
        => db.Customers.AsNoTracking().Where(c => c.Email.StartsWith(prefix));

    // LIKE '%term%' - wiodacy wildcard, indeks nie pomaga: skan calego indeksu
    public static IQueryable<Customer> EmailContains(ShopContext db, string term)
        => db.Customers.AsNoTracking().Where(c => c.Email.Contains(term));

    // LIKE '%suffix' - j.w.
    public static IQueryable<Customer> EmailEndsWith(ShopContext db, string suffix)
        => db.Customers.AsNoTracking().Where(c => c.Email.EndsWith(suffix));

    // Contains na liscie: EF 10 tlumaczy to na IN (@ids1..N) albo OPENJSON zaleznie od rozmiaru/trybu
    public static IQueryable<Customer> ByIds(ShopContext db, List<int> ids)
        => db.Customers.AsNoTracking().Where(c => ids.Contains(c.Id));

    // wymuszone literaly w SQL: kazdy inny zestaw id = inny tekst SQL = inny plan w cache
    public static IQueryable<Customer> ByIdsConstant(ShopContext db, List<int> ids)
        => db.Customers.AsNoTracking().Where(c => EF.Constant(ids).Contains(c.Id));
}
