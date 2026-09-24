// Przykład edukacyjny: C# 14 "extension members" (extension blocks).
// Rozszerzamy System.String o właściwość instancyjną ORAZ o statyczną metodę
// fabrykującą - czego stare "extension methods" (C# 3-13) nigdy nie potrafiły.

var candidates = new[] { "haslo123", "Tr0ub4dor&3", "abc", "K0min1arz!2026" };

foreach (var password in candidates)
{
    // IsStrongPassword wygląda jak zwykła właściwość na stringu, a jest zdefiniowana
    // w zupełnie osobnej klasie statycznej niżej w pliku.
    var verdict = password.IsStrongPassword ? "OK" : "za słabe";
    Console.WriteLine($"{password,-16} -> {verdict}");
}

// To jest sedno nowości: statyczny członek wywołany bezpośrednio na typie string,
// tak jakby string.GenerateStrong(...) był metodą wbudowaną w .NET.
var generated = string.GenerateStrong(length: 12);
Console.WriteLine($"\nWygenerowane hasło: {generated}");
Console.WriteLine($"Czy przechodzi własną walidację? {generated.IsStrongPassword}");

public static class PasswordExtensions
{
    // Blok "extension(Type identyfikator)" - identyfikator działa jak "this" w
    // starych extension methods, ale wewnątrz bloku można definiować też properties
    // i statyczne members, nie tylko metody instancyjne.
    extension(string password)
    {
        public bool IsStrongPassword =>
            password.Length >= 8
            && password.Any(char.IsUpper)
            && password.Any(char.IsDigit)
            && password.Any(c => !char.IsLetterOrDigit(c));

        // Statyczny member zdefiniowany w bloku extension(string ...) jest wołany
        // jako string.GenerateStrong(...) - nie PasswordExtensions.GenerateStrong(...).
        // To właśnie było niemożliwe przed C# 14.
        public static string GenerateStrong(int length)
        {
            const string letters = "ABCDEFGHJKLMNPQRSTUVWXYZabcdefghijkmnpqrstuvwxyz";
            const string digits = "23456789";
            const string symbols = "!@#$%^&*";
            var rng = Random.Shared;

            var chars = new List<char>
            {
                letters[rng.Next(letters.Length)],
                letters[rng.Next(letters.Length)].ToString().ToUpperInvariant()[0],
                digits[rng.Next(digits.Length)],
                symbols[rng.Next(symbols.Length)],
            };
            while (chars.Count < Math.Max(length, chars.Count))
            {
                chars.Add(letters[rng.Next(letters.Length)]);
            }

            return new string(chars.OrderBy(_ => rng.Next()).ToArray());
        }
    }
}
