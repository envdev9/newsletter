<div align="center">

# 📰 TECH PRASÓWKA
### Wydanie #25 — 17 października 2026

![AI](https://img.shields.io/badge/AI_%2F_Prompty-D97757?style=for-the-badge&logo=anthropic&logoColor=white)
![.NET](https://img.shields.io/badge/.NET_10-512BD4?style=for-the-badge&logo=dotnet&logoColor=white)
![Roslyn](https://img.shields.io/badge/walidator-Roslyn-68217A?style=for-the-badge&logo=csharp&logoColor=white)

## Walidator odpowiedzi modelu na Roslynie: 10 fałszywych alarmów regexu, 5 przepuszczonych zmyśleń i jedna rzecz, w której regex wygrywa

</div>

---

> _"Regex odpowiada na pytanie „czy ten tekst wygląda jak deklaracja". Twój walidator powinien odpowiadać
> na pytanie „czy ten symbol istnieje"."_

Poprzednio w tej rubryce: [#18 - łańcuch promptów z kontraktem](../../2026-10-11/ai-prompts/ARTICLE.md).
Zostawiłem tam uczciwy przypis: *„indeks symboli to regexy, nie Roslyn"*. Dziś go zdejmuję i **mierzę, ile
to naprawdę zmienia**. Nie omawiam ponownie łańcucha, kontraktów C01-C17 ani promptu naprawczego.

**🎯 Dlaczego to ważne:** reguła C06 z #18 („symbol z odpowiedzi modelu musi istnieć") jest tak dobra, jak
indeks, na którym stoi. Zły indeks psuje ją w **obie strony naraz**: odrzuca prawdziwe symbole (model traci
próby na „naprawianie" poprawnej odpowiedzi) i przepuszcza zmyślone (które dojeżdżają do kroku 3 jako fakt).
A Roslyn, kompilator C# jako biblioteka, daje coś, czego regex nie da nigdy: **wynik kompilacji poprawki
w pamięci, z kodem błędu i pozycją**, gotowy do wklejenia do promptu naprawczego.

> ⚠️ **Uczciwie na starcie: żaden model nie był uruchamiany.** „Twierdzenia modelu" w
> [`code/claims.txt`](code/claims.txt) i warianty poprawek w [`code/patchcheck.py`](code/patchcheck.py)
> **napisałem ręcznie**. Mierzę walidatory, nie model. Dodatkowo korpus `hard/` **zbudowałem celowo tak,
> żeby łamał regex** - to test pułapek, nie próba reprezentatywna prawdziwego kodu.

---

### 1️⃣ Roslyn bez NuGeta, w ~120 liniach

[`code/SymbolIndex/`](code/SymbolIndex/) (.NET 10) kompiluje katalog `.cs` w pamięci
(`CSharpCompilation.Create`) i robi dwie rzeczy:

- `index <katalog>` - przechodzi po symbolach (`INamedTypeSymbol`, metody, właściwości, pola, zdarzenia,
  składowe enum), z pełną nazwą zagnieżdżoną (`Ledger.Snapshot.Describe`), dostępnością, **wszystkimi plikami
  deklaracji** i sygnaturami przeciążeń,
- `diag <katalog>` - błędy kompilatora: `CS0117 Billing/Money.cs(8,48): ...`.

Haczyk wdrożeniowy: nie potrzebujesz pakietu. Roslyn leży w SDK (`<MSBuildExtensionsPath>Roslyn/bincore/`),
więc `<Reference>` z `HintPath` działa **offline**. Cena: wersja Roslyna = wersja SDK i to nie jest
wspierany kontrakt; normalna droga to `PackageReference Include="Microsoft.CodeAnalysis.CSharp"`
(tej drogi nie sprawdzałem - brak sieci w tym przebiegu). Drugi haczyk: bez MSBuilda nie ma
`ImplicitUsings`, więc `SymbolIndex` sam dokłada `global using System; ...`; referencje to
**implementacje** runtime'u narzędzia, nie *reference assemblies* (dla naszych 6 przypadków dało to ten sam
wynik co `dotnet build`, ale to nie gwarancja).

---

### 2️⃣ Regex vs Roslyn na tych samych plikach

Regex to **dosłownie ta sama funkcja** `build_index` z #18 ([`code/regex_index.py`](code/regex_index.py);
zmieniony tylko parametr z nazwą podkatalogu). Prawda (`expected_*.txt`) - pisana ręcznie, z czytania kodu.
Dwa korpusy: `Billing` (te same 3 pliki co w #18) i `corpus/hard` (5 plików z pułapkami). Prawdziwy output
[`compare.py`](code/compare.py):

```
== korpus Billing: 12 symboli w prawdzie, regex zwrocil 9, Roslyn 12
  regex    trafione  9/12  pominiete  3  widma (nie istnieja)  0
           pominiete: InvoiceLine.Quantity, InvoiceLine.Sku, InvoiceLine.UnitPrice
  Roslyn   trafione 12/12  pominiete  0  widma (nie istnieja)  0

== korpus hard: 41 symboli w prawdzie, regex zwrocil 28, Roslyn 40
  regex    trafione 16/41  pominiete 25  widma (nie istnieja) 12
           widma:     Fake, Inner, Inner.AfterInner, Inner.Depth, Legacy, Legacy.Add, Parser.Commented, Parser.Ghost, Snapshot, Snapshot.Describe, Snapshot.Take, struct
  Roslyn   trafione 40/41  pominiete  1  widma (nie istnieja)  0
           pominiete: Platform.OnlyWin
  zgodnosc plikow dla znalezionych: regex bledne ['Ledger'], Roslyn bledne 0
```

| Pułapka (plik w `corpus/hard`) | Co robi regex | Dlaczego |
|---|---|---|
| właściwość `public decimal Balance { get; private set; }`, pole, `event`, `enum` | pomija | regex szuka `(` albo `=>` po nazwie |
| **`record` pozycyjny** (`InvoiceLine(string Sku, ...)` - **już w kodzie z #18!**) | pomija `Sku`, `Quantity`, `UnitPrice` | właściwości nie mają deklaracji w tekście |
| `readonly record struct Rate(...)` | tworzy widmo `struct`, gubi `Rate` | `record\s+(\w+)` łapie następne słowo |
| komentarz `// The old class Legacy ...` w środku klasy | widmo `Legacy`, a **kolejne składowe lądują w nim** (`Legacy.Add`) | regex nie zna komentarzy |
| `// public static int Ghost(...)` i `/* ... */` | widma `Parser.Ghost`, `Parser.Commented` | jw. |
| typ zagnieżdżony | `Snapshot.Take` zamiast `Ledger.Take` (aktualna klasa nigdy nie wraca na zewnętrzną) | brak stosu zasięgów |
| metoda generyczna `Convert<T>(`, metoda `private`/`internal` | pomija | `<T>` przed `(`; wymóg `public` |
| `partial class Ledger` w 2 plikach | wskazuje jeden plik (ostatni) | mapa symbol→jeden plik |

Jedyny punkt dla regexu: [`Platform.cs`](code/corpus/hard/Platform.cs) ma `public static int OnlyWin()` pod
`#if LEGACY_WIN`. Regex widzi tekst; Roslyn - **aktywną konfigurację**, więc symbolu nie ma. To dobra i zła
wiadomość naraz (patrz sekcja 4).

---

### 3️⃣ Co to zmienia dla reguł C06/C07: werdykty na 25 twierdzeniach

25 twierdzeń „modelu" (pisanych ręcznie; 8 zmyślonych, 17 prawdziwych - patrz
[`claims.txt`](code/claims.txt)). Reguła: symbol w indeksie **i** w tym pliku (C06+C07), przy Roslynie
dodatkowo zgodna sygnatura, jeśli ją podano. Wycinek prawdziwego outputu:

```
twierdzenie                        prawda regex    Roslyn
InvoiceLine.Quantity               real   ODRZUC   OK        <- prawdziwa wlasciwosc, regex odrzuca
Money.Round(decimal,int)           fake   OK       ODRZUC    <- zmyslone przeciazenie, regex nie zna sygnatur
Parser.Ghost                       fake   OK       ODRZUC    <- symbol tylko w komentarzu
Legacy                             fake   OK       ODRZUC
Ledger                             real   ODRZUC   OK        <- partial: C07 sprawdza zly plik
Platform.OnlyWin                   real   OK       ODRZUC    <- #if: tu Roslyn przegrywa
...
regex: poprawne decyzje 10/25, falszywe zielone 5, falszywe czerwone 10
Roslyn: poprawne decyzje 24/25, falszywe zielone 0, falszywe czerwone 1
```

| | Regex (#18) | Roslyn |
|---|---|---|
| ✅ Poprawne decyzje | 10/25 | **24/25** |
| 🟢 Fałszywe zielone (zmyślenie przeszło) | **5** | 0 |
| 🔴 Fałszywe czerwone (prawdziwy symbol odrzucony) | **10** | 1 |

Uwaga na interpretację: te 10/25 to wynik **na korpusie zbudowanym przeciw regexowi**. Na samym `Billing`
(prawdziwy kod z #18) regex miał 9/12 symboli i zawiódł tylko na właściwościach rekordu. Wniosek nie brzmi
„regex jest zły w 60%", tylko: **każda z tych pułapek to zwykły C#, a regex nie ma jak o niej zawiadomić**.
Fałszywy czerwony kosztuje pętlę naprawczą i prośbę do modelu o „poprawienie" czegoś poprawnego (model bywa
wtedy skłonny zmienić poprawną odpowiedź na gorszą - tego nie mierzyłem).

---

### 4️⃣ Krok 3: kompilacja poprawki w pamięci

Najciekawsza rzecz, której regex nie może zrobić w ogóle. [`patchcheck.py`](code/patchcheck.py) bierze 6
wariantów poprawki `Money.Round` (ciało pisane ręcznie, diff generuje `difflib`), robi `git apply` na kopii
w `/tmp` i puszcza trzy sprawdzenia: reguły formatu w stylu C13-C17, `SymbolIndex diag` (Roslyn) oraz wyrocznię
(`dotnet build` + `Billing.Check`). Prawdziwy output:

```
id             reguly formatu  Roslyn (diag)    dotnet build     Billing.Check          opis
p0_good        OK              OK               OK               zielone                poprawna: AwayFromZero
p1_bad_enum    OK              CS0117           CS0117           -                      zmyslony czlon enum
p2_bad_method  OK              CS0117           CS0117           -                      zmyslona metoda Math.RoundHalfUp
p3_bad_arg     OK              CS1503           CS1503           -                      zly typ argumentu (int zamiast enum)
p4_bad_type    OK              CS0266           CS0266           -                      double zamiast decimal (CS0266)
p5_wrong_fix   OK              OK               OK               CZERWONE: BLEDY: 1     kompiluje sie, ale zle: ToPositiveInfinity

zgodnosc zbioru kodow bledow Roslyn vs dotnet build: 6/6

przyklad listy bledow dla promptu naprawczego (p1_bad_enum):
- CS0117 Billing/Money.cs(8,48): 'MidpointRounding' does not contain a definition for 'AwayFromZeroes'
```

Trzy wnioski:

- **Format jest poprawny, a kod nie istnieje.** Cztery z sześciu poprawek przechodzą wszystkie reguły
  formatu/zakresu z #18 (mieszczą się w jednym pliku, jednym hunku, `git apply` zadowolony), a kompilator
  je odrzuca. To jest „zmyślony symbol" z kroku 1, tylko że w kroku 3, gdzie regex-owy indeks nie sięga.
- **Błąd z Roslyna jest lepszą paliwem dla promptu naprawczego** niż „poprawka nie przeszła": kod, plik,
  linia, kolumna, treść. To dokładnie format „konkretna reguła, nie opinia" z #18.
- **`p5` przechodzi wszystko poza testami.** `ToPositiveInfinity` kompiluje się, mieści w zakresie i
  zepsuje `Round(-0.125)`. Roslyn sprawdza *czy kod jest poprawnym C#*, nie *czy robi to, co trzeba* - bramka
  zachowania nadal jest niezbędna.

Czas (jeden przebieg, zimny start, ta maszyna): proces `SymbolIndex diag` 1,26-1,63 s (z czego ~1,2-1,5 s w
procesie - głównie JIT i ładowanie referencji), `dotnet build` kopii z restore 3,6-4,5 s. To nie jest porównanie
uczciwe pod względem pracy (build robi restore i emisję), a przewaga **nie wynika z samego Roslyna, tylko z braku
MSBuilda**; w procesie, który trzyma kompilację rozgrzaną, koszt byłby inny - tego nie mierzyłem.

---

### 5️⃣ Czego to nie dowodzi

> - **Żaden model nie był uruchamiany.** Twierdzenia i poprawki to moja fabrykacja. Nie wiem, jak często
>   prawdziwy model zmyśla przeciążenie, pisze o symbolu z komentarza albo sięga po `record` pozycyjny.
> - **Korpus `hard/` jest adversarialny**, a prawda (`expected_*.txt`, `claims.txt`) - moja, pisana po
>   przeczytaniu kodu; Roslyn się z nią zgodził (poza `#if`), więc „zgodność" częściowo to sprawdzenie,
>   że dobrze przeczytałem kod. 25 twierdzeń i 53 symbole to garść, nie próba statystyczna.
> - Roslyn nie widzi kodu **poza aktywną konfiguracją** (`#if`) ani wygenerowanego przez *source generators*
>   (nie testowałem generatorów w ogóle). Obejście dla `#if` - kilka kompilacji z różnymi `define` i suma - też
>   nie sprawdzane.
> - Tylko katalogi płaskie (bez podkatalogów), explicit interface implementations, operatory i lokalne funkcje
>   pomijam świadomie w obu narzędziach; przeciążenia różnią się tylko sygnaturą, więc reguła ich nie rozróżnia
>   po samej nazwie.
> - Roslyn w tym wydaniu pochodzi z SDK 10.0.400; wersja z NuGeta i zachowanie na innym SDK - niezweryfikowane.
> - **Stryker.NET** (kierunek z #14/#18): nie próbowałem go instalować, więc nie ma porównania.
> - Prompty z `prompts/` nie wchodzą w to wydanie (tylko walidator); koszt tokenowy łańcucha - dalej niemierzony.

---

## Wspólny mianownik

Walidator, który ma pilnować modelu, nie może być mniej rozumiejący kod niż sam model. Regex potrafi
sprawdzić *kształt* odpowiedzi; **czy rzecz, o której mowa, istnieje i się kompiluje, wie tylko kompilator**.
Roslyn w pamięci kosztuje ~120 linii C# i jedną referencję z SDK, a zamienia „wygląda jak symbol" na „jest
symbolem" - i daje błąd, który model da się naprawić.

---

## 📎 Jak zweryfikować

Zobacz [`code/README.md`](code/README.md) - komendy i prawdziwy output.

---

<div align="center">

[← wróć do wydania #25 (wszystkie rubryki)](../README.md) · [spis wydań](../../README.md)

</div>
