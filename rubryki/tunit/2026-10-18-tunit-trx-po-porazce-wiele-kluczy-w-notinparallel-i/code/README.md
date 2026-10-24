# Kod do wydania #25 — TUnit: TRX po porażce, `[NotInParallel]` z wieloma kluczami, pokrycie z biblioteką

Pełny artykuł: [`../ARTICLE.md`](../ARTICLE.md).

Wymagania: **.NET 10 SDK** (sprawdzone na `10.0.400`), dostęp do NuGet. Pakiet: `TUnit 1.75.0`.

## Fragment prasówki, którego dotyczy ten kod

> TRX przy porażce ma `outcome="Failed"`, `<ErrorInfo>` (`<Message>` z „Expected … but found …” i
> `<StackTrace>` z numerem linii) oraz `<StdOut>` z outputem testu; `Console.WriteLine` z hooka
> `[AfterEvery(Assembly)]` dokleja się do outputu testu. `[NotInParallel(["orders", "stock"])]` blokuje
> oba klucze naraz: klasa z dwoma kluczami nie nakłada się z żadną z klas z pojedynczym kluczem, a te dwie
> biegną równolegle. `--coverage --coverage-output-format cobertura` na bibliotece produkcyjnej dało 80%
> linii (niepokryta gałąź `express`, testowana tylko przez `[Explicit]`), a jeden test — 60%.

## Struktura

```
global.json                          # "test": { "runner": "Microsoft.Testing.Platform" }
FilterLab.slnx
FilterLab.Core/Shipping.cs           # kod produkcyjny (gałąź express niepokryta w zwykłym przebiegu)
FilterLab.Tests/ShippingTests.cs     # testy + [Explicit] (express, celowa porażka)
FilterLab.Tests/MultiKeyTests.cs     # [NotInParallel(["orders","stock"])] i pojedyncze klucze
FilterLab.Tests/Probe.cs             # miernik równoległości + oś czasu + [AfterEvery(Assembly)]
```

## Jak odpalić od zera (zweryfikowane `dotnet run`)

Podaj ścieżkę do projektu (z korzenia repo: `rubryki/tunit/2026-10-18-tunit-trx-po-porazce-wiele-kluczy-w-notinparallel-i/code/FilterLab.Tests/FilterLab.Tests.csproj`):

```bash
# zwykły przebieg + oś czasu
dotnet run --project FilterLab.Tests/FilterLab.Tests.csproj -- --output Detailed

# TRX z porażką (kod wyjścia 2); plik: FilterLab.Tests/bin/Debug/net10.0/TestResults/*.trx
dotnet run --project FilterLab.Tests/FilterLab.Tests.csproj -- --report-trx --treenode-filter /FilterLab.Tests/FilterLab.Tests/ShippingTests/Celowa_porazka_z_outputem

# pokrycie, pełny przebieg (80%), potem cobertura XML w TestResults/
dotnet run --project FilterLab.Tests/FilterLab.Tests.csproj -- --coverage --coverage-output-format cobertura

# pokrycie jednego testu (60%)
dotnet run --project FilterLab.Tests/FilterLab.Tests.csproj -- --coverage --coverage-output-format cobertura --treenode-filter /FilterLab.Tests/FilterLab.Tests/ShippingTests/Standard_do_kilograma_kosztuje_10
```

## Prawdziwy output (zwykły przebieg, ścieżki skrócone)

```text
passed Standard_ponad_kilogram_doplata_2_za_kg (25ms)
passed Standard_do_kilograma_kosztuje_10 (28ms)
passed Waga_niedodatnia_rzuca (17ms)
passed Nieznana_metoda_rzuca (2ms)
passed O1 (310ms)
passed S1 (301ms)
passed S2 (301ms)
passed O2 (303ms)
passed T1 (301ms)
PROBE szczyt per grupa: AB=1, orders=1, stock=1
PROBE   O1   orders     0 ->   302 ms
PROBE   S1   stock    12 ->   312 ms
PROBE   S2   stock   313 ->   613 ms
PROBE   O2   orders   314 ->   615 ms
PROBE   T1   AB      617 ->   917 ms
PROBE   T2   AB      919 ->  1220 ms
passed T2 (301ms)

Test run summary: Passed!
  total: 10
  failed: 0
  succeeded: 10
  skipped: 0
```

Porażka (kod wyjścia 2):

```text
failed Celowa_porazka_z_outputem (58ms)
  TUnit.Engine.Exceptions.TestFailedException: [Test Failure] AssertionException: Expected to be 999
  but found 10
  Standard output
    output-przed-porazka
    PROBE szczyt per grupa: 
  total: 1  failed: 1
```

Pokrycie (pełny przebieg): `FilterLab.Core - Line: 80.0%`, `Block: N/A`.

## Niezweryfikowane

- Filtry z `*` w `--treenode-filter` (środowisko autora odrzuciło polecenie).
- `dotnet test` z katalogu `code/` (odrzucone przez środowisko; z korzenia repo `--solution` daje `MSB1001`).
- Zawartość raportu HTML TUnit.
- `bin/` i `obj/` zostają po buildzie (są w `.gitignore` tego katalogu); `TestResults/` też.
