<div align="center">

# 📰 TECH PRASÓWKA
### Wydanie #25 — 18 października 2026

![TUnit](https://img.shields.io/badge/TUnit-2EA44F?style=for-the-badge)
![Poziom](https://img.shields.io/badge/poziom-zaawansowany-D9534F?style=for-the-badge)
![Status](https://img.shields.io/badge/przebieg-zweryfikowany_częściowo-F0AD4E?style=for-the-badge)

## TUnit: TRX po porażce, wiele kluczy w `[NotInParallel]` i pokrycie kodu, któremu można ufać

</div>

---

> 📌 **Dlaczego to ważne.** Wczoraj zostawiliśmy kilka białych plam: TRX tylko z zielonych testów,
> `[NotInParallel]` tylko z jednym kluczem i pokrycie `N/A` bez kodu produkcyjnego. A prawdziwe CI
> żyje właśnie tam: w czerwonym TRX, w testach dotykających dwóch zasobów naraz i w liczbie, którą
> ktoś wpisze do bramki jakości. Dziś zamykamy te luki — **zmierzone**, z jednym uczciwym wyjątkiem (na dole).

Środowisko: TUnit **1.75.0**, .NET SDK 10.0.400, uruchamianie przez `dotnet run --project ... -- <opcje>`.
Nowy projekt: biblioteka `FilterLab.Core` (kod produkcyjny) + `FilterLab.Tests` (`ProjectReference`). Pełny kod: [`code/`](code/).

## 🔎 Co zmierzone, a co nie

| 🧩 Fakt | 🏷️ Status |
|---|---|
| TRX przy porażce: `outcome="Failed"`, `<ErrorInfo>` z `<Message>` i `<StackTrace>`, `<StdOut>` z outputem testu | ✔️ zmierzone |
| `[NotInParallel(["orders", "stock"])]` — klasa blokuje dwa klucze naraz | ✔️ zmierzone (2 przebiegi) |
| Pokrycie z prawdziwą biblioteką: 80% (pełny przebieg) vs 60% (jeden test), niepokryta gałąź widoczna w cobertura XML | ✔️ zmierzone |
| `Console.WriteLine` z hooka sesji klei się do outputu testu — także w konsoli przy porażce | ✔️ zmierzone |
| Filtry z `*` w ścieżce `--treenode-filter` | ❌ środowisko odrzuciło polecenie (drugi raz) |
| `dotnet test` z katalogu `code/` | ❌ środowisko odrzuciło polecenie |

## 1. 🧾 TRX, gdy jest czerwono

Test `Celowa_porazka_z_outputem` (`[Explicit]`, odpalany filtrem) pisze linię do `TestContext.Current!.Output`
i pada na asercji. Komenda i kod wyjścia **2**:

```bash
dotnet run --project FilterLab.Tests/FilterLab.Tests.csproj -- --report-trx --treenode-filter /FilterLab.Tests/FilterLab.Tests/ShippingTests/Celowa_porazka_z_outputem
```

Prawdziwy fragment TRX (ścieżki i dane maszyny pominięte):

```xml
<UnitTestResult ... testName="Celowa_porazka_z_outputem" ... outcome="Failed" ...>
  <Output>
    <StdOut>output-przed-porazka
PROBE szczyt per grupa: 
</StdOut>
    <ErrorInfo>
      <Message>AssertionException: Expected to be 999
but found 10

at Assert.That(Shipping.Cost("standard", 1m)).IsEqualTo(999m)</Message>
      <StackTrace>   at FilterLab.Tests.ShippingTests.Celowa_porazka_z_outputem() in <repo>/ShippingTests.cs:line 42
   --- TUnit internals omitted (run with --detailed-stacktrace for full trace) ---</StackTrace>
    </ErrorInfo>
  </Output>
</UnitTestResult>
...
<Counters total="1" executed="1" passed="0" failed="1" error="0" ... />
```

Wszystko, czego potrzebuje parser raportów w CI (komunikat, stos z numerem linii, output), jest w jednym
elemencie `<Output>`. Komunikat asercji ma w TRX pełne „Expected … but found …” razem z wyrażeniem.

> 🎯 **Haczyk (zmierzony, potwierdza wczorajszy).** Zobacz linię `PROBE szczyt per grupa:` w `<StdOut>`.
> To `Console.WriteLine` z hooka `[AfterEvery(Assembly)]`, nie z testu — a wylądowało w outputcie
> **jedynego** testu tego przebiegu, także w konsoli pod „Standard output”. Hook sesji nie ma własnego
> miejsca w raporcie; jego wydruk dokleja się do testu, który skończył się ostatni. Raportuj z hooków do pliku
> (artefakt), nie do konsoli.

## 2. 🔐 `[NotInParallel]` z wieloma kluczami

Realny scenariusz: przelew między magazynami dotyka *zamówień* i *stanów magazynowych* jednocześnie.
Zwykłe zapisy do zamówień i do stanów mogą iść równolegle względem siebie, ale przelew nie może iść
równolegle z żadnymi z nich.

```csharp
[NotInParallel(["orders", "stock"])]
public class TransferTests { /* T1, T2 */ }

[NotInParallel("orders")]
public class OrdersWriters { /* O1, O2 */ }

[NotInParallel("stock")]
public class StockWriters { /* S1, S2 */ }
```

Oś czasu z przebiegu (każdy test czeka 300 ms w ciele; `Probe` zapisuje start i koniec):

```text
PROBE szczyt per grupa: AB=1, orders=1, stock=1
PROBE   O1   orders     0 ->   302 ms
PROBE   S1   stock    12 ->   312 ms
PROBE   S2   stock   313 ->   613 ms
PROBE   O2   orders   314 ->   615 ms
PROBE   T1   AB      617 ->   917 ms
PROBE   T2   AB      919 ->  1220 ms
```

Wnioski:

- **Klucze różne nie blokują się nawzajem:** `O1` (orders) i `S1` (stock) wystartowały w odstępie 12 ms
  i biegły razem; to samo `S2`/`O2`.
- **Klasa z dwoma kluczami czeka na oba:** `T1` ruszyło dopiero ~2 ms po zakończeniu *obu* sekwencji
  (615 ms), `T2` po `T1`. W żadnym momencie nie było nakładania.
- Drugi przebieg miał ten sam układ (czasy różnią się o kilkadziesiąt ms; pierwszy: `T1` 644–945, `T2` 948–1249).
  W obu przebiegach przelewy poszły **na końcu** — to kolejność, jaką zaobserwowałem, nie gwarancja
  z dokumentacji. Nie polegaj na niej.

> 🎯 **Haczyk kosztowy.** Same zapisy do zamówień i stanów zmieściły się w ~0,6 s (dwa tory równolegle);
> dwa przelewy dołożyły kolejne ~0,6 s, bo zablokowały oba tory. Wiele kluczy = precyzyjniej niż jeden szeroki `db`, ale każdy test z wieloma
> kluczami wciąż serializuje cały swój „zbiór” zasobów. Trzymaj takich testów jak najmniej.

## 3. 📊 Pokrycie z prawdziwym kodem produkcyjnym

Wczorajsze `N/A` było pytaniem o to, czy `--coverage` w ogóle widzi cokolwiek. Teraz `FilterLab.Core`
ma klasę `Shipping` z gałęziami `standard`, `express` i błędami. Gałąź `express` testuje tylko test
`[Explicit]` — czyli w zwykłym przebiegu jest niepokryta.

```bash
dotnet run --project FilterLab.Tests/FilterLab.Tests.csproj -- --coverage --coverage-output-format cobertura
```

```text
Test run summary: Passed! ...
  total: 10
  succeeded: 10
  ...
  Code Coverage Summary:
    Total - Line: 80.0%
    Total - Block: N/A
    FilterLab.Core - Line: 80.0%
    FilterLab.Core - Block: N/A
```

Plik `*.cobertura.xml` ma `line-rate="0.8"` i dwie linie z `hits="0"` (obie w gałęzi `express`).
Ten sam kod uruchomiony filtrem na **jednym** teście dał `line-rate="0.6"` (6 z 10 linii trafionych).

Trzy rzeczy do zapamiętania:

- Pokrycie liczy się tylko dla **zbadanej biblioteki** (`FilterLab.Core`); sam projekt testowy nie
  pojawia się w podsumowaniu. Dlatego rozdzielenie kodu na bibliotekę i projekt testowy daje czytelną liczbę.
- `Block: N/A` zostaje — przy formacie cobertura konsola pokazuje tylko liczby linii.
- `[Explicit]` **nie** podnosi pokrycia zwykłego przebiegu. Test „tylko na żądanie” to dług w liczbie,
  którą widzi bramka jakości.

> 🎯 **Haczyk.** 80% brzmi dobrze, a niepokryta jest cała ścieżka `express`, czyli dokładnie ta,
> która pobiera dopłatę. Procent mówi „ile linii”, nie „czy kluczowa gałąź”. Zajrzyj w XML, zanim ustawisz próg.

## ⚠️ Czego nie udało się zweryfikować

- **Filtry z `*`** (`/*/*/*/Nazwa`): po raz drugi środowisko, w którym pracuję, odrzuciło takie polecenie
  (nie próbowałem go obchodzić). Nie widziałem działania wildcardów.
- **`dotnet test` z `code/`:** polecenie (uruchomienie w katalogu z `global.json`) zostało odrzucone przez
  środowisko; z korzenia repo `dotnet test --solution` daje `MSB1001`, bo `global.json` nie jest widoczny. Przebiegi
  powyżej to `dotnet run`.
- TRX z porażką sprawdzony w jednym przebiegu; oś czasu — dwa przebiegi; pełne pokrycie (80%) — jeden przebieg, 60% — jeden.
- Zawartość raportu HTML TUnit nadal nie czytana.

## ✅ Podsumowanie weryfikacji

- ✔️ TUnit 1.75.0, .NET SDK 10.0.400, `dotnet run`: 10 testów w zwykłym przebiegu (10 passed), dwa przebiegi bez różnic w liczbach.
- ✔️ TRX z porażką, wiele kluczy `[NotInParallel]`, pokrycie z biblioteką (60% / 80%).
- ❌ Filtry z `*`, `dotnet test`, HTML.

**Pełny kod:** [`code/`](code/) — rozwiązanie [`FilterLab.slnx`](code/FilterLab.slnx).

---

## 📎 Jak uruchomić kod z tego wydania

Zobacz [`code/README.md`](code/README.md).

---

<div align="center">

[← wszystkie artykuły: 🧪 TUnit](../README.md) · [spis rubryk](../../../README.md)

</div>
