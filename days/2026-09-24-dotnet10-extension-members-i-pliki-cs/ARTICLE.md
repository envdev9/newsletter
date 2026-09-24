<div align="center">

# 📰 TECH PRASÓWKA
### Wydanie #1 — 24 września 2026

![.NET](https://img.shields.io/badge/.NET-10-512BD4?style=for-the-badge&logo=dotnet&logoColor=white)

## Dwie nowości z .NET 10, które zmieniają codzienne pisanie C#

</div>

---

> _"Extension methods od 20 lat pozwalały udawać, że dopisujesz coś do cudzego typu.
> C# 14 w końcu pozwala to zrobić naprawdę - łącznie ze statycznymi members."_

Dziś dwie rzeczy z .NET 10 / C# 14, obie małe, obie zmieniają codzienną pracę:
**extension members** (rozszerzony `extension` block) i **file-based apps**
(`dotnet run plik.cs` bez żadnego projektu). Obie sprawdzone lokalnie na
`.NET SDK 10.0.400` — kod w [`code/`](code/) kompiluje się i uruchamia.

---

## 1️⃣ Extension members — rozszerzenia, które w końcu potrafią więcej

### Problem, który to rozwiązuje

Klasyczne extension methods (C# 3.0, 2007 rok) miały twardy limit: mogłeś dopisać
tylko **metody instancyjne**. Chciałeś dodać do `string` właściwość obliczaną w locie
(`IsPalindrome`, `IsStrongPassword`)? Nie dało się - musiałeś pisać
`password.IsStrongPassword()` z nawiasami, mimo że semantycznie to własność, nie
czynność. A dopisanie **statycznej** metody, która wygląda jakby była częścią samego
typu (`string.GenerateStrong(...)`, tak jak `string.Join(...)` jest częścią `string`)?
Zupełnie niemożliwe - musiała siedzieć w osobnej klasie narzędziowej.

### Co się zmieniło

C# 14 wprowadza blok `extension(Typ identyfikator) { ... }` wewnątrz `static class`.
W środku możesz definiować właściwości, indeksery i - to jest największa zmiana -
**statyczne members, które są wywoływane bezpośrednio na rozszerzanym typie**.

```csharp
public static class PasswordExtensions
{
    extension(string password)
    {
        // Właściwość - żadnych nawiasów przy wywołaniu.
        public bool IsStrongPassword =>
            password.Length >= 8
            && password.Any(char.IsUpper)
            && password.Any(char.IsDigit)
            && password.Any(c => !char.IsLetterOrDigit(c));

        // Statyczny member - wołany jako string.GenerateStrong(...), NIE
        // PasswordExtensions.GenerateStrong(...). To jest ta nowość.
        public static string GenerateStrong(int length) { /* ... */ }
    }
}
```

Wywołanie wygląda tak, jakby oba members od zawsze były częścią `System.String`:

```csharp
"Tr0ub4dor&3".IsStrongPassword   // true - jak zwykła właściwość
string.GenerateStrong(12)        // jak wbudowana metoda statyczna stringa
```

### Dlaczego to ważne w praktyce

To nie jest kosmetyka składniowa. Biblioteki, które dotąd musiały wybierać między
"naturalnym" API (ale wymagającym dziedziczenia albo modyfikacji cudzego typu) a
"brzydkim, ale możliwym" (statyczna klasa `XyzHelpers`), teraz mogą mieć naturalne API
bez żadnego kompromisu. To też krok w stronę tego, dokąd zmierza C# z **shapes/
role-based generics** w kolejnych wersjach - extension members to fundament pod
przyszłe, jeszcze mocniejsze mechanizmy rozszerzania typów.

**Pełny, uruchamialny przykład:** [`code/extension-members/`](code/extension-members/).

---

## 2️⃣ File-based apps — `dotnet run plik.cs` bez projektu

### Problem, który to rozwiązuje

Chcesz napisać 10-liniowy skrypt w C# - jednorazowy, do przetestowania pomysłu, do
automatyzacji czegoś na szybko. Do tej pory: `dotnet new console`, plik `.csproj`,
folder, `bin/`, `obj/`... dla dziesięciu linijek kodu. Realny koszt startowy odstraszał
od używania C# tam, gdzie normalnie sięgało się po bash albo Python.

### Co się zmieniło

.NET 10 SDK potrafi uruchomić **pojedynczy plik `.cs`** bezpośrednio, bez żadnego
projektu:

```bash
dotnet run hello.cs
```

Plik może zawierać zwykłe top-level statements (jak w każdym nowym projekcie konsolowym
od C# 9), a SDK sam, w locie, tworzy dla niego efemeryczny kontekst kompilacji. Można
nawet ściągać paczki NuGet bezpośrednio w pliku, dyrektywą `#:package`:

```csharp
#:package Humanizer@2.14.1

using Humanizer;

Console.WriteLine("dotnet_run_app".Humanize());
// -> "dotnet run app"
```

Na Linuksie/macOS plik taki można nawet zrobić wykonywalnym (`chmod +x`) z shebangiem
`#!/usr/bin/env dotnet run` na górze i odpalać jak zwykły skrypt.

### Dlaczego to ważne w praktyce

To realna konkurencja dla bash/Python w niszy "krótki skrypt automatyzujący coś w
homelabie/CI". Masz cały ekosystem .NET (typowanie, LINQ, async, NuGet) bez ceremonii
projektu. Gdy skrypt urośnie i będzie tego wymagał, `dotnet project convert` (nowość w
tym samym wydaniu SDK) przerabia plik na pełny projekt - więc nie ma efektu "teraz muszę
to przepisać od zera".

**Pełny, uruchamialny przykład:** [`code/file-based-app/`](code/file-based-app/).

---

## 📎 Jak uruchomić kod z tego wydania

Zobacz [`code/README.md`](code/README.md) — dokładne komendy dla obu przykładów.

---

<div align="center">

**Jutro:** Ansible od zera — pierwszy playbook, który naprawdę coś robi.

[← powrót do spisu wydań](../../README.md)

</div>
