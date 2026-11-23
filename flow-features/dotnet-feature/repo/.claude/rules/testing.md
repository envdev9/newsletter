---
paths:
  - "tests/**/*.cs"
---

# Testy w tym repo

<!-- Szablon. Ogólne zasady testów są w ~/.claude/rules/dotnet.md i dotnet-data.md. Uzupełnij <...>. -->

Wzorce: `tests/<...>/<X>ServiceTests.cs` (jednostkowy), `tests/<...>/<X>RepositoryTests.cs` (integracyjny).

- Framework: <xUnit>, asercje: <FluentAssertions / Shouldly / Assert>, mocki: <NSubstitute / fake'i>.
- Nazwy: `<Metoda>_<Warunek>_<Oczekiwany wynik>` <albo zdanie opisujące zachowanie>.
- Fixture bazy: <klasa, np. `PostgresFixture`>, connection string z `ConnectionStrings__TestDb`.
- Dane testowe: <buildery w `tests/<...>/Builders/`>.
- Założenia z designu: `[Trait("Assumption", "A1")]`; czekające na decyzję: `[Fact(Skip = "czeka na decyzję A2")]`.
- Testy jednego założenia: `dotnet test --filter "Assumption=A1"`. Lista wszystkich: `grep -rn 'Trait("Assumption"' tests/`.
