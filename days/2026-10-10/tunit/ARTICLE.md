<div align="center">

# 📰 TECH PRASÓWKA
### Wydanie #17 — 10 października 2026

![TUnit](https://img.shields.io/badge/TUnit-2EA44F?style=for-the-badge)
![Poziom](https://img.shields.io/badge/poziom-średni-F0AD4E?style=for-the-badge)
![Status](https://img.shields.io/badge/przebieg-niezweryfikowany-D9534F?style=for-the-badge)

## TUnit: pomijanie testów — `[Skip]`, własny `SkipAttribute`, `Skip.Test` i `[Explicit]`

</div>

---

> ⚠️ **Uczciwie na wstępie.** To wydanie jest **niepełne**: kod się kompiluje (`dotnet build`, 0 błędów,
> 0 ostrzeżeń), ale **testów z tego wydania nie udało mi się uruchomić**. Po pierwszym, próbnym przebiegu
> (1 test-zapalnik, 1/1) środowisko zaczęło odrzucać każde `dotnet test`. Poniżej opisuję więc to, co kod
> robi z założenia, i wprost oddzielam to od tego, co zmierzyłem. **Żadnych wyników testów nie wymyślam.**

Rubryka od kilku wydań siedziała w JWT i `WebApplicationFactory`. Zmieniamy kierunek na coś, co każdy
zespół kiedyś odkrywa boleśnie: **jak pomijać testy, żeby nie okłamywać raportu**. Zakomentowany test to
test, o którym wszyscy zapomnieli. Pominięty atrybutem trafia do raportu z powodem.

## Co zmierzone, a co nie

| 🧩 Fakt | 🏷️ Status |
|---|---|
| `TUnit 1.73.19` to najnowsza wersja z NuGet w chwili pisania (wyszukiwanie `dotnet package search`; w liście stabilnych: 1.73.0, 1.73.5, 1.73.19) | ✔️ zmierzone |
| .NET SDK `10.0.400`, runner `Microsoft.Testing.Platform` przez `global.json` | ✔️ zmierzone |
| Test-zapalnik na `TUnit 1.73.19` przeszedł (1/1, ok. 1,9 s); `dotnet test` wypisał też artefakt `SkipLab.Tests-linux-net10.0-report.html` | ✔️ zmierzone (jeden przebieg, przed dodaniem właściwych testów) |
| Poniższe API się **kompiluje** na 1.73.19: `SkipAttribute` z nadpisaniem `Task<bool> ShouldSkip(TestRegisteredContext)`, `Skip.Test(string)`, `[Explicit]` | ✔️ zmierzone (`dotnet build`) |
| Jak pominięte testy wyglądają w podsumowaniu (`skipped: N`), czy `[Explicit]` ujawnia się filtrem, kod wyjścia, kiedy dokładnie wołany jest `ShouldSkip` | ❌ **niezmierzone** |

## 1. ⏭️ Pięć sposobów, trzy poziomy „kiedy”

W `SkipTests.cs` jest po jednym teście na każdy sposób:

| Sposób | Kiedy zapada decyzja | Po co |
|---|---|---|
| `[Skip("powód")]` | statycznie, zawsze | znana usterka z ticketem; powód do raportu |
| `[RequiresEnvVar("SKIPLAB_DB")]` (własny `SkipAttribute`) | przy rejestracji testu, przez `ShouldSkip` | test integracyjny, który ma sens tylko tam, gdzie jest zasób |
| `[LinuxOnly]` (własny `SkipAttribute`) | j.w. | testy zależne od systemu plików/OS |
| `Skip.Test("powód")` w ciele testu | w trakcie, gdy dopiero test się dowie | warunek znany dopiero po zrobieniu czegoś |
| `[Explicit]` | nie biegnie, chyba że wskaże go filtr | drogie testy (benchmarki, smoke na produkcję) |

Własny atrybut jest króciutki — cała „inteligencja” to jedna metoda:

```csharp
public sealed class RequiresEnvVarAttribute(string name) : SkipAttribute($"brak zmiennej srodowiskowej {name}")
{
    public override Task<bool> ShouldSkip(TestRegisteredContext context)
        => Task.FromResult(string.IsNullOrEmpty(Environment.GetEnvironmentVariable(name)));
}
```

Ten kształt (konstruktor z powodem + `ShouldSkip`) to **to, co się kompiluje na 1.73.19** — i tyle mogę o nim
poręczyć. Kolejność wywołań i moment decyzji to moje założenia z nazwy metody, nie pomiar.

> 🎯 **Dlaczego to ważne:** pominięcie z powodem i z warunkiem trzyma w raporcie *widoczny dług*. Test bez
> bazy danych na laptopie dewelopera nie ma być zielony (bo nic nie sprawdził) ani czerwony (bo to nie błąd),
> tylko pominięty — i właśnie ta trzecia kategoria jest sensem tej rubryki. Zanim zaufasz „zielonemu”
> buildowi, sprawdź w nim liczbę pominiętych.

## 2. 🔬 Czego bym się spodziewał (hipotezy do sprawdzenia przez czytelnika)

To **nie jest output**, tylko lista rzeczy do sprawdzenia, kiedy odpalisz kod u siebie:

1. `dotnet test` bez zmiennej `SKIPLAB_DB`: test `Wymaga_zmiennej_srodowiskowej` jest pominięty; z
   `SKIPLAB_DB=cokolwiek` — biegnie i przechodzi.
2. `Droga_operacja_tylko_na_zadanie` (`[Explicit]`) nie biegnie w zwykłym przebiegu. Jak go uruchomić
   (`--treenode-filter` z nazwą testu — składnia z #13)? To trzeba sprawdzić.
3. `Statycznie_pominiety` nie wykona ciała (które i tak by padło: `char.IsLetterOrDigit` przepuszcza `ż`).
4. `Pominiety_w_trakcie` na Linuksie z ext4 (rozróżnia wielkość liter): pominięty z komunikatem.

## 3. ⚠️ Pułapka, która jest już udowodniona z konstrukcji

`Statycznie_pominiety` zawiera **błędną asercję** (oczekuje `zazolc`, a `Slugifier` zachowa `zażółć`). Gdyby ktoś
usunął `[Skip]`, test by padł. To celowy przykład na to, że pominięcie chowa także *niepoprawny* test —
dlatego powód musi mieć numer ticketu, a zespół powinien liczyć pominięte w CI.

## ✅ Co zweryfikowano, a co nie

- ✔️ `dotnet build` projektu `SkipLab.Tests`: 0 błędów, 0 ostrzeżeń, TUnit 1.73.19, .NET SDK 10.0.400.
- ✔️ Jeden przebieg `dotnet test` z jednym testem-zapalnikiem: 1/1.
- ❌ **Przebieg właściwych testów (`SkipTests.cs`): nie wykonany** — kolejne `dotnet test` zostały odrzucone
  przez środowisko (3 próby, w tym z `--no-build`; `dotnet build` i `dotnet --version` przechodziły). Nie obchodziłem blokady.
- ❌ Niezweryfikowane: liczba pominiętych w podsumowaniu, działanie `[Explicit]` z filtrem, moment wołania
  `ShouldSkip`, zachowanie przy wszystkich testach pominiętych (kod wyjścia 8?), `[Property]` i filtr po
  właściwościach (planowane jako druga część wydania — nie zaczęte), artefakty/`TestContext.Output`.
- ⚠️ `bin/` i `obj/` zostały w `code/` (usunięcie odrzucone); są w `code/.gitignore`.

**Pełny kod:** [`code/`](code/) — solution [`SkipLab.slnx`](code/SkipLab.slnx).

---

## 📎 Jak uruchomić kod z tego wydania

Zobacz [`code/README.md`](code/README.md).

---

<div align="center">

[← wróć do wydania #17 (wszystkie rubryki)](../README.md) · [spis wydań](../../../README.md)

</div>
