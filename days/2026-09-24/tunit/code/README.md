# Kod do wydania #1 — TUnit: pierwszy test bez refleksji w runtime

Pełny artykuł: [`../ARTICLE.md`](../ARTICLE.md). Poniżej ten sam kod + jak go odpalić.

Wymagania: **.NET 10 SDK** (`dotnet --version` → `10.x`).

## Fragment prasówki, którego dotyczy ten kod

> xUnit, NUnit i MSTest w czasie **działania programu** skanują Twoje assembly
> refleksją, żeby zbudować listę testów. TUnit robi to inaczej: **generator źródeł**
> analizuje klasy testowe **w momencie kompilacji** i generuje gotową, statyczną listę
> testów jako zwykły kod C#. Żadnego skanowania w runtime - szybszy start testów i pełna
> kompatybilność z Native AOT/trimmingiem, bez kompromisów, na które są skazane
> frameworki oparte na refleksji.
>
> Składnia asercji: `await Assert.That(wynik).IsEqualTo(5)` - fluent API zamiast
> `Assert.Equal(5, wynik)`, i **asynchroniczne** (stąd `await`).

## Struktura projektu

```
TunitDemo/
├── TunitDemo.csproj     # projekt testowy z pakietem TUnit
├── global.json          # przełącza `dotnet test` na nowy silnik Microsoft.Testing.Platform
├── Calculator.cs        # prosta klasa, którą testujemy
├── CalculatorTests.cs   # 3 testy: Add, Divide/0, IsEven
└── .gitignore           # ignoruje TestResults/ (raport HTML z każdego przebiegu)
```

## Jak odpalić od zera

```bash
# .NET SDK 10 bywa poza domyślnym PATH - jeśli `dotnet --version` nie działa:
export PATH="$HOME/.dotnet:$PATH"

cd TunitDemo
dotnet test
```

To wystarczy - `dotnet restore` i `dotnet build` odpalą się automatycznie jako część
`dotnet test`. Pakiet `TUnit` (wersja `1.69.0`) i cała reszta zależności ściągną się z
NuGet przy pierwszym uruchomieniu.

### Ważne: `global.json` w tym folderze nie jest przypadkiem

Bez pliku `global.json` z zawartością:

```json
{
  "test": {
    "runner": "Microsoft.Testing.Platform"
  }
}
```

`dotnet test` na .NET 10 SDK kończy się błędem `Testing with VSTest target is no longer
supported...` - TUnit używa nowego silnika testowego (Microsoft.Testing.Platform), a
.NET 10 SDK wymaga jawnego opt-inu do niego przy komendzie `dotnet test`. Szczegóły w
[`../ARTICLE.md`](../ARTICLE.md#pułapka-na-którą-trafisz-przy-pierwszym-dotnet-test---i-jak-ją-ominąć).

## Prawdziwy output (`dotnet test`, uruchomione lokalnie, czyste `bin/`/`obj/`)

```
$ export PATH="$HOME/.dotnet:$PATH"
$ dotnet --version
10.0.400
$ cd TunitDemo
$ rm -rf bin obj TestResults
$ dotnet test
Running tests from /home/mag/newsletter/days/2026-09-24/tunit/code/TunitDemo/bin/Debug/net10.0/TunitDemo.dll (net10.0|x64)
/home/mag/newsletter/days/2026-09-24/tunit/code/TunitDemo/bin/Debug/net10.0/TunitDemo.dll (net10.0|x64) passed (3s 064ms)

  In process file artifacts produced:
    - /home/mag/newsletter/days/2026-09-24/tunit/code/TunitDemo/TestResults/TunitDemo-linux-net10.0-report.html

Test run summary: Passed!
  total: 3
  failed: 0
  succeeded: 3
  skipped: 0
  duration: 4s 496ms
```

**3 testy, 3 przeszły, 0 nieudanych.** Sprawdzone lokalnie na `.NET SDK 10.0.400` i
`TUnit 1.69.0` przed publikacją tego wydania.
