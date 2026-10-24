using Microsoft.EntityFrameworkCore;

namespace EfPlanDemo;

public class Customer
{
    public int Id { get; set; }
    public string Email { get; set; } = "";
    public string Name { get; set; } = "";
}

// Email = varchar(100) + indeks (IsUnicode(false), zeby nie mieszac tego wydania z #14).
public class ShopContext : DbContext
{
    public ShopContext(DbContextOptions options) : base(options) { }

    public DbSet<Customer> Customers => Set<Customer>();

    protected override void OnModelCreating(ModelBuilder b)
    {
        b.Entity<Customer>(e =>
        {
            e.Property(c => c.Email).HasMaxLength(100).IsUnicode(false);
            e.HasIndex(c => c.Email);
        });
    }
}
