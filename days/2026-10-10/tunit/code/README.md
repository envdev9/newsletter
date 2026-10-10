# Kod do wydania #17 — TUnit: pomijanie testów (`[Skip]`, własny `SkipAttribute`, `Skip.Test`, `[Explicit]`)

Pełny artykuł: [`../ARTICLE.md`](../ARTICLE.md).

> ⚠️ **Status:** projekt się kompiluje (`dotnet build`: 0 błędów, 0 ostrzeżeń), ale właściwe testy
> (`SkipTests.cs`) **nie zostały uruchomione** — `dotnet test` był odrzucany przez środowisko autora.
> Nie ma tu więc "prawdziwego outputu" testów; uruchom i sprawdź sam.

Wymagania: **.NET 10 SDK** (sprawdzone na `10.0.400`), dostęp do NuGet. Pakiet: `TUnit 1.73.19`.

## Fragment prasówki, którego dotyczy ten kod

> Pominięty test z powodem to widoczny dług, a zakomentowany — zapomniany. TUnit pozwala pominąć test
> statycznie (`[Skip("powód")]`), warunkowo własnym atrybutem dziedziczącym po `SkipAttribute`
> (`ShouldSkip`), z wnętrza testu (`Skip.Test("powód")`) albo oznaczyć go `[Explicit]`. Wszystkie te API
> kompilują się na TUnit 1.73.19; ich zachowanie w runtime nie zostało zmierzone.

## Struktura

```
global.json                      # "test": { "runner": "Microsoft.Testing.Platform" } -- WYMAGANE
SkipLab.slnx
SkipLab/Probes.cs                # Slugifier, FsProbe (czy FS rozroznia wielkosc liter), DbSettings
SkipLab.Tests/EnvironmentSkips.cs  # [RequiresEnvVar], [LinuxOnly] : SkipAttribute
SkipLab.Tests/SkipTests.cs       # po jednym tescie na kazdy sposob pomijania
```

## Jak odpalić od zera

```bash
cd code
dotnet test --solution SkipLab.slnx --results-directory /tmp/tunit-skiplab-results
```

(Autor uruchamiał wcześniej `dotnet test --project SkipLab.Tests/SkipLab.Tests.csproj` z `global.json`
w katalogu nadrzędnym; wariant `--solution` nie był testowany w tym wydaniu.)

Z włączoną zmienną (test `Wymaga_zmiennej_srodowiskowej` powinien przestać być pominięty):

```bash
SKIPLAB_DB=demo dotnet test --solution SkipLab.slnx --results-directory /tmp/tunit-skiplab-results
```

Co sprawdzić (hipotezy, nie wyniki): liczba `skipped` w podsumowaniu; jak uruchomić test `[Explicit]`
filtrem `--treenode-filter`.

## Nie zweryfikowano

Wszystkiego, co dotyczy uruchomienia `SkipTests.cs`: liczby pominiętych, `[Explicit]` z filtrem, momentu
wywołania `ShouldSkip`, kodu wyjścia. Zweryfikowane: kompilacja oraz jeden przebieg testu-zapalnika (1/1).

Artefakty: po budowie zostały `bin/` i `obj/` (wykluczone przez `.gitignore`).
