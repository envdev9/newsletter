using Microsoft.EntityFrameworkCore;

namespace PgPlanDemo;

public class Customer
{
    public int Id { get; set; }
    public string Email { get; set; } = "";
}

public class ShopContext : DbContext
{
    private readonly string _cs;
    private readonly ParameterTranslationMode? _mode;
    private readonly IEnumerable<Microsoft.EntityFrameworkCore.Diagnostics.IInterceptor> _interceptors;

    /// <param name="mode">null = nie ustawiaj (domyslne zachowanie Npgsql)</param>
    public ShopContext(string cs, ParameterTranslationMode? mode = null,
        params Microsoft.EntityFrameworkCore.Diagnostics.IInterceptor[] interceptors)
    {
        _cs = cs;
        _mode = mode;
        _interceptors = interceptors;
    }

    public DbSet<Customer> Customers => Set<Customer>();

    protected override void OnConfiguring(DbContextOptionsBuilder options)
    {
        options.UseNpgsql(_cs, o =>
        {
            if (_mode is { } m) o.UseParameterizedCollectionMode(m);
        });
        // porownujemy tryby w jednym procesie - cache dostawcy uslug utrwalilby pierwszy tryb (patrz #15)
        options.EnableServiceProviderCaching(false);
        options.AddInterceptors(_interceptors);
    }

    protected override void OnModelCreating(ModelBuilder b)
    {
        b.Entity<Customer>(e =>
        {
            e.ToTable("customers");
            e.Property(c => c.Email).HasMaxLength(100);
            e.HasIndex(c => c.Email); // zwykly btree - o to wlasnie chodzi w pomiarze
        });
    }
}
