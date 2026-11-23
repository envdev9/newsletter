---
paths:
  - "src/**/*Service.cs"
  - "src/**/Services/**/*.cs"
  - "src/**/Application/**/*.cs"
---

# Serwisy

<!-- Szablon. Dopasuj ścieżki i uzupełnij <...>. -->

Wzorzec: `src/<...>/<X>Service.cs`

- Serwis to jeden przypadek użycia lub spójna grupa (np. `OrderService`). Interfejs `I<X>Service` w tym samym projekcie.
- Zależności przez konstruktor (primary constructor), tylko interfejsy. Czas przez `TimeProvider`, nie `DateTime.UtcNow`.
- Tu jest logika biznesowa i sprawdzenie własności zasobu. Bez HTTP (`IActionResult`, `HttpContext`) i bez SQL.
- Wynik: <np. `Result<T>` z błędami domenowymi / wyjątki domenowe>. Nie zwracaj `null` jako błędu.
- Transakcja obejmująca kilka repozytoriów: <np. `IUnitOfWork` / transakcja przekazywana do repozytoriów>.
- Lifetime: <np. Scoped>.

## Testy serwisów

- Testy jednostkowe w `tests/<...>.UnitTests/<X>ServiceTests.cs`, przez publiczne metody serwisu.
- Repozytoria zastępuj <fake'ami w pamięci / NSubstitute>, ale nie mockuj wnętrza serwisu.
