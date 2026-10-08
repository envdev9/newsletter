using Microsoft.EntityFrameworkCore;

namespace EfDemo;

// "Zly" model: Email jest zwyklym stringiem -> EF mapuje go na nvarchar,
// a w bazie (db-first / reczna migracja) kolumna to varchar(100) z indeksem.
public class BadShopContext : DbContext
{
    public BadShopContext(DbContextOptions options) : base(options) { }

    public DbSet<Customer> Customers => Set<Customer>();
    public DbSet<Order> Orders => Set<Order>();
    public DbSet<Tag> Tags => Set<Tag>();

    protected override void OnModelCreating(ModelBuilder b)
    {
        b.Entity<Customer>(e =>
        {
            e.Property(c => c.Email).HasMaxLength(100);
            e.HasIndex(c => c.Email);
        });
    }
}
