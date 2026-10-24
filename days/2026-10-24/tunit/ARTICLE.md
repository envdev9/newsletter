<div align="center">

# 📰 TECH PRASÓWKA
### Wydanie #29 — 24 października 2026

![TUnit](https://img.shields.io/badge/TUnit-2EA44F?style=for-the-badge)
![Poziom](https://img.shields.io/badge/poziom-zaawansowany-D9534F?style=for-the-badge)
![Status](https://img.shields.io/badge/przebieg-zweryfikowany-2EA44F?style=for-the-badge)

## TUnit: własne źródło danych z pliku CSV i własny konstruktor klas testowych z DI

</div>

---

> 📌 **Dlaczego to ważne.** Do tej pory dane do testów brały się z `[Arguments]`, `[MethodDataSource]` i fixture'ów,
> a klasy testowe tworzył sam TUnit przez konstruktor bez parametrów. Prawdziwe projekty chcą dwóch rzeczy:
> (1) tabeli przypadków trzymanej w pliku, który może edytować analityk, i (2) testów, którym kontener DI poda
> serwis przez konstruktor, ze scope'em sprzątanym po każdym teście. Obie rzeczy to rozszerzenia, które
> piszesz raz, a potem używasz jednym atrybutem.

Środowisko: TUnit **1.76.0** (nowsza niż 1.75.0 z #25), .NET SDK 10.0.400, `dotnet run --project ... -- <opcje>`.
Kod: [`code/`](code/) — `DataLab.Core` (cennik z rabatami + DI) i `DataLab.Tests`.

## 🔎 Co zmierzone, a co nie

| 🧩 Fakt | 🏷️ Status |
|---|---|
| `DataSourceGeneratorAttribute<T1,T2,T3>` czytający `cases.csv`: 8 wierszy = 8 osobnych testów | ✔️ zmierzone |
| `GenerateDataSources` wywołane raz na całe odkrywanie testów (`generateCalls=1`) | ✔️ zmierzone |
| `[DisplayName("... $net ... $tier")]` podstawia wartości z wygenerowanych danych; `{0}` nie | ✔️ zmierzone |
| `[ClassConstructor<T>]` + `ITestEndEventReceiver`: 10 testów = 10 scope'ów, 10 zwolnionych, także gdy test pada | ✔️ zmierzone |
| Błędny wiersz CSV: porażka wskazuje dokładnie ten wiersz, kod wyjścia 2 | ✔️ zmierzone |
| Filtr `--treenode-filter` z `*` | ❌ środowisko odrzuciło polecenie (trzeci raz) |
| `dotnet test --project` | ❌ `MSB1001` w tym środowisku (patrz niżej) |

## 1. 📄 Własne źródło danych: tabela przypadków w CSV

`DataSourceGeneratorAttribute<...>` to klasa bazowa, po której dziedziczysz, żeby napisać własny atrybut danych.
Liczba parametrów generyczna odpowiada parametrom metody testowej. Nasz atrybut czyta plik leżący obok binarki:

```csharp
[AttributeUsage(AttributeTargets.Method)]
public sealed class CsvCasesAttribute(string file) : DataSourceGeneratorAttribute<decimal, string, decimal>
{
    protected override IEnumerable<Func<(decimal, string, decimal)>> GenerateDataSources(DataGeneratorMetadata metadata)
    {
        var path = Path.Combine(AppContext.BaseDirectory, file);
        foreach (var line in File.ReadLines(path).Skip(1).Where(l => !string.IsNullOrWhiteSpace(l)))
        {
            var p = line.Split(',');
            var row = (decimal.Parse(p[0], CultureInfo.InvariantCulture), p[1], decimal.Parse(p[2], CultureInfo.InvariantCulture));
            yield return () => row;
        }
    }
}
```

Użycie to jeden atrybut:

```csharp
[Test]
[CsvCases("cases.csv")]
[DisplayName("Total(net=$net, tier=$tier) = $expected")]
public async Task Total_zgodny_z_tabela(decimal net, string tier, decimal expected)
    => await Assert.That(pricing.Total(net, tier)).IsEqualTo(expected);
```

Plik `cases.csv` trafia do katalogu wyjściowego przez `<None Update="cases.csv" CopyToOutputDirectory="PreserveNewest" />`.
Prawdziwy output (kolejność testów między przebiegami się zmienia, bo biegną równolegle):

```text
passed Total(net=100.00, tier=silver) = 95.00 (23ms)
passed Total(net=500.00, tier=none) = 480.00 (38ms)
passed Total(net=499.99, tier=gold) = 449.99 (23ms)
passed Total(net=1000.00, tier=gold) = 880.00 (23ms)
...
  total: 10    succeeded: 10    failed: 0
```

Wiersze `500.00` i `499.99` w pliku to celowe wartości graniczne progu rabatu kwotowego (od 500 zł odejmujemy 20 zł).

> 🎯 **Haczyk 1: nazwa testu.** Z `[DisplayName("Total(net={0}, ...)")]` wyszło dosłowne `{0}` w wynikach (pierwszy
> przebieg, osiem identycznych linii — nie do rozróżnienia). Dopiero `$net`, `$tier`, `$expected` — nazwy
> **parametrów metody** — podstawiły wartości. Przy zielonym przebiegu to kosmetyka, ale przy czerwonym nazwa to
> jedyna informacja, który wiersz tabeli zawiódł.

Dowód, że to działa przy porażce: zmieniłem w CSV oczekiwaną wartość `500.00,none,480.00` na `481.00`:

```text
failed Total(net=500.00, tier=none) = 481.00 (126ms)
  TUnit.Engine.Exceptions.TestFailedException: [Test Failure] AssertionException: Expected to be 481.00
  but found 480.00
  at Assert.That(pricing.Total(net, tier)).IsEqualTo(expected)
...
  total: 10   failed: 1   succeeded: 9        (kod wyjścia 2)
```

Nie ma tu pomyłki, który wiersz poległ, i nie ma ręcznej pętli w teście, która przy pierwszym błędzie ukryłaby resztę.
(Plik przywróciłem do poprawnej wartości; w `code/` jest wersja zielona.)

> 🎯 **Haczyk 2: kiedy czytany jest plik.** `GenerateDataSources` zostało wywołane **raz** na przebieg
> (licznik `generateCalls=1`), więc zmiana CSV w katalogu wyjściowym działa przy następnym starcie procesu,
> nie w trakcie. W IDE/ w trybie obserwacji, który nie odkrywa testów ponownie, możesz tego nie zobaczyć — tego nie sprawdzałem.

## 2. 💉 `[ClassConstructor<T>]`: DI w konstruktorze klasy testowej

Domyślnie TUnit tworzy klasę testową sam. Jeśli konstruktor ma parametry, które nie pochodzą z `[ClassDataSource]`,
potrzebny jest własny konstruktor. Implementujesz `IClassConstructor`, a kontener DI robi resztę:

```csharp
public sealed class DiClassConstructor : IClassConstructor, ITestEndEventReceiver
{
    private static readonly ServiceProvider Root = Composition.Build();
    private static readonly Dictionary<object, IServiceScope> Scopes = new(ReferenceEqualityComparer.Instance);

    public Task<object> Create(Type type, ClassConstructorMetadata classConstructorMetadata)
    {
        var scope = Root.CreateScope();
        var instance = ActivatorUtilities.CreateInstance(scope.ServiceProvider, type);
        lock (Scopes) Scopes[instance] = scope;
        return Task.FromResult(instance);
    }

    public ValueTask OnTestEnd(TestContext context)
    {
        var instance = context.Metadata.TestDetails.ClassInstance;
        IServiceScope? scope;
        lock (Scopes) { Scopes.Remove(instance, out scope); }
        scope?.Dispose();
        return ValueTask.CompletedTask;
    }

    public int Order => 0;
}
```

Klasa testowa deklaruje swoje zależności jak zwykły serwis:

```csharp
[ClassConstructor<DiClassConstructor>]
public class PricingTests(PricingService pricing, RequestScopeMarker marker) { ... }
```

`RequestScopeMarker` to serwis `Scoped` z licznikami utworzeń i zwolnień (w `DataLab.Core`), a kontener budowany jest
z `ValidateScopes = true` i `ValidateOnBuild = true`. Wynik: **10 testów, 10 scope'ów, 10 zwolnień**:

```text
RAPORT created=10 disposed=10 generateCalls=1
```

TUnit tworzy nową instancję klasy dla każdego testu, więc `[ClassConstructor]` jest wołany dla każdej z nich — i tu
cenny jest `ITestEndEventReceiver`: pozwala zwolnić scope **po** teście. W przebiegu z celową porażką liczby
też wyszły `created=10 disposed=10`, czyli scope sprzątany jest także, gdy test pada.

Dodatkowa obserwacja: test `Kazdy_test_ma_swoj_scope` drukował liczniki w chwili wykonania, np.
`created=10 disposed=8` (równolegle) — czyli w momencie, gdy ten test biegł, część poprzednich już zwolniła scope.
Przy kolejnych przebiegach liczby się zmieniały (`id=9`/`id=10`), bo kolejność jest niedeterministyczna.

> 🎯 **Haczyk 3: stan statyczny.** Mapa `Scopes` jest statyczna i współdzielona przez wszystkie równoległe testy,
> więc `lock` jest obowiązkowy. Bez własnej mapy instancja → scope nie masz jak powiązać `OnTestEnd` ze scope'em,
> bo `IClassConstructor` zwraca tylko obiekt. To kształt, który zadziałał u mnie; nie twierdzę, że to jedyny sposób.

## ⚠️ Czego nie udało się zweryfikować

- **`dotnet test --project ...`** dało `MSB1001 Unknown switch --project`: `global.json` z runnerem
  Microsoft.Testing.Platform leży w `code/`, a polecenie szuka go od bieżącego katalogu, w którym pracuję (nie
  mogłem do niego wejść). Wszystkie przebiegi to `dotnet run --project`. Z katalogu `code/` `dotnet test` powinno
  działać, ale **tego nie widziałem**.
- **Filtr `--treenode-filter` z `*`** — trzeci raz środowisko odrzuciło polecenie; nie próbowałem obejść.
- Nie sprawdzałem, czy TUnit tworzy instancje klas (a więc woła `Create`) leniwie czy wszystkie przed startem —
  liczniki, które widziałem, nie rozstrzygają tego.
- Źródła danych asynchroniczne (`AsyncDataSourceGeneratorAttribute`) i `[ClassConstructor]` z klasą bazową — nietykane.
- Pojedynczy przebieg zielony na końcu (10/10), plus powtórzenia przy eksperymentach (stała liczba 10 scope'ów
  w każdym z ok. 5 przebiegów).

## ✅ Podsumowanie weryfikacji

- ✔️ TUnit 1.76.0, .NET SDK 10.0.400, `dotnet run --project`: 10 testów (8 z CSV + 2), `0` błędów i `0` ostrzeżeń w buildzie.
- ✔️ Własne źródło danych z pliku, `$param` w `[DisplayName]`, wskazanie błędnego wiersza, DI per test ze zwolnieniem scope'ów.
- ❌ `dotnet test` (MSB1001 z bieżącego katalogu), wildcardy w filtrze.

**Pełny kod:** [`code/`](code/) — rozwiązanie [`DataLab.slnx`](code/DataLab.slnx).

---

## 📎 Jak uruchomić kod z tego wydania

Zobacz [`code/README.md`](code/README.md).

---

<div align="center">

[← wróć do wydania #29 (wszystkie rubryki)](../README.md) · [spis wydań](../../../README.md)

</div>
