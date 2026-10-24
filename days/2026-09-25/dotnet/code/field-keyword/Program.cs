// C# 14: słowo kluczowe `field` w semi-auto properties.
using System.ComponentModel;

var user = new UserProfile();
user.PropertyChanged += (_, e) => Console.WriteLine($"  [event] zmieniono: {e.PropertyName}");

Console.WriteLine("--- Name: walidacja + trim w setterze ---");
user.Name = "  Ada Lovelace  ";
Console.WriteLine($"Name = '{user.Name}'");
user.Name = "Ada Lovelace";            // ta sama wartość -> brak eventu
try { user.Name = "   "; }
catch (ArgumentException ex) { Console.WriteLine($"Wyjątek: {ex.Message}"); }

Console.WriteLine("--- Email: getter z domyślną wartością, setter z normalizacją ---");
Console.WriteLine($"Email (przed ustawieniem) = '{user.Email}'");
user.Email = "ADA@Example.COM";
Console.WriteLine($"Email = '{user.Email}'");

Console.WriteLine("--- Tags: leniwa inicjalizacja w getterze ---");
Console.WriteLine($"Tags.Count = {user.Tags.Count}");
user.Tags.Add("math");
Console.WriteLine($"Tags = [{string.Join(", ", user.Tags)}]");

Console.WriteLine($"--- Ile razy leniwy getter tworzył listę: {user.TagsCreated} ---");

public class UserProfile : INotifyPropertyChanged
{
    public event PropertyChangedEventHandler? PropertyChanged;

    // Wcześniej: ręczne pole _name + cała ceremonia. Teraz: `field` to
    // niejawne pole zapasowe generowane przez kompilator.
    public string Name
    {
        get;
        set
        {
            ArgumentException.ThrowIfNullOrWhiteSpace(value);
            var trimmed = value.Trim();
            if (field == trimmed) return;
            field = trimmed;
            PropertyChanged?.Invoke(this, new(nameof(Name)));
        }
    } = "";

    // Getter ma logikę, setter pozostaje auto (`set;`) - mieszanie jest legalne.
    public string Email
    {
        get => string.IsNullOrEmpty(field) ? "(brak)" : field;
        set => field = value.ToLowerInvariant();
    }

    public int TagsCreated { get; private set; }

    // Leniwa inicjalizacja bez ręcznego pola.
    public List<string> Tags
    {
        get
        {
            if (field is null)
            {
                field = new();
                TagsCreated++;
            }
            return field;
        }
    }
}
