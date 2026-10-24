using System.Data.SqlClient;

namespace Shop;

public class OrderService
{
    private const string Password = "Passw0rd!";   // zaszyty sekret

    public Order Get(int id, string customer)
    {
        var sql = "SELECT * FROM Orders WHERE Id = " + id + " AND Customer = '" + customer + "'";
        using var cmd = new SqlCommand(sql);
        return Map(cmd);
    }

    public string Download(HttpClient http, string url)
    {
        return http.GetStringAsync(url).Result;   // blokuje watek
    }

    public async void FireAndForget(Order o)     // async void
    {
        await Save(o);
    }

    public bool HasAny(IQueryable<Order> q)
    {
        return q.Count() > 0;
    }

    public void Swallow()
    {
        try { Run(); }
        catch (Exception) { }
    }
}
