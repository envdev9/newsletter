---
paths:
  - "**/*.cs"
  - "**/*.csproj"
  - "**/*.sln"
  - "**/*.slnx"
---

# Zasady .NET (ogólne)

Obowiązują każdego, kto pisze kod C#: główną sesję i agenta `dotnet-developer`.
Zasady konkretnego repo (`CLAUDE.md` i `.claude/rules/` w repo) mają pierwszeństwo przed tym plikiem.

Pliki uzupełniające (czytaj, gdy zadanie dotyczy):
- `~/.claude/rules/dotnet-data.md`: Dapper, PostgreSQL, SqlDeployer, testy integracyjne na bazie,
- `~/.claude/rules/dotnet-cloud.md`: API, Kubernetes, Aspire, CI (TeamCity).

## Zasady pracy

- Zanim napiszesz kod, przeczytaj sąsiedni kod i dopasuj się do istniejących konwencji (nazewnictwo, struktura folderów, styl DI, obsługa błędów). Nie wprowadzaj nowych wzorców, jeśli repo ma już swój.
- Polecenie użytkownika lub zatwierdzony design wygrywa ze wzorcem z kodu. Jeśli kod robi coś inaczej niż polecenie (np. polecenie: `UPDATE`, a w repo jest delete + insert), zrób według polecenia i zgłoś rozbieżność.
- Rób tylko to, co jest w zadaniu. Nie refaktoryzuj niezwiązanego kodu i nie dodawaj funkcji "na zapas".
- TDD: najpierw test, który się wywala z właściwego powodu, potem minimalny kod, potem uruchomienie testów. Nie raportuj "działa" bez wyniku `dotnet test`. Testów nie odkładaj na koniec, także przy niepełnych wymaganiach.
- Jeśli design jest sprzeczny z kodem albo czegoś brakuje, zatrzymaj się i zgłoś to zamiast zgadywać.
- Nie rób commita, pusha ani zmian na bazie innej niż lokalna/testowa bez wyraźnej zgody użytkownika.

## Niejasne wymagania

- Nie zgaduj po cichu. Niejasny punkt to: **pytanie** (blokuje, potrzebna odpowiedź), **założenie** (A1, A2…: „zakładam X, bo Y”, wymaga akceptacji) albo **spike** (wyrzucany prototyp bez testów, potem właściwa wersja w TDD).
- Test oparty na założeniu: `[Trait("Assumption", "A1")]`.
- Funkcja czekająca na decyzję: `[Fact(Skip = "czeka na decyzję A2")]` zamiast zgadywanej implementacji.
- Testy przez publiczne API, bez mockowania wnętrza, żeby zmiana wymagania zmieniała mało testów.

## Standardy C# / .NET

- Włączone nullable reference types. Nie wyciszaj ostrzeżeń przez `!`, chyba że masz uzasadnienie w komentarzu.
- `async`/`await` do końca, bez `.Result` i `.Wait()`. Metody asynchroniczne przyjmują i propagują `CancellationToken`. Nie używaj `async void` poza handlerami zdarzeń. Zamiast `Thread.Sleep` w pętli: `await Task.Delay(..., ct)` lub `PeriodicTimer`.
- Wstrzykiwanie zależności przez konstruktor. Zależności przez interfejsy tam, gdzie to ułatwia testy (także `Console`, czas: `TimeProvider`, system plików). Zwracaj uwagę na lifetime (Scoped nie trafia do Singletona).
- Konfiguracja przez `IOptions<T>` z walidacją przy starcie. Sekrety nigdy w kodzie ani w `appsettings.json`.
- Logowanie przez `ILogger<T>` z szablonami (`"Order {OrderId} cancelled"`), bez interpolacji stringów i bez danych wrażliwych.
- DTO na granicy (rekordy), encje domenowe nie wychodzą na zewnątrz. Walidacja wejścia na granicy.
- Błędy: konkretne wyjątki lub wynik z błędem; na granicy API spójne `ProblemDetails`. Nie łap `Exception` bez powodu i nie połykaj wyjątków.
- Krótkie metody, jedna odpowiedzialność, czytelne nazwy. Komentarze tylko tam, gdzie wyjaśniają "dlaczego".

## Testy (ogólne)

- xUnit (lub framework używany w repo). Nazwy opisują zachowanie, układ Arrange-Act-Assert, jeden powód porażki na test.
- Logika biznesowa: testy jednostkowe. Integracje z bazą: patrz `dotnet-data.md`.
- Testuj ścieżki błędów i przypadki brzegowe, nie tylko happy path. Testy niezależne od kolejności i od czasu systemowego (`TimeProvider`/`FakeTimeProvider`).

## Weryfikacja

- `dotnet build` bez nowych ostrzeżeń i `dotnet test` na zielono, z prawdziwym outputem.
- Smoke test aplikacji, gdy to możliwe (`dotnet run` / `docker run` ze scenariuszem). Konsola interaktywna: `script -qec "<cmd>" /dev/null` z wejściem z `printf`. Łapie TTY, kodowanie znaków, sygnały i prawa do plików, czego nie łapią testy jednostkowe.

## Checklista self-review

Przejdź po diffie i odpowiedz sobie na każdy punkt:

- [ ] Zrobione dokładnie to, co w poleceniu/designie (np. `UPDATE`, a nie delete + insert)? Nic ponad zakres?
- [ ] Konwencje repo zachowane (`CLAUDE.md`, `.claude/rules/`, pliki wzorcowe)?
- [ ] Testy napisane przed kodem, pokrywają ścieżki błędów i brzegowe, założenia oznaczone?
- [ ] Brak ukrytych założeń spoza listy z designu?
- [ ] async do końca, `CancellationToken` przekazany, brak `.Result`/`Thread.Sleep`?
- [ ] DI zamiast statycznych zależności, poprawne lifetime?
- [ ] Brak `catch (Exception)` bez powodu, brak połykania wyjątków?
- [ ] Brak sekretów i danych wrażliwych w kodzie i logach?
- [ ] Nullable bez nowych ostrzeżeń i bez nieuzasadnionego `!`?
- [ ] Build, testy i smoke test uruchomione, output sprawdzony?
