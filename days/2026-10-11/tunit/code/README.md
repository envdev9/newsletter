# Kod do wydania #18 — TUnit: kiedy zapada decyzja o pominięciu testu i jak to widać w raporcie

Pełny artykuł: [`../ARTICLE.md`](../ARTICLE.md).

Wymagania: **.NET 10 SDK** (sprawdzone na `10.0.400`), dostęp do NuGet. Pakiet: `TUnit 1.73.19`.

## Fragment prasówki, którego dotyczy ten kod

> Decyzja `SkipAttribute.ShouldSkip` zapada przy rejestracji testu, przed wykonaniem jakiegokolwiek ciała
> testu (zmierzone dziennikiem numerowanych zdarzeń). `Skip.Test` w ciele pomija dopiero po wykonaniu
> kodu poprzedzającego wywołanie. `[Explicit]` nie wchodzi do `total`. Powód pominięcia trafia do
> wyjścia pod nazwą testu.

## Struktura

```
global.json                           # "test": { "runner": "Microsoft.Testing.Platform" } -- WYMAGANE dla `dotnet test`
SkipLab.slnx
SkipLab/Probes.cs                     # Slugifier, FsProbe, DbSettings
SkipLab.Tests/EnvironmentSkips.cs     # Trace + [RequiresEnvVar], [LinuxOnly] : SkipAttribute
SkipLab.Tests/SkipTests.cs            # po jednym tescie na kazdy sposob pomijania (+ [Explicit])
SkipLab.Tests/PropertyAndOrderTests.cs# [Property] + test zrzucajacy dziennik kolejnosci
```

## Jak odpalić od zera (zweryfikowane)

```bash
dotnet run --project SkipLab.Tests/SkipLab.Tests.csproj -- --output Detailed
```

Uruchamiane z katalogu `code/` (zweryfikowano z podaniem ścieżki bezwzględnej do projektu). Faktyczny
wynik na tym kodzie: `total: 9, failed: 0, succeeded: 6, skipped: 3`.

## Do samodzielnego sprawdzenia (NIE uruchomione przez autora)

```bash
# 1. zmienna ustawiona -> Wymaga_zmiennej_srodowiskowej powinien przejsc
SKIPLAB_DB=demo dotnet run --project SkipLab.Tests/SkipLab.Tests.csproj -- --output Detailed

# 2. [Explicit] tylko na zadanie (filtr treenode)
dotnet run --project SkipLab.Tests/SkipLab.Tests.csproj -- --treenode-filter "/*/*/SkipTests/Droga_operacja_tylko_na_zadanie"

# 3. filtr po [Property]
dotnet run --project SkipLab.Tests/SkipLab.Tests.csproj -- --treenode-filter "/*/*/*/*[Kind=Unit]"

# 4. klasyczne dotnet test (global.json musi byc w biezacym katalogu lub wyzej)
dotnet test --solution SkipLab.slnx
```

Uwaga: `dotnet test --solution ...` uruchomione z katalogu, nad którym nie ma `global.json`, kończy się
`MSB1001: Unknown switch` (SDK w trybie VSTest) — to zmierzone.

## Nie zweryfikowano

Punkty 1–4 powyżej; kod wyjścia dla przebiegu, w którym wszystko jest pominięte; zachowanie
`ShouldSkip` przy `[Repeat]`/`[Retry]`/`[Arguments]`.

Artefakty: po budowie powstają `bin/` i `obj/` (wykluczone przez `.gitignore`); przebieg wypisuje też
`*-report.html` w `bin/Debug/net10.0/TestResults/`.
