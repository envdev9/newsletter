namespace EfDemo;

public class Customer
{
    public int Id { get; set; }
    public string Email { get; set; } = "";
    public string Name { get; set; } = "";
    public List<Order> Orders { get; set; } = new();
    public List<Tag> Tags { get; set; } = new();
}

public class Order
{
    public int Id { get; set; }
    public int CustomerId { get; set; }
    public decimal Total { get; set; }
    public Customer? Customer { get; set; }
}

public record OrderCount(string Name, int Orders);

public class Tag
{
    public int Id { get; set; }
    public int CustomerId { get; set; }
    public string Label { get; set; } = "";
}
