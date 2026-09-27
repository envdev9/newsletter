namespace Shop;

public class Cache
{
    public string Load(Task<string> t)
    {
        t.Wait();
        return t.Result;
    }

    public async void OnTick()
    {
        await Task.Delay(10);
    }
}
