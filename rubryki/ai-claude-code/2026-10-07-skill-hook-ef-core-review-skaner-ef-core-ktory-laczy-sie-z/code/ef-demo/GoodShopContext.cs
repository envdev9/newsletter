using Microsoft.EntityFrameworkCore;

namespace EfDemo;

// "Dobry" model: kolumna Email jawnie oznaczona jako varchar -> parametr tez varchar.
public class GoodShopContext : DbContext
{
    public GoodShopContext(DbContextOptions options) : base(options) { }

    public DbSet<Customer> Customers => Set<Customer>();
    public DbSet<Order> Orders => Set<Order>();
    public DbSet<Tag> Tags => Set<Tag>();

    protected override void OnModelCreating(ModelBuilder b)
    {
        b.Entity<Customer>(e =>
        {
            e.Property(c => c.Email).HasMaxLength(100).IsUnicode(false);
            e.HasIndex(c => c.Email);
        });
    }
}
