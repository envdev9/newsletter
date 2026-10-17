# Kod do wydania #24 — TUnit: output, artefakty, TRX, kody wyjścia i `[NotInParallel]` vs `[ParallelGroup]`

Pełny artykuł: [`../ARTICLE.md`](../ARTICLE.md).

Wymagania: **.NET 10 SDK** (sprawdzone na `10.0.400`), dostęp do NuGet. Pakiet: `TUnit 1.75.0`.

## Fragment prasówki, którego dotyczy ten kod

> `TestContext.Current!.Output.WriteLine` i `Console.WriteLine` trafiają do `<StdOut>` testu w TRX; w konsoli
> output testu widać przy porażce. `Output.AttachArtifact(new Artifact { File = ... })` daje wpis w
> „In process file artifacts” i `<ResultFile>` w TRX (to referencja do pliku). `--report-trx` działa bez
> dodatkowego pakietu; `[Explicit]` nie wchodzi do `total`. Kody wyjścia: wszystko pominięte = 0, filtr bez
> dopasowań = 8, porażka = 2. `[NotInParallel("db")]` działa ponad granicami klas (jedna kolejka),
> różne klucze się nie blokują; `[ParallelGroup]`: testy w grupie równolegle, grupy po kolei.

## Struktura

```
global.json                       # "test": { "runner": "Microsoft.Testing.Platform" } -- dla `dotnet test`
ReportingLab/ReportingLab.csproj  # TUnit 1.75.0
ReportingLab/OutputTests.cs       # Output, AttachArtifact, [Explicit] test padajacy
ReportingLab/AllSkipped.cs        # test zawsze pominiety (kod wyjscia)
ReportingLab/Probe.cs             # miernik rownoleglosci + os czasu + [AfterEvery(Assembly)]
ReportingLab/ParallelTests.cs     # [NotInParallel("db"/"cache")] + testy wolne
ReportingLab/GroupTests.cs        # [ParallelGroup("g1"/"g2")]
```

## Jak odpalić od zera (zweryfikowane)

Z katalogu `code/` (lub podając ścieżkę bezwzględną do projektu):

```bash
# zwykly przebieg + os czasu rownoleglosci
dotnet run --project ReportingLab/ReportingLab.csproj -- --output Detailed

# TRX (plik w ReportingLab/bin/Debug/net10.0/TestResults/*.trx)
dotnet run --project ReportingLab/ReportingLab.csproj -- --report-trx

# [Explicit] wprost przez filtr (pada, kod wyjscia 2)
dotnet run --project ReportingLab/ReportingLab.csproj -- --output Detailed --treenode-filter /ReportingLab/ReportingLab/OutputTests/Test_ktory_pada_z_outputem

# filtr po [Property] (lista, 1 test)
dotnet run --project ReportingLab/ReportingLab.csproj -- --list-tests --treenode-filter "/ReportingLab/ReportingLab/OutputTests/Test_ktory_pada_z_outputem[Kind=Failing]"

# wszystko pominiete -> kod 0
dotnet run --project ReportingLab/ReportingLab.csproj -- --treenode-filter /ReportingLab/ReportingLab/AllSkipped/S1

# filtr bez dopasowan -> kod 8
dotnet run --project ReportingLab/ReportingLab.csproj -- --treenode-filter /ReportingLab/ReportingLab/NieMaTakiej/X

# pokrycie
dotnet run --project ReportingLab/ReportingLab.csproj -- --coverage --coverage-output-format cobertura
```

## Prawdziwy output (przebieg `--output Detailed`, ścieżki zanonimizowane)

```text
skipped S1 (32ms)
  celowo pominiety - sprawdzamy kod wyjscia
linia przez Console.WriteLine
passed Output_przez_TestContext (95ms)
passed Artefakt_pliku (92ms)
...
PROBE szczyt per grupa: cache=1, db=1, free=4, g1=2, g2=2; szczyt lacznie: 6
PROBE   C1   cache      0 ->   301 ms
PROBE   F1   free       2 ->   305 ms
PROBE   A3   db        57 ->   358 ms
PROBE   C2   cache    312 ->   614 ms
PROBE   A2   db       360 ->   660 ms
PROBE   A1   db       662 ->   963 ms
PROBE   B1   db       966 ->  1266 ms
PROBE   B2   db      1268 ->  1569 ms
PROBE   G1b  g1      1583 ->  1883 ms
PROBE   G1a  g1      1584 ->  1885 ms
PROBE   G2b  g2      1888 ->  2188 ms
PROBE   G2a  g2      1889 ->  2188 ms

  In process file artifacts produced:
    - For test 'Artefakt_pliku': /tmp/reportinglab-<guid>.txt
    - <repo>/ReportingLab/bin/Debug/net10.0/TestResults/ReportingLab-linux-net10.0-report.html

Test run summary: Passed!
  total: 18
  failed: 0
  succeeded: 17
  skipped: 1
```

Porażka `[Explicit]` przez filtr (kod wyjścia 2):

```text
failed Test_ktory_pada_z_outputem (51ms)
  ... Expected to be 5
  but found 3
  Standard output
    ten output ma byc widoczny przy porazce
  total: 1  failed: 1
```

Filtr bez dopasowań (kod 8): `Test run summary: Zero tests ran`, `total: 0`.

## Niezweryfikowane

Filtry z `*` w ścieżce (środowisko autora odrzucało takie polecenia), `dotnet test` (spoza katalogu z
`global.json` daje `MSB1001`; z `code/` nie uruchamiane), TRX przy porażce, zawartość raportu HTML,
realne pokrycie (podsumowanie `N/A` — brak kodu produkcyjnego), wiele kluczy w jednym `[NotInParallel]`.
`bin/` i `obj/` zostają po buildzie (są w `.gitignore` repo).
