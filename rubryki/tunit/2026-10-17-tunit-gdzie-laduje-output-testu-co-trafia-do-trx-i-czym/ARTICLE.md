<div align="center">

# 📰 TECH PRASÓWKA
### Wydanie #24 — 17 października 2026

![TUnit](https://img.shields.io/badge/TUnit-2EA44F?style=for-the-badge)
![Poziom](https://img.shields.io/badge/poziom-zaawansowany-D9534F?style=for-the-badge)
![Status](https://img.shields.io/badge/przebieg-zweryfikowany-2EA44F?style=for-the-badge)

## TUnit: gdzie ląduje output testu, co trafia do TRX i czym naprawdę jest `[ParallelGroup]`

</div>

---

> 📌 **Dlaczego to ważne.** Zielony test nikogo nie obchodzi. Obchodzi go czerwony test w CI o 3 w nocy:
> czy zobaczę, co test wypisał? Czy plik, który wygenerował, dotrze do raportu? Czy mogę uruchomić
> pojedynczy „drogi” test bez kopiowania całej pipeline? I czy te `[NotInParallel]`, które wkleiłem
> „na wszelki wypadek”, nie zabijają mi czasu przebiegu? Dziś odpowiedzi — **zmierzone**, nie zgadywane.

Środowisko: TUnit **1.75.0** (najnowsza w NuGet na dziś), .NET SDK 10.0.400, uruchamianie przez
`dotnet run --project ... -- <opcje>` (TUnit to zwykły plik wykonywalny). Pełny kod: [`code/`](code/).

## 🔎 Co zmierzone, a co nie

| 🧩 Fakt | 🏷️ Status |
|---|---|
| `TestContext.Current!.Output.WriteLine` i `Console.WriteLine` trafiają do TRX (`<StdOut>`) | ✔️ zmierzone |
| Output przechodzącego testu NIE jest drukowany w konsoli przy `--output Detailed` (w zwykłym przebiegu), a w porażce tak | ✔️ zmierzone |
| `Output.AttachArtifact(new Artifact { File = ... })` → wpis w sekcji „In process file artifacts” i `<ResultFile>` w TRX | ✔️ zmierzone |
| `--report-trx` działa „z pudełka” (bez dodatkowego pakietu) | ✔️ zmierzone |
| `[Explicit]` odpalony przez `--treenode-filter` z dokładną ścieżką; filtr po `[Property]` | ✔️ zmierzone |
| Kod wyjścia: wszystko pominięte = 0, filtr bez dopasowań = 8, porażka = 2 | ✔️ zmierzone |
| `[NotInParallel("klucz")]` między klasami; `[ParallelGroup]` | ✔️ zmierzone (2 przebiegi) |
| `--coverage` (format `.coverage` i `cobertura`) tworzy plik | ✔️ zmierzone, ale podsumowanie `N/A` |
| Filtry z `*` w ścieżce (`/*/*/*/Nazwa`) | ❌ środowisko odrzuciło uruchomienie |
| Zawartość raportu HTML, TRX przy porażce, wiele kluczy w jednym `[NotInParallel]` | ❌ nie sprawdzano |

## 1. 🖨️ Output: dwa kanały, jedno miejsce docelowe

```csharp
TestContext.Current!.Output.WriteLine("linia przez TestContext.Output");
Console.WriteLine("linia przez Console.WriteLine");
```

Oba trafiają do tego samego `<StdOut>` testu w TRX (prawdziwy fragment, ścieżki i nazwy użytkownika pominięte):

```xml
<UnitTestResult ... testName="Output_przez_TestContext" ... outcome="Passed" ...>
  <Output>
    <StdOut>linia przez TestContext.Output
linia przez Console.WriteLine
</StdOut>
  </Output>
</UnitTestResult>
```

A w konsoli? Test, który pada (`[Explicit]`, odpalany ręcznie, patrz niżej), pokazuje swój output pod
błędem jako `Standard output`:

```text
failed Test_ktory_pada_z_outputem (51ms)
  TUnit.Engine.Exceptions.TestFailedException: [Test Failure] AssertionException: Expected to be 5
  but found 3

  at Assert.That(sum).IsEqualTo(5)
    at ReportingLab.OutputTests.Test_ktory_pada_z_outputem() in <repo>/OutputTests.cs:35
  Standard output
    ten output ma byc widoczny przy porazce
```

W przebiegu `Detailed` output testów **zielonych** w konsoli się nie pojawił (poza jedną linią
`Console.WriteLine` na samej górze, bez przypisania do testu) — ale siedzi w TRX. Wniosek praktyczny: nie szukaj
logów zielonych testów w konsoli CI, szukaj w TRX.

> 🎯 **Haczyk (zmierzony):** `Console.WriteLine` z **hooka** `[AfterEvery(Assembly)]` wylądował w TRX
> jako `StdOut` ostatniego zakończonego testu (`B2`), a nie jako coś „sesyjnego”. Jeśli diagnostykę sesji
> wrzucasz do konsoli z hooka, w raporcie przykleisz ją do przypadkowego testu. Tyle wiem z jednego przebiegu TRX;
> nie sprawdzałem, czy to zawsze „ostatni”.

## 2. 📎 Artefakty testu

```csharp
TestContext.Current!.Output.AttachArtifact(new Artifact
{
    File = new FileInfo(path),
    DisplayName = "raport testowy",
    Description = "plik z ciala testu"
});
```

API istnieje w 1.75.0 (skompilowało się za pierwszym razem). Efekt w konsoli:

```text
  In process file artifacts produced:
    - For test 'Artefakt_pliku': /tmp/reportinglab-<guid>.txt
    - <repo>/ReportingLab/bin/Debug/net10.0/TestResults/ReportingLab-linux-net10.0-report.html
```

i w TRX, osobny test z `ResultFiles` (plik jest tam referencjonowany ścieżką względną do katalogu wyników):

```xml
<ResultFiles>
  <ResultFile path="<host>/reportinglab-<guid>.txt" />
</ResultFiles>
```

Dwie rzeczy do zapamiętania. Po pierwsze TUnit sam dorzuca własny raport HTML (`*-report.html`) — pojawił się
w każdym przebiegu, bez prośby. Po drugie artefakt to **referencja do pliku**: jeśli test zapisuje go w `/tmp`,
a runner CI sprząta `/tmp` przed publikacją, raport będzie wskazywał pustkę. Zapisuj artefakty w katalogu, który
CI publikuje.

## 3. 🧾 `--report-trx` i `--coverage`

```bash
dotnet run --project ReportingLab/ReportingLab.csproj -- --report-trx
```

```text
Test run summary: Passed! - .../ReportingLab.dll (net10.0|x64)
  total: 13
  ...
  Out of process file artifacts produced:
    - .../TestResults/ReportingLab_net10.0_x64.trx
```

Jedna pułapka liczb: w kodzie jest 14 testów, a TRX (i `total`) mówi **13** — `[Explicit]` nie jest
wliczany (wiemy to już z #18, tu potwierdzone w TRX: `<Counters total="13" executed="13" ...>`).
`--list-tests` pokazuje 14, bo wylicza wszystko.

`--coverage` działa bez doinstalowywania czegokolwiek (TUnit ciągnie rozszerzenie), tworzy plik `*.coverage`,
a z `--coverage-output-format cobertura` plik `*.cobertura.xml`. Ale podsumowanie w konsoli
wyszło `Line: N/A`, `Block: N/A`. Mój projekt nie ma kodu produkcyjnego do mierzenia, więc to nie dowód,
że nie działa — to dowód, że **nie sprawdziłem poprawnej liczby**. Nie ufaj `N/A` jako „0%”.

## 4. 🎯 Uruchamianie jednego drogiego testu: `[Explicit]` + `--treenode-filter`

```bash
dotnet run --project ReportingLab/ReportingLab.csproj -- --treenode-filter /ReportingLab/ReportingLab/OutputTests/Test_ktory_pada_z_outputem
```

Ścieżka to `/Assembly/Namespace/Klasa/Metoda`. Test `[Explicit]` ruszył (`total: 1`, `failed: 1`), kod wyjścia **2**.
Filtr po `[Property]` dopisuje się w nawiasach kwadratowych na końcu segmentu metody; sprawdziłem go przez
`--list-tests`, który zwrócił dokładnie 1 test (`found 1 test(s)`):

```bash
dotnet run --project ReportingLab/ReportingLab.csproj -- --list-tests --treenode-filter "/ReportingLab/ReportingLab/OutputTests/Test_ktory_pada_z_outputem[Kind=Failing]"
```

Uwaga uczciwości: filtry z gwiazdkami (`/*/*/*/Nazwa`, `/**/Nazwa`) to powszechna składnia, ale **moje środowisko
odrzucało każde polecenie z `*` w filtrze**, więc użyłem pełnych ścieżek. Nie widziałem na własne oczy działania wildcardów.

### Kody wyjścia (zmierzone)

| Sytuacja | `total` | Kod wyjścia |
|---|---|---|
| Wszystko przechodzi / są pominięte | 18 (17 passed, 1 skipped) | **0** |
| **Wszystkie** wybrane testy pominięte (`S1`) | 1 (0 passed, 1 skipped) | **0** — „Passed!” |
| Filtr bez dopasowań | 0 | **8** (`Zero tests ran`) |
| Test padł | 1 failed | **2** |

> 🎯 **Haczyk:** przebieg, w którym *nic nie sprawdzono* (same skipy), jest dla CI zielony. Gate na „coś
> faktycznie się wykonało” musisz zrobić sam (np. odczyt `succeeded` z outputu). Pusty filtr jest za to czerwony (8).

## 5. 🚦 `[NotInParallel("klucz")]` kontra `[ParallelGroup]`

Probe liczy, ile testów z danej grupy jednocześnie jest w ciele (`Task.Delay(300)`) i zapisuje oś czasu.
Układ: `DbWritersA` (3 testy) i `DbWritersB` (2 testy) — obie klasy z `[NotInParallel("db")]`;
`CacheWriters` z `[NotInParallel("cache")]` (2 testy); `Free` (4 testy bez ograniczeń); dwie klasy z
`[ParallelGroup("g1")]`/`[ParallelGroup("g2")]` po dwa testy.

```text
PROBE szczyt per grupa: cache=1, db=1, free=4, g1=2, g2=2; szczyt lacznie: 6
PROBE   C1   cache      0 ->   301 ms
PROBE   F1   free       2 ->   305 ms
PROBE   F3   free       3 ->   306 ms
PROBE   F4   free      14 ->   314 ms
PROBE   F2   free      14 ->   315 ms
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
```

Co z tego wynika:

- **Ten sam klucz działa ponad granicami klas.** `A*` i `B*` (dwie klasy) ułożyły się w jedną kolejkę:
  5 testów po ~300 ms jeden po drugim, szczyt `db=1`. Klucz to zamek globalny w przebiegu, nie atrybut klasy.
- **Różne klucze nie blokują się wzajemnie** — `C1` (cache) biegło równolegle z `A3` (db) i z `Free`.
  Szczyt łączny 6 = 4 wolne + 1 db + 1 cache.
- **`[ParallelGroup]` to NIE „grupa wątków”.** Testy z tej samej grupy biegną równolegle (`g1=2`),
  ale **grupy biegną po kolei**: `g2` ruszyło dopiero, gdy skończyło `g1` (1885 → 1888 ms). Co więcej, w obu
  przebiegach grupy ruszyły dopiero po zakończeniu całej kolejki `db` (B2 skończył 1569, G1 wystartował
  1583) — czyli były po kolejce testów `[NotInParallel]`. To zachowanie z dwóch przebiegów, nie gwarancja
  z dokumentacji.

> 🎯 **Haczyk kosztowy:** 5 testów z jednym kluczem `db` to 1,5 s czystej kolejki. Jeden szeroki klucz
> na „wszystko, co dotyka bazy” zmienia równoległy zestaw w sekwencyjny. Dziel klucze (per tabela, per schemat),
> nie dawaj jednego `[NotInParallel]` bez klucza na klasę „na wszelki wypadek”.

## ⚠️ Środowisko i `dotnet test`

`dotnet test --project ...` uruchomione spoza katalogu z `global.json` dało `MSB1001: Unknown switch` (SDK działa
w trybie VSTest). Przebiegi powyżej to `dotnet run --project`, który tego problemu nie ma. W `code/` jest `global.json`
z `"test": {"runner": "Microsoft.Testing.Platform"}` — `dotnet test` z tego katalogu **nie był przeze mnie uruchamiany**.

## ✅ Podsumowanie weryfikacji

- ✔️ TUnit 1.75.0, .NET SDK 10.0.400, `dotnet run`: 18 testów (17 passed, 1 skipped), 3 przebiegi bez flakowania liczb;
  oś czasu równoległości zmierzona dwukrotnie z takim samym układem.
- ✔️ Output, artefakt, TRX, `--list-tests`, `[Explicit]` przez filtr, filtr `[Property]`, kody wyjścia 0/2/8, `--coverage`.
- ❌ Filtry z `*`, `dotnet test`, zawartość HTML, TRX z porażką, wiele kluczy w jednym `[NotInParallel]`,
  realne pokrycie kodu (brak kodu produkcyjnego).

**Pełny kod:** [`code/`](code/) — projekt [`ReportingLab`](code/ReportingLab/ReportingLab.csproj).

---

## 📎 Jak uruchomić kod z tego wydania

Zobacz [`code/README.md`](code/README.md).

---

<div align="center">

[← wszystkie artykuły: 🧪 TUnit](../README.md) · [spis rubryk](../../../README.md)

</div>
