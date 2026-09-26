using Orders.App;

var order = new Order(1, "Kowalski", 120.50m);
Console.WriteLine(OrderPricing.WithVat(order));
