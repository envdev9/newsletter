# Kod do wydania #12 — TUnit + `[AfterEvery(Assembly)]`/`[AfterEvery(Class)]` z DWOMA projektami testowymi

Pełny artykuł: [`../ARTICLE.md`](../ARTICLE.md). Poniżej ten sam kod + jak go odpalić.

Wymagania: **.NET 10 SDK** (`dotnet --version` → `10.x`). Podstawy TUnit: wydania #1–#5,
#7, #9 (w szczególności #4: `[AfterEvery(Test)]`; #7: `[AfterEvery(Assembly)]`; #9:
`[AfterEvery(Class)]`).

## Fragment prasówki, którego dotyczy ten kod

> W wydaniach #4, #7 i #9 poznaliśmy całą rodzinę `[AfterEvery]`: `Test` → `Class` →
> `Assembly`. Każde z tych wydań kończyło się jednak tą samą zastrzeżoną niepewnością: w
> repo był tylko **jeden** projekt testowy, więc pytanie "czy `[AfterEvery(Assembly)]`
> odpala się raz na assembly, czy raz na cały przebieg `dotnet test`" było czysto
> teoretyczne — przy jednym projekcie te dwie interpretacje dają identyczny wynik. Dziś to
> domykamy: solution z **dwoma** projektami testowymi (`Catalog.Tests`, `Shipping.Tests`),
> jeden `dotnet test` na poziomie solution, i realny pomiar PID procesu oraz liczników
> statycznych w każdym z nich.
>
> Wynik: `[AfterEvery(Assembly)]` odpala się RAZ NA PROJEKT (assembly), widząc wyłącznie
> testy tego projektu. Każdy projekt testowy to osobny proces systemowy
> (`Environment.ProcessId` różny), uruchamiany WSPÓŁBIEŻNIE z innymi projektami w tym
> samym `dotnet test`. Statyczny stan (nawet identycznie nazwana klasa `SharedState` w
> obu projektach) nigdy nie przecieka między nimi.

## Struktura projektu

```
TunitMultiProject.slnx              # solution: oba projekty testowe
global.json                         # "test": { "runner": "Microsoft.Testing.Platform" }

Catalog.Tests/                      # projekt testowy #1: 2 klasy, 5 testów
├── Catalog.Tests.csproj           # net10.0, TUnit 1.72.16
├── PricingCalculator.cs           # logika pod testem (VAT, rabat procentowy)
├── PricingTests.cs                # 3 testy
├── DiscountTests.cs               # 2 testy
├── SharedState.cs                 # statyczne liczniki -- TYLKO tego projektu
├── AssemblyHooks.cs               # [AfterEvery(Assembly)] -- PID, TestCount, licznik
├── ClassHooks.cs                  # [AfterEvery(Class)] -- raz na klasę (2x w tym projekcie)
└── .gitignore                     # bin/, obj/, TestResults/

Shipping.Tests/                     # projekt testowy #2: 1 klasa, 4 testy
├── Shipping.Tests.csproj          # net10.0, TUnit 1.72.16
├── ShippingCostCalculator.cs      # logika pod testem (stawka wg wagi)
├── ShippingCostTests.cs           # 4 testy
├── SharedState.cs                 # IDENTYCZNA nazwa/struktura jak w Catalog.Tests -- celowo
├── AssemblyHooks.cs
├── ClassHooks.cs                  # raz na klasę (1x w tym projekcie)
└── .gitignore
```

Dwa projekty są całkowicie niezależne (brak `ProjectReference` między nimi) — spaja je
wyłącznie `TunitMultiProject.slnx`.

## Jak odpalić od zera

```bash
cd code
dotnet test --output Detailed --results-directory /tmp/tunit-multi-results
```

Uruchamiaj z folderu `code/` (poziom solution) — SDK szuka `global.json` od bieżącego
katalogu, a `dotnet test` bez podanego projektu/solution operuje na pierwszym `.sln`
znalezionym w katalogu. `--results-directory` trzyma raporty HTML poza repo.

Żeby zobaczyć TYLKO jeden projekt (dla porównania z zachowaniem solution-wide):

```bash
cd code/Catalog.Tests
dotnet test --output Detailed
```

## Prawdziwy output (9/9, przebieg z tej maszyny — solution-wide, oba projekty naraz)

```
Running tests from .../Shipping.Tests.dll (net10.0|x64)
Running tests from .../Catalog.Tests.dll (net10.0|x64)
passed CostFor_1Kg_DajeNajnizszaStawke (32ms)
  from .../Shipping.Tests.dll (net10.0|x64)
passed CostFor_20Kg_DajeWyzszaStawke (40ms)
  from .../Shipping.Tests.dll (net10.0|x64)
passed CostFor_5Kg_DajeSrodkowaStawke (37ms)
  from .../Shipping.Tests.dll (net10.0|x64)
passed CostFor_PonadLimit_DajeNajwyzszaStawke (2ms)
  from .../Shipping.Tests.dll (net10.0|x64)
  Standard output
    === [Shipping.Tests] [AfterEvery(Class)] wywolanie #1: klasa ShippingCostTests ===
      Testow w klasie: 4 (passed=4)
    === [Shipping.Tests] [AfterEvery(Assembly)] wywolanie #1 ===
      PID procesu = 576540
      Testow w TEJ assembly: 4 (passed=4)
      SharedState.ShippingTestsSeen (static pole TYLKO tego projektu) = 1
passed ApplyDiscount_Z10Proc_Obniza (30ms)
  from .../Catalog.Tests.dll (net10.0|x64)
passed NetToGross_Z23ProcVat_LiczyPoprawnie (28ms)
  from .../Catalog.Tests.dll (net10.0|x64)
passed NetToGross_ZZerowymVat_ZwracaNetto (1ms)
  from .../Catalog.Tests.dll (net10.0|x64)
passed ApplyDiscount_Z100Proc_DajeZero (29ms)
  from .../Catalog.Tests.dll (net10.0|x64)
  Standard output
    === [Catalog.Tests] [AfterEvery(Class)] wywolanie #1: klasa DiscountTests ===
      Testow w klasie: 2 (passed=2)
passed NetToGross_ZUjemnymVat_RzucaWyjatek (47ms)
  from .../Catalog.Tests.dll (net10.0|x64)
  Standard output
    === [Catalog.Tests] [AfterEvery(Class)] wywolanie #2: klasa PricingTests ===
      Testow w klasie: 3 (passed=3)
    === [Catalog.Tests] [AfterEvery(Assembly)] wywolanie #1 ===
      PID procesu = 576541
      Testow w TEJ assembly: 5 (passed=5)
      SharedState.CatalogTestsSeen (static pole TYLKO tego projektu) = 2

.../Shipping.Tests.dll (net10.0|x64) passed (1s 176ms)
.../Catalog.Tests.dll (net10.0|x64) passed (1s 084ms)

Test run summary: Passed!
  .../Catalog.Tests.dll (net10.0|x64) passed (1s 084ms)
  .../Shipping.Tests.dll (net10.0|x64) passed (1s 176ms)

  total: 9
  failed: 0
  succeeded: 9
  skipped: 0
  duration: 1s 803ms
```

Zwróć uwagę na trzy rzeczy w tym logu:

1. **Dwa różne PID-y** (`576540`, `576541`) w tym samym przebiegu `dotnet test` — każdy
   projekt testowy to osobny proces systemowy.
2. **Przeplatający się output** (`Shipping.Tests` i `Catalog.Tests` miesza się w logu, a
   czasy trwania `1s 176ms`/`1s 084ms` pokrywają się) — `dotnet test` na poziomie
   solution uruchamia projekty testowe WSPÓŁBIEŻNIE, nie po kolei.
3. **`TestCount` w każdym `[AfterEvery(Assembly)]` ogranicza się do WŁASNEGO projektu**
   (4 w `Shipping.Tests`, 5 w `Catalog.Tests` — nigdy 9).

Powtórzone trzykrotnie (`dotnet test` uruchomiony osobno za każdym razem) — za każdym
razem **9/9**, ten sam wzorzec wywołań hooków (`Assembly` 1×/projekt, `Class` 2× w
`Catalog.Tests` i 1× w `Shipping.Tests`), zmieniały się tylko same wartości PID (bo to
nowe procesy przy każdym wywołaniu) — nigdy flakowania.

## Dlaczego dwie identyczne klasy `SharedState`

`Catalog.Tests/SharedState.cs` i `Shipping.Tests/SharedState.cs` mają tę samą nazwę,
strukturę i logikę — to świadomy eksperyment kontrolny. Po przebiegu
`SharedState.CatalogTestsSeen` (tylko w `Catalog.Tests`) = `2`, a
`SharedState.ShippingTestsSeen` (tylko w `Shipping.Tests`) = `1` — każdy liczony od zera,
niezależnie, bez wzajemnego wpływu. To, że kompilacja nawet nie zgłasza konfliktu nazw,
potwierdza niezależnie to samo, co PID-y w sekcji wyżej: to dwie całkowicie osobne
assembly w dwóch osobnych procesach, nie dwa typy w jednej przestrzeni nazw.

## Nie zweryfikowano

Zachowanie przy 3+ projektach testowych w jednym solution (tu: tylko dwa), projekty
testowe z `ProjectReference` między sobą (tu: całkowicie niezależne), Aspire + TUnit
(`DistributedApplicationTestingBuilder` — osobne wydanie rubryki Aspire dzisiaj),
odświeżanie tokenu JWT / `RS256` (temat z wydania #9, nadal otwarty, niezwiązany z tym
wydaniem).
