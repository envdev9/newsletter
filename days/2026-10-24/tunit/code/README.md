# Kod do wydania #29 — TUnit: własne źródło danych z CSV i `[ClassConstructor]` z DI

Pełny artykuł: [`../ARTICLE.md`](../ARTICLE.md).

Wymagania: **.NET 10 SDK** (sprawdzone na `10.0.400`), dostęp do NuGet. Pakiety: `TUnit 1.76.0`,
`Microsoft.Extensions.DependencyInjection 10.0.0`.

## Fragment prasówki, którego dotyczy ten kod

> `DataSourceGeneratorAttribute<decimal, string, decimal>` czyta `cases.csv` i zamienia każdy wiersz w osobny test
> (8 wierszy = 8 testów; `GenerateDataSources` wywołane raz na przebieg). W `[DisplayName]` wartości podstawia
> się przez `$nazwaParametru` (`{0}` zostaje dosłowne). `[ClassConstructor<DiClassConstructor>]` + `ITestEndEventReceiver`
> daje każdej instancji klasy testowej własny scope DI i zwalnia go po teście: 10 testów, `created=10 disposed=10`,
> także przy porażce. Błędny wiersz CSV daje porażkę z nazwą dokładnie tego wiersza (kod wyjścia 2).

## Struktura

```
global.json                           # "test": { "runner": "Microsoft.Testing.Platform" }
DataLab.slnx
DataLab.Core/Pricing.cs               # PricingService, IDiscountPolicy, RequestScopeMarker (scoped), Composition
DataLab.Tests/CsvDataSource.cs        # CsvCasesAttribute : DataSourceGeneratorAttribute<decimal,string,decimal>
DataLab.Tests/DiClassConstructor.cs   # IClassConstructor + ITestEndEventReceiver
DataLab.Tests/PricingTests.cs         # testy (CSV, wyjątek, scope per test) + [After(Class)] z raportem
DataLab.Tests/cases.csv               # tabela przypadków
```

## Jak odpalić od zera (zweryfikowane `dotnet run`)

Z korzenia repo:

```bash
dotnet run --project days/2026-10-24/tunit/code/DataLab.Tests/DataLab.Tests.csproj -- --output Detailed
```

(lub z katalogu `code/`: `dotnet run --project DataLab.Tests/DataLab.Tests.csproj -- --output Detailed`).

## Prawdziwy output (jeden z kilku przebiegów; kolejność testów jest niedeterministyczna)

```text
scope-marker-id=9 created-w-chwili-testu=10 disposed-w-chwili-testu=8
passed Total(net=100.00, tier=none) = 100.00 (24ms)
passed Total(net=100.00, tier=silver) = 95.00 (23ms)
passed Total(net=100.00, tier=gold) = 90.00 (38ms)
passed Total(net=500.00, tier=none) = 480.00 (38ms)
passed Total(net=499.99, tier=gold) = 449.99 (23ms)
passed Total(net=1000.00, tier=gold) = 880.00 (23ms)
passed Total(net=100.00, tier=platinum) = 85.00 (26ms)
passed Total(net=500.00, tier=platinum) = 405.00 (24ms)
passed Nieznany_poziom_rzuca (29ms)
RAPORT created=10 disposed=10 generateCalls=1
passed Kazdy_test_ma_swoj_scope (29ms)

Test run summary: Passed!
  total: 10
  failed: 0
  succeeded: 10
  skipped: 0
```

Eksperyment z porażką: zmień w `cases.csv` `500.00,none,480.00` na `500.00,none,481.00` i uruchom ponownie:
`failed Total(net=500.00, tier=none) = 481.00` — `Expected to be 481.00 but found 480.00`, `failed: 1, succeeded: 9`, kod wyjścia 2.

## Niezweryfikowane

- `dotnet test --project ...` — w środowisku autora dało `MSB1001` (`global.json` nie był widoczny z bieżącego katalogu);
  z katalogu `code/` powinno działać, ale nie zostało uruchomione.
- Filtry z `*` w `--treenode-filter` (środowisko autora odrzuciło polecenie).
- Czy instancje klas testowych powstają leniwie, czy przed startem pierwszego testu.
- `bin/`, `obj/` i `TestResults/` zostają po buildzie (są w `.gitignore` tego katalogu).
