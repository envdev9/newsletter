---
description: Generuje kompletny plik testów jednostkowych (xUnit) dla wskazanej klasy C#
argument-hint: "[ścieżka-do-pliku.cs]"
allowed-tools: Read, Write, Glob, Bash(dotnet build:*), Bash(dotnet test:*)
---

Wygeneruj kompletny plik testów jednostkowych xUnit dla klasy C# wskazanej w $ARGUMENTS.

Wykonaj po kolei:

1. Odczytaj plik $ARGUMENTS (narzędziem Read) i zidentyfikuj:
   - publiczne konstruktory i ich zależności (interfejsy do zamockowania),
   - publiczne metody/właściwości do przetestowania,
   - rzucane wyjątki i warunki brzegowe widoczne w kodzie (np. `ArgumentNullException`,
     walidacje, wczesne `return`).
2. Znajdź projekt testowy powiązany z projektem źródłowym (Glob po `**/*.Tests.csproj`
   albo `**/*Tests.csproj` w repo) - jeśli go nie ma, zapytaj mnie zanim cokolwiek
   utworzysz.
3. Utwórz plik `<NazwaKlasy>Tests.cs` w projekcie testowym, w ścieżce lustrzanej do
   ścieżki klasy źródłowej (np. `Services/OrderService.cs` -> `Services/OrderServiceTests.cs`).
4. Testy pisz w konwencji Arrange-Act-Assert, nazwy metod w formacie
   `MetodaTestowana_Scenariusz_OczekiwanyEfekt`. Pokryj: happy path, przynajmniej jeden
   warunek brzegowy per publiczna metoda, i każdy jawnie rzucany wyjątek.
5. Zależności mockuj przez interfejsy konstruktora (NSubstitute, jeśli projekt już go
   używa - sprawdź istniejące testy w tym samym projekcie, żeby nie mieszać bibliotek
   mockujących w jednym projekcie).
6. Po wygenerowaniu pliku uruchom `dotnet build` na projekcie testowym, a potem
   `dotnet test --filter "FullyQualifiedName~<NazwaKlasy>Tests"`. Jeśli coś nie
   kompiluje się albo test nie przechodzi - popraw i uruchom ponownie, maksymalnie
   3 próby.
7. Na koniec pokaż krótkie podsumowanie: ile testów, co pokrywają, wynik `dotnet test`.

Nie zgaduj zachowania zależności, których nie widzisz w kodzie - jeśli sygnatura
interfejsu nie mówi wystarczająco, zapytaj zamiast zakładać.
