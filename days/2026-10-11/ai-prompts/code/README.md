# Kod do wydania #18 — łańcuch promptów z kontraktem między krokami

Pełny artykuł: [`../ARTICLE.md`](../ARTICLE.md).

## Fragment prasówki, którego dotyczy ten kod

> Jeden prompt „napraw i upewnij się, że testy przechodzą" ma jedno kryterium: kolor testów. Łańcuch trzech
> kroków (triaż → plan → patch) z **kontraktem na granicy każdego kroku** odrzuca zmyślony symbol, rozrost zakresu
> i edycję testów, zanim wynik trafi do następnego promptu; błąd walidatora wraca do modelu jako lista reguł.
> Na 7 nagraniach: fałszywe zielone 0 (kontrakty) vs 2 (ten sam łańcuch bez kontraktów, tylko bramka końcowa),
> koszt: 1 fałszywe czerwone (ścisły JSON). Kontrakty nie rozumieją poprawności — zła poprawka w dobrym formacie
> odpada dopiero w bramce zachowania. **Żaden model nie był uruchamiany: „odpowiedzi modelu" to ręcznie pisane
> nagrania** (`fixtures/`), więc wynik mówi o łańcuchu i kontraktach, nie o modelu.

## Struktura

```
code/
├── Billing/            # biblioteka .NET 10 z prawdziwym błędem (banker's rounding w Money.Round)
├── Billing.Check/      # kryterium akceptacji: 6 przypadków, exit 1 przy porażce (przed poprawką: 5 FAIL)
├── bug_report.txt      # wejście kroku 1
├── prompts/            # mega_bad.txt (zły) + step1/2/3 + repair (szablony z {{placeholderami}})
├── chain.py            # indeks symboli, budowanie promptów, kontrakty C01-C17, prompt naprawczy, bramka, runner
├── fixtures/           # 7 nagrań "odpowiedzi modelu" (PISANE RĘCZNIE): s0..s6, po 3 pliki stepN.txt
└── test_chain.py       # każde nagranie: z kontraktami vs bez; tabela i metryki
```

## Jak uruchomić

Wymagania: .NET SDK (użyto 10.0.400), Python 3 stdlib (3.10.4), `git` (tylko `git apply`; działa poza
repozytorium). Komendy z katalogu głównego repo; `-B` = bez `__pycache__`. Skrypty same sprzątają kopie robocze
w `/tmp` (`prompt-chain-*`, `prompt-gate-*`) i nie zostawiają `bin/obj` w repo.

```bash
# 1. błąd istnieje (exit 1, 5x FAIL); zostawia bin/obj w code/ (są w .gitignore)
dotnet run --project days/2026-10-11/ai-prompts/code/Billing.Check/Billing.Check.csproj

# 2. indeks symboli i zbudowany prompt kroku 2 (wejście = nagranie kroku 1 po walidacji)
python3 -B days/2026-10-11/ai-prompts/code/chain.py index
python3 -B days/2026-10-11/ai-prompts/code/chain.py prompt 2

# 3. walidacja pojedynczego kroku (exit 1 = naruszenia)
python3 -B days/2026-10-11/ai-prompts/code/chain.py check-step 1 days/2026-10-11/ai-prompts/code/fixtures/s2_halluc_symbol/step1.txt
python3 -B days/2026-10-11/ai-prompts/code/chain.py check-step 2 days/2026-10-11/ai-prompts/code/fixtures/s3_scope_creep/step2.txt --triage days/2026-10-11/ai-prompts/code/fixtures/s3_scope_creep/step1.txt
python3 -B days/2026-10-11/ai-prompts/code/chain.py check-step 3 days/2026-10-11/ai-prompts/code/fixtures/s4_test_tamper/step3.txt --plan days/2026-10-11/ai-prompts/code/fixtures/s4_test_tamper/step2.txt

# 4. prompt naprawczy zbudowany z błędów walidatora
python3 -B days/2026-10-11/ai-prompts/code/chain.py repair 1 days/2026-10-11/ai-prompts/code/fixtures/s2_halluc_symbol/step1.txt

# 5. cały łańcuch na jednym nagraniu (z kontraktami / bez)
python3 -B days/2026-10-11/ai-prompts/code/chain.py run s6_wrong_fix
python3 -B days/2026-10-11/ai-prompts/code/chain.py run s4_test_tamper --no-contracts

# 6. porównanie na wszystkich 7 nagraniach (kilka buildów dotnet; exit 0 = zgodne z oczekiwaniem)
python3 -B days/2026-10-11/ai-prompts/code/test_chain.py
```

Podpięcie prawdziwego modelu: `chain.run_chain(model, contracts=True, ...)` przyjmuje dowolne
`Callable[[int, str], str]` (numer kroku, prompt → tekst). **Tego nie uruchamiałem** — jedyna zaimplementowana
wtyczka to `ReplayModel`.

## Weryfikacja — rzeczywisty output (uruchomione 2026-10-11, .NET 10.0.400, Python 3.10.4)

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

### `chain.py index`

```
Billing/Discounts.cs: Discounts, Discounts.IsEligible
Billing/InvoiceCalculator.cs: InvoiceCalculator, InvoiceCalculator.LineTotal, InvoiceCalculator.Total, InvoiceLine
Billing/Money.cs: Money, Money.Percent, Money.Round
```

### `check-step` na nagraniach z awariami (każde: exit 1)

```
s2 krok 1: [C06] symbol `InvoiceCalculator.RoundTotal` nie istnieje w indeksie
s1 krok 1: [C01] odpowiedz nie jest czystym obiektem JSON (prosa albo ogrodzenie ``` wokol)
s3 krok 2: [C11] plik Billing/Discounts.cs poza zakresem triazu ['Billing/Money.cs']
s4 krok 3: [C14] diff zmienia Billing.Check/Program.cs - Billing.Check jest tylko do odczytu
s5 krok 3: [C16] git apply --check: error: patch failed: Billing/Money.cs:5
```

(Nagłówek `sN krok K:` dopisany tu dla czytelności; skrypt wypisuje tylko linię `[Cxx] ...` i
`WYNIK: NARUSZENIA: 1`.)

### `chain.py run`

```
s0_good  (z kontraktami): accepted=True stage=- calls=3 detail=WSZYSTKO OK
s6_wrong_fix (z kontraktami): accepted=False stage=bramka calls=3 detail=BLEDY: 1
```

(`run` wypisuje `accepted=... stage=... calls=... detail=...`; nawias dopisany tu.)

### `test_chain.py` (exit 0)

```
id                 prawda   kontrakty              wywolan  baseline               opis
s0_good            dobra    ZIELONE                3/3      ZIELONE                poprawny przebieg
s1_fenced_json     dobra    odrzucone: krok 1      1/3      ZIELONE                tresc dobra, JSON w ``` + prosa
s2_halluc_symbol   zla      odrzucone: krok 1      1/3      odrzucone: bramka      krok 1 zmysla InvoiceCalculator.RoundTotal
s3_scope_creep     zla      odrzucone: krok 2      2/3      ZIELONE                plan i diff dotykaja Discounts.cs
s4_test_tamper     zla      odrzucone: krok 3      3/3      ZIELONE                diff zmienia oczekiwania w Billing.Check
s5_bad_context     zla      odrzucone: krok 3      3/3      odrzucone: bramka      diff nie aplikuje sie (zly kontekst)
s6_wrong_fix       zla      odrzucone: bramka      3/3      odrzucone: bramka      poprawny format, zla poprawka (ToPositiveInfinity)

zgodnosc werdyktu z prawda: kontrakty 6/7, baseline 5/7
falszywe zielone (zla zmiana przyjeta): kontrakty 0, baseline 2
falszywe czerwone (dobra zmiana odrzucona): kontrakty 1, baseline 0
wywolania modelu na 5 zlych scenariuszach: kontrakty 12, baseline 15
niezgodnosci z oczekiwaniem: 0
```

Uwaga o `wywolan`: to liczba kroków wykonanych do odrzucenia (kontrakty/baseline); baseline zawsze robi 3.

## Co NIE jest zweryfikowane

- **Zachowanie jakiegokolwiek modelu** — żaden nie był uruchamiany; `fixtures/` to moja fabrykacja typowych awarii,
  a 6 z 7 scenariuszy i reguły C10/C11/C14 powstały razem (wynik zawyżony). Częstość takich awarii nieznana.
- Pętla naprawcza: prompt jest budowany, ale nie ponawiany, a skuteczność nieznana; limit „2 próby" umowny.
- Prompty z `prompts/` nie są lintowane (jak w #17); placeholdery wypełnia skrypt.
- Indeks symboli to regexy (brak atrybutów, `partial`, przeciążeń, typów zagnieżdżonych); 3 pliki.
- Bramka zachowania ma 6 przypadków — poprawka spełniająca je, ale błędna poza nimi, przejdzie wszystko.
- Wyjaśnienie, dlaczego `git apply` odrzucił hunk z jedną linią kontekstu przed zmianą i zerem po (kotwiczenie
  do końca pliku), to moja interpretacja — nie sprawdzałem w źródłach gita.
- Koszt tokenowy łańcucha vs jeden prompt — nie mierzony.
