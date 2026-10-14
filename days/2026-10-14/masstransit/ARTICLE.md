<div align="center">

# 📰 TECH PRASÓWKA
### Wydanie #21 — 14 października 2026

![MassTransit](https://img.shields.io/badge/MassTransit-FF6600?style=for-the-badge)
![Poziom](https://img.shields.io/badge/poziom-zaawansowany-red?style=for-the-badge)
![Status](https://img.shields.io/badge/uruchomienie-NIEZWERYFIKOWANE-yellow?style=for-the-badge)

## 📨 Trwała saga w EF Core: stan w bazie, restart procesu i wyścig dwóch eventów

</div>

---

> **Uczciwie na wstępie.** Kod z tego wydania **kompiluje się** (`dotnet build`: 0 errors,
> MassTransit 8.5.10, .NET SDK 10.0.400), ale **scenariusze uruchomieniowe (restart procesu,
> wyścig, pesymistyczna współbieżność) nie zostały uruchomione**: po pierwszym przebiegu sesja
> odrzuciła kolejne `dotnet <dll>`. Poniżej opisuję tylko to, co faktycznie widziałem, a
> resztę oznaczam jako hipotezę do sprawdzenia przez Ciebie.

## 🎯 Dlaczego to ważne

Saga z #3 trzymała stan w pamięci procesu: restart = zapomniane zamówienia. Repozytorium EF
Core zapisuje stan sagi jako wiersz w tabeli, więc nowy proces może podjąć sagę tam, gdzie
poprzedni skończył. Cena: jak tylko dwa eventy trafiają w tę samą sagę równolegle, musisz
zdecydować, co z konfliktem (optymistycznie albo pesymistycznie).

## 🧩 1. Co jest w projekcie (zweryfikowane: kompiluje się)

- `OrderState : SagaStateMachineInstance, ISagaVersion` - wiersz sagi z kolumną `Version`
  (token współbieżności, `IsConcurrencyToken()`), licznik `EventsApplied` i ślad `Trail`.
- `OrderDbContext : SagaDbContext` + `SagaClassMap<OrderState>` (przestrzeń nazw
  `MassTransit.EntityFrameworkCoreIntegration`).
- `AddSagaStateMachine<,>().EntityFrameworkRepository(r => { r.ConcurrencyMode = ...; r.ExistingDbContext<OrderDbContext>(); })`
  na SQLite (plik), transport in-memory. Restart = nowy proces z nową szyną in-memory i tą
  samą bazą; wiadomości nie są trwałe, trwały jest tylko stan sagi.
- Tryby: `submit`, `pay` (osobny proces), `race <optimistic|pessimistic> <retry|noretry>`, `show`.

## 🪤 2. Haczyk zmierzony: typy wiadomości w globalnej przestrzeni nazw

Pierwsze uruchomienie (jedyne, które wykonałem) padło przy starcie hosta:

```
System.ArgumentException: Messages types must have a valid namespace: OrderSubmitted (Parameter 'T')
   at MassTransit.Topology.SendTopology.GetMessageTopology[T]()
```

`record OrderSubmitted(...)` bez `namespace` (a więc w przestrzeni globalnej, co przy
top-level statements wygląda niewinnie) jest odrzucane przez topologię MassTransit - błąd
pojawia się dopiero przy rejestracji korelacji maszyny stanów. Poprawka: `namespace EfSagaDemo;`.
Po poprawce projekt się buduje; dalszych uruchomień nie wykonałem.

## 🚧 3. Co NIE zostało zweryfikowane (nie traktuj jako faktów)

- Że nowy proces rzeczywiście wznawia sagę z wiersza w bazie (`submit` potem `pay`).
- Zachowanie wyścigu `PaymentReceived` + `ItemPacked`: oczekuję (hipoteza), że przy
  `Optimistic` jeden event trafi na konflikt wersji (`DbUpdateConcurrencyException` w
  `Fault<T>`), a z `UseMessageRetry` zostanie ponowiony - `FaultPrinter<T>` ma to wypisać.
- Czy `ConcurrencyMode.Pessimistic` działa na SQLite: MassTransit używa blokad wierszy w SQL
  zależnych od dostawcy (SQL Server/PostgreSQL); SQLite ich nie ma, więc spodziewam się
  problemu - **niesprawdzone**, więc nie zakładaj.
- Ostrzeżenie `NU1903` (podatność w transitive `SQLitePCLRaw.lib.e_sqlite3` 2.1.10) - widoczne
  przy buildzie; nie badałem, czy nowsza wersja pakietu je usuwa.

## ▶️ Następny krok

Uruchom scenariusze z [`code/README.md`](code/README.md) i porównaj z hipotezami powyżej.
Następny poziom: wynik tych pomiarów, potem PostgreSQL z `UsePostgresLockStatements`
(do sprawdzenia) i prawdziwy pesymistyczny lock.

---

<div align="center">

[← wróć do wydania #21 (wszystkie rubryki)](../README.md) · [spis wydań](../../../README.md)

</div>
