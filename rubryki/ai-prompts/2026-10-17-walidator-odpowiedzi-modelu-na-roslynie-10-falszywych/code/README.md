# Kod do wydania #25 — walidator na Roslynie zamiast regexów

Pełny artykuł: [`../ARTICLE.md`](../ARTICLE.md).

## Fragment prasówki, którego dotyczy ten kod

> Reguła C06 z #18 („symbol z odpowiedzi modelu musi istnieć") jest tak dobra, jak indeks symboli. Ten sam
> indeks zbudowany regexami i Roslynem, puszczony na tych samych plikach (3 pliki `Billing` z #18 + 5 plików
> `corpus/hard` zbudowanych jako pułapki): regex 25 trafionych symboli z 53, 12 widm, 28 pominiętych; Roslyn 52/53
> (nie widzi tylko symbolu pod nieaktywnym `#if`). Na 25 twierdzeniach „modelu": regex 10/25 poprawnych decyzji
> (5 fałszywych zielonych, 10 fałszywych czerwonych), Roslyn 24/25. Roslyn dodatkowo kompiluje poprawkę w pamięci:
> 4 z 6 wariantów przechodzi reguły formatu, a kompilator je odrzuca (CS0117/CS1503/CS0266, zgodnie z `dotnet build`);
> poprawka, która się kompiluje, ale jest błędna, odpada dopiero na testach. **Żaden model nie był uruchamiany:
> twierdzenia i poprawki są pisane ręcznie, korpus `hard/` jest adversarialny.**

## Struktura

```
code/
├── Billing/            # biblioteka z #18 (kopia; banker's rounding w Money.Round)
├── Billing.Check/      # kryterium akceptacji z #18 (6 przypadków)
├── corpus/hard/        # 5 plików C# z pułapkami (komentarze, zagnieżdżenia, partial, record struct, #if...)
├── SymbolIndex/        # Roslyn: `index` (indeks symboli) i `diag` (błędy kompilatora); bez NuGeta
├── regex_index.py      # build_index z chain.py (#18), jedyna zmiana: parametr podkatalogu
├── expected_*.txt      # prawda o symbolach (PISANA RĘCZNIE)
├── claims.txt          # 25 twierdzeń "modelu" (PISANE RĘCZNIE) z etykietą real/fake
├── compare.py          # regex vs Roslyn: indeks + werdykty C06/C07
└── patchcheck.py       # 6 wariantów poprawki: reguły formatu vs Roslyn vs dotnet build + Billing.Check
```

## Jak uruchomić od zera

Wymagania: .NET SDK 10.0.400 (Roslyn jest brany z katalogu SDK, offline), Python 3 stdlib (3.10.4), `git`
(tylko `git apply`). Komendy z katalogu głównego repo; `-B` = bez `__pycache__`. `patchcheck.py` sprząta kopie
w `/tmp` (`patchcheck-*`); `bin/obj` zostają w `SymbolIndex/` i `Billing*/` (są w `.gitignore`).

```bash
# 1. zbuduj narzędzie (Release; compare.py/patchcheck.py szukają bin/Release/net10.0/SymbolIndex.dll)
dotnet build rubryki/ai-prompts/2026-10-17-walidator-odpowiedzi-modelu-na-roslynie-10-falszywych/code/SymbolIndex/SymbolIndex.csproj -c Release -nologo

# 2. indeks Roslyna ręcznie (kolumny: symbol, rodzaj, dostępność, pliki, sygnatury) i diagnostyka
dotnet rubryki/ai-prompts/2026-10-17-walidator-odpowiedzi-modelu-na-roslynie-10-falszywych/code/SymbolIndex/bin/Release/net10.0/SymbolIndex.dll index rubryki/ai-prompts/2026-10-17-walidator-odpowiedzi-modelu-na-roslynie-10-falszywych/code/corpus/hard
dotnet rubryki/ai-prompts/2026-10-17-walidator-odpowiedzi-modelu-na-roslynie-10-falszywych/code/SymbolIndex/bin/Release/net10.0/SymbolIndex.dll diag rubryki/ai-prompts/2026-10-17-walidator-odpowiedzi-modelu-na-roslynie-10-falszywych/code/Billing

# 3. regex vs Roslyn: indeks na 2 korpusach + 25 werdyktów
python3 -B rubryki/ai-prompts/2026-10-17-walidator-odpowiedzi-modelu-na-roslynie-10-falszywych/code/compare.py

# 4. poprawki: reguły formatu vs Roslyn vs dotnet build (kilka buildów, ~1 min)
python3 -B rubryki/ai-prompts/2026-10-17-walidator-odpowiedzi-modelu-na-roslynie-10-falszywych/code/patchcheck.py

# 5. (kontrola) błąd z #18 nadal istnieje: exit 1, 5x FAIL
dotnet run --project rubryki/ai-prompts/2026-10-17-walidator-odpowiedzi-modelu-na-roslynie-10-falszywych/code/Billing.Check/Billing.Check.csproj
```

Wariant z pakietem NuGet zamiast referencji do SDK: w `SymbolIndex.csproj` zastąp oba `<Reference>` przez
`<PackageReference Include="Microsoft.CodeAnalysis.CSharp" Version="..." />`. **Nie sprawdzałem** (brak sieci).

## Weryfikacja — rzeczywisty output (uruchomione 2026-10-17, .NET 10.0.400, Python 3.10.4)

### `SymbolIndex index corpus/hard` (fragment) i `diag`

```
IPricer.Price	method	public	hard/Shapes.cs	string
Ledger	class	public	hard/Ledger.cs;hard/Ledger.Reports.cs	
Ledger.Snapshot.Describe	method	public	hard/Ledger.cs	
Parser.Convert	method	public	hard/Tricky.cs	string
Pricer.Price	method	public	hard/Shapes.cs	string;string,int
Rate.Currency	property	public	hard/Shapes.cs	
Tier.Premium	enummember	public	hard/Shapes.cs	
(40 symboli; bez Platform.OnlyWin, bo #if LEGACY_WIN jest nieaktywny)

diag corpus/hard:  # errors=0 warnings=1   (ms zalezy od przebiegu)
```

### `compare.py` (exit 0)

```
== korpus Billing: 12 symboli w prawdzie, regex zwrocil 9, Roslyn 12
  regex    trafione  9/12  pominiete  3  widma (nie istnieja)  0
           pominiete: InvoiceLine.Quantity, InvoiceLine.Sku, InvoiceLine.UnitPrice
  Roslyn   trafione 12/12  pominiete  0  widma (nie istnieja)  0
  regex (porownanie luzne, 2 ostatnie czlony): trafione 9/12
  zgodnosc plikow dla znalezionych: regex bledne 0, Roslyn bledne 0

== korpus hard: 41 symboli w prawdzie, regex zwrocil 28, Roslyn 40
  regex    trafione 16/41  pominiete 25  widma (nie istnieja) 12
           pominiete: IPricer.Price, Ledger.Add, Ledger.Balance, Ledger.Banner, Ledger.Count, Ledger.Snapshot, Ledger.Snapshot.Describe, Ledger.Snapshot.Value, Ledger.Take, Ledger._entries, Outer.AfterInner, Outer.Changed, Outer.Inner, Outer.Inner.Depth, Outer.Width, Parser.Convert, Parser.Helper, Pricer.Range, Pricer._calls, Rate, Rate.Currency, Rate.Value, Tier, Tier.Basic, Tier.Premium
           widma:     Fake, Inner, Inner.AfterInner, Inner.Depth, Legacy, Legacy.Add, Parser.Commented, Parser.Ghost, Snapshot, Snapshot.Describe, Snapshot.Take, struct
  Roslyn   trafione 40/41  pominiete  1  widma (nie istnieja)  0
           pominiete: Platform.OnlyWin
  regex (porownanie luzne, 2 ostatnie czlony): trafione 18/41
  zgodnosc plikow dla znalezionych: regex bledne ['Ledger'], Roslyn bledne 0

RAZEM (oba korpusy):
  regex   trafione 25, pominiete 28, widma 12
  roslyn  trafione 52, pominiete 1, widma 0

== werdykty C06/C07 na twierdzeniach (OK = walidator przepuszcza, ODRZUC = odrzuca)
twierdzenie                        prawda regex    Roslyn   notatka
Money.Round                        real   OK       OK       kontrola: istnieje
InvoiceLine.Quantity               real   ODRZUC   OK       wlasciwosc pozycyjna rekordu
InvoiceCalculator.RoundTotal       fake   ODRZUC   ODRZUC   zmyslony symbol z #18 (S2)
Money.Round(decimal,int)           fake   OK       ODRZUC   zmyslone przeciazenie (Math.Round je ma, Money.Round nie)
Money.Fake                         fake   ODRZUC   ODRZUC   kontrola: nigdzie nie wystepuje
Ledger.Balance                     real   ODRZUC   OK       wlasciwosc auto, bez nawiasu
Ledger.Take                        real   ODRZUC   OK       metoda po zagniezdzonej klasie
Ledger.Snapshot                    real   ODRZUC   OK       typ zagniezdzony
Ledger                             real   ODRZUC   OK       klasa partial: deklaracja takze w drugim pliku
Ledger.Average                     real   OK       OK       kontrola: prosta metoda
Legacy                             fake   OK       ODRZUC   wystepuje tylko w komentarzu "old class Legacy"
Outer.AfterInner                   real   ODRZUC   OK       skladowa po zagniezdzonej klasie
Parser.Parse                       real   OK       OK       kontrola: prosta metoda
Parser.Parse                       fake   ODRZUC   ODRZUC   zly plik (C07)
Parser.Ghost                       fake   OK       ODRZUC   wystepuje tylko w komentarzu //
Parser.Commented                   fake   OK       ODRZUC   wystepuje tylko w komentarzu /* */
Parser.Convert                     real   ODRZUC   OK       metoda generyczna
Parser.Helper                      real   ODRZUC   OK       metoda prywatna (bug moze siedziec w prywatnej)
Parser.LoadAsync                   real   OK       OK       kontrola: async
Pricer.Old                         real   OK       OK       kontrola: atrybut + sygnatura w 2 liniach
Pricer.Price(string,int)           real   OK       OK       istniejace przeciazenie
Pricer.Price(string,int,int)       fake   OK       ODRZUC   zmyslone przeciazenie
Platform.OnlyWin                   real   OK       ODRZUC   istnieje w tekscie, ale pod #if LEGACY_WIN (nieaktywny) - tu Roslyn przegrywa
Rate                               real   ODRZUC   OK       record struct
Tier.Premium                       real   ODRZUC   OK       skladowa enum
regex: poprawne decyzje 10/25, falszywe zielone (zmyslony symbol przeszedl) 5, falszywe czerwone (prawdziwy symbol odrzucony) 10
Roslyn: poprawne decyzje 24/25, falszywe zielone (zmyslony symbol przeszedl) 0, falszywe czerwone (prawdziwy symbol odrzucony) 1
```

### `patchcheck.py` (exit 0)

```
id             reguly formatu  Roslyn (diag)    dotnet build     Billing.Check          opis
p0_good        OK              OK               OK               zielone                poprawna: AwayFromZero
p1_bad_enum    OK              CS0117           CS0117           -                      zmyslony czlon enum
p2_bad_method  OK              CS0117           CS0117           -                      zmyslona metoda Math.RoundHalfUp
p3_bad_arg     OK              CS1503           CS1503           -                      zly typ argumentu (int zamiast enum)
p4_bad_type    OK              CS0266           CS0266           -                      double zamiast decimal (CS0266)
p5_wrong_fix   OK              OK               OK               CZERWONE: BLEDY: 1     kompiluje sie, ale zle: ToPositiveInfinity

zgodnosc zbioru kodow bledow Roslyn vs dotnet build: 6/6
czasy [ms] (1 przebieg, zimny start): p0_good: Roslyn proces 1258 (w procesie 1174) / build 4401; p1_bad_enum: Roslyn proces 1584 (w procesie 1482) / build 4133; p2_bad_method: Roslyn proces 1541 (w procesie 1457) / build 4515; p3_bad_arg: Roslyn proces 1474 (w procesie 1385) / build 3868; p4_bad_type: Roslyn proces 1523 (w procesie 1436) / build 3567; p5_wrong_fix: Roslyn proces 1625 (w procesie 1539) / build 4052

przyklad listy bledow dla promptu naprawczego (p1_bad_enum):
- CS0117 Billing/Money.cs(8,48): 'MidpointRounding' does not contain a definition for 'AwayFromZeroes'
```

Czasy zmieniają się między przebiegami; to jeden przebieg, nie benchmark.

### `Billing.Check` przed poprawką (exit 1)

```
OK   Round(2.675): 2.68 (oczekiwano 2.68)
FAIL Round(2.665): 2.66 (oczekiwano 2.67)
FAIL Round(0.125): 0.12 (oczekiwano 0.13)
FAIL Round(-0.125): -0.12 (oczekiwano -0.13)
FAIL LineTotal(3 x 0.835): 2.50 (oczekiwano 2.51)
FAIL Total(2 x 0.125 + 10.00, rabat 10%): 9.23 (oczekiwano 9.22)
BLEDY: 5
```

## Co NIE jest zweryfikowane

- **Zachowanie jakiegokolwiek modelu** — żaden nie był uruchamiany; twierdzenia (`claims.txt`) i ciała poprawek
  (`patchcheck.py`) są pisane ręcznie. Częstość takich błędów u prawdziwego modelu nieznana.
- Korpus `hard/` jest **adversarialny** (zbudowany przeciw regexowi), prawda jest moja (czytanie kodu); 53 symbole
  i 25 twierdzeń to nie próba statystyczna. Sam `Billing` (prawdziwy kod z #18): regex 9/12.
- Roslyn nie widzi kodu pod nieaktywnym `#if` (zmierzone: `Platform.OnlyWin`) ani wygenerowanego przez *source
  generators* (niezmierzone); obejście kilkoma zestawami `define` — nie sprawdzane.
- Referencje kompilacji to implementacje runtime'u narzędzia (nie *reference assemblies*); zgodność z `dotnet build`
  zmierzona tylko na 6 poprawkach jednej metody.
- Roslyn z SDK (nie NuGet) — wersja zależna od SDK, nie wspierany kontrakt; wariant z `PackageReference` nieuruchomiony.
- Pominięte celowo w obu narzędziach: podkatalogi, explicit interface implementations, operatory, konstruktory.
- Czasy: jeden przebieg, zimny start, `dotnet build` z restore (inna praca niż `diag`); rozgrzany proces nie mierzony.
- Stryker.NET nie był próbowany; koszt tokenów łańcucha vs jeden prompt — niemierzony.
