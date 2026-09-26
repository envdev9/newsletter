namespace Orders.App;

public record Order(int Id, string Customer, decimal NetAmount);

public static class OrderPricing
{
    public static decimal WithVat(Order order) => Math.Round(order.NetAmount * 1.23m, 2);
}
