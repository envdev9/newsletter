// Plik "recznie pisany": deklaracje definiujace (jak z generatora) + reszta logiki.
// W realu deklaracje definiujace wygenerowalby source generator, a implementacje
// pisalby Ty - albo odwrotnie.

var s = new Sensor("temp-1", 21.5);

s.Changed += v => Console.WriteLine($"  [handler] nowa wartosc: {v}");
s.Changed += v => Console.WriteLine($"  [handler 2] {v}");
s.Update(22.0);
s.Update(23.5);

Console.WriteLine($"Log konstruktora: {string.Join(" | ", s.Trace)}");
Console.WriteLine($"Liczba subskrybentow: {s.SubscriberCount}");

var d = new Sensor("bez-wartosci");
Console.WriteLine($"Konstruktor 1-arg -> Name={d.Name}, Value={d.Value}");

// --- Czesc 1: "uzytkownik" --------------------------------------------------
public partial class Sensor
{
    public string Name { get; }
    public double Value { get; private set; }
    public List<string> Trace { get; } = new();

    // Implementujaca deklaracja: tu jest ciało I ewentualny initializer (: this/: base).
    public partial Sensor(string name, double initial)
    {
        Name = name;
        Value = initial;
        Trace.Add("ctor(ręczna implementacja)");
    }

    // Konstruktor delegujacy do partial ctor - zwykly, nie-partial.
    public Sensor(string name) : this(name, double.NaN) { }

    public void Update(double v)
    {
        Value = v;
        _handlers?.Invoke(v); // event z add/remove nie jest "field-like" - wolamy delegata
    }
}

// --- Czesc 2: "wygenerowana" -------------------------------------------------
public partial class Sensor
{
    // Definiujaca deklaracja konstruktora: sam podpis, srednik, brak ciala.
    public partial Sensor(string name, double initial);

    // Partial event: definiujaca deklaracja jest "field-like" (bez add/remove)...
    public partial event Action<double>? Changed;
}

// --- Czesc 3: implementacja eventu (np. dopisana przez dewelopera) -----------
public partial class Sensor
{
    private Action<double>? _handlers;
    public int SubscriberCount => _handlers?.GetInvocationList().Length ?? 0;

    // ...a implementujaca MUSI miec add/remove.
    public partial event Action<double>? Changed
    {
        add { _handlers += value; Trace.Add("add"); }
        remove { _handlers -= value; Trace.Add("remove"); }
    }
}
