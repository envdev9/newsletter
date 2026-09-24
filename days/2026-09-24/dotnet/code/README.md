# Kod do wydania #1 — Extension members i file-based apps (.NET 10)

Pełny artykuł: [`../ARTICLE.md`](../ARTICLE.md). Poniżej ten sam kod + jak go odpalić.

Wymagania: **.NET 10 SDK** (`dotnet --version` → `10.x`).

## Fragment prasówki, którego dotyczy ten kod

> C# 14 wprowadza blok `extension(Typ identyfikator) { ... }` wewnątrz `static class`.
> W środku możesz definiować właściwości, indeksery i statyczne members, które są
> wywoływane bezpośrednio na rozszerzanym typie - `string.GenerateStrong(...)` działa
> tak, jakby od zawsze było metodą wbudowaną w `System.String`.
>
> .NET 10 SDK potrafi uruchomić pojedynczy plik `.cs` bezpośrednio, bez żadnego
> projektu (`dotnet run plik.cs`), łącznie z pobieraniem paczek NuGet przez dyrektywę
> `#:package` na górze pliku.

## 1. Extension members

```bash
cd extension-members
dotnet run
```

Oczekiwany wynik (fragment):

```
haslo123         -> za słabe
Tr0ub4dor&3      -> OK
abc              -> za słabe
K0min1arz!2026   -> OK

Wygenerowane hasło: <losowe 12 znaków>
Czy przechodzi własną walidację? True
```

## 2. File-based apps

Bez `.csproj` — plik uruchamiany bezpośrednio:

```bash
cd file-based-app
dotnet run hello.cs Mag
```

Wynik:

```
Cześć, Mag!
To działa bez żadnego .csproj - uruchomione o <godzina>.
Argumentów przekazanych z linii poleceń: 1
```

Bonus — file-based app z paczką NuGet ściąganą w locie (`#:package`):

```bash
dotnet run pkg-demo.cs
```

Wynik:

```
dotnet_run_app -> dotnet run app
extension_members_in_csharp_14 -> extension members in csharp 14
no_more_csproj -> no more csproj
```

Oba przykłady sprawdzone lokalnie na `.NET SDK 10.0.400` przed publikacją.
