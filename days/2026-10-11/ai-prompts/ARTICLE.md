<div align="center">

# 📰 TECH PRASÓWKA
### Wydanie #18 — 11 października 2026

![AI](https://img.shields.io/badge/AI_%2F_Prompty-D97757?style=for-the-badge&logo=anthropic&logoColor=white)
![.NET](https://img.shields.io/badge/.NET_10-512BD4?style=for-the-badge&logo=dotnet&logoColor=white)
![Python](https://img.shields.io/badge/kontrakty-Python_stdlib-3776AB?style=for-the-badge&logo=python&logoColor=white)

## Jeden wielki prompt vs łańcuch trzech: kontrakt między krokami, który odrzuca zmyślone symbole, rozrost zakresu i „naprawione" testy

</div>

---

> _"Prompt „napraw i upewnij się, że testy przechodzą" ma jedno kryterium sukcesu: zielone testy.
> Zielone testy da się dostać na dwa sposoby, a model nie ma powodu preferować tego trudniejszego."_

Poprzednio w tej rubryce: [#17 - dokumentacja z walidatorem](../../2026-10-10/ai-prompts/ARTICLE.md).
Tam kończyło się zapowiedzią: „łańcuch promptów z kontraktem między krokami, uruchamiany end-to-end".
Dziś go mamy - w wersji, w której **sam łańcuch jest prawdziwy i uruchomiony, a model zastąpiony
nagraniami**. Nie omawiam tu ponownie XML-doc, README ani testów mutacyjnych.

**🎯 Dlaczego to ważne:** jeden długi prompt „zrób całą robotę" ma wszystkie błędy naraz i **żadnego punktu,
w którym da się je złapać tanio**. Rozbijasz na kroki, ale bez kontraktu to tylko trzy razy dłuższy czat:
zmyślony symbol z kroku 1 dojeżdża do kroku 3 jako „fakt". Kontrakt to wąski, maszynowo sprawdzalny format
wyniku każdego kroku **plus reguły, które skrypt sprawdza, zanim wynik trafi do następnego promptu**.

> ⚠️ **Uczciwie na starcie: żaden model nie był uruchamiany.** Siedem „odpowiedzi modelu" w
> [`code/fixtures/`](code/fixtures/) **napisałem ręcznie** - sześć z nich to fabrykacja typowych awarii
> (zmyślony symbol, rozrost zakresu, dopisana prosa, podmieniony test). Nie wiem, jak często prawdziwy model
> tak się myli. Mierzę **łańcuch i jego kontrakty**, nie model.

---

### 1️⃣ Zadanie i kod

[`code/Billing/`](code/Billing/) (.NET 10, zero pakietów): `Money.Round`, `InvoiceCalculator`, `Discounts`.
Prawdziwy błąd: `Math.Round(amount, 2)` zaokrągla połówki do parzystej (*banker's rounding*), a księgowość
chce „od zera". [`code/Billing.Check/`](code/Billing.Check/) to 6 przypadków, uruchamianych przed poprawką:

```
OK   Round(2.675): 2.68 (oczekiwano 2.68)
FAIL Round(2.665): 2.66 (oczekiwano 2.67)
FAIL Round(0.125): 0.12 (oczekiwano 0.13)
FAIL Round(-0.125): -0.12 (oczekiwano -0.13)
FAIL LineTotal(3 x 0.835): 2.50 (oczekiwano 2.51)
FAIL Total(2 x 0.125 + 10.00, rabat 10%): 9.23 (oczekiwano 9.22)
BLEDY: 5
```

Pierwszy przypadek (2.675) przechodzi przed poprawką i po niej - to kontrola, że nie „naprawiamy wszystkiego".

---

### 2️⃣ Zły prompt vs łańcuch

> ❌ [`prompts/mega_bad.txt`](code/prompts/mega_bad.txt): _„Napraw błąd z zaokrągleniem kwot w bibliotece Billing
> (faktura wychodzi o grosz za mało) i upewnij się, że testy przechodzą. Zrób to porządnie i zwróć gotową zmianę."_

| Co w nim jest | Dlaczego boli |
|---|---|
| „upewnij się, że testy przechodzą" | kryterium = kolor, nie zachowanie; **edycja oczekiwań w teście też daje zielone** (scenariusz S4 niżej) |
| brak zakresu | „porządnie" zaprasza do sprzątania sąsiednich plików (S3) |
| brak listy dozwolonych nazw | model uzupełnia API z „typowych" bibliotek: `RoundTotal` brzmi przekonująco (S2) |
| „gotowa zmiana" bez formatu | prosa, ogrodzenia ```, diff z obciętym kontekstem |

✅ Łańcuch z [`code/prompts/`](code/prompts/): trzy szablony, w których **skrypt wkleja fakty**, a wynik każdego
kroku przechodzi walidator, zanim stanie się wejściem następnego.

| Krok | Wejście (ze skryptu) | Wyjście | Kontrakt (reguły `C..`) |
|---|---|---|---|
| 1 triaż | zgłoszenie + **indeks symboli** | JSON: `symptom`, `suspects`, `unknowns` | czysty JSON (C01), klucze (C02), symptom cytuje liczbę ze zgłoszenia (C04), symbol **istnieje** i jest w tym pliku (C06/C07) |
| 2 plan | zwalidowany JSON z kroku 1 + źródła *tylko podejrzanych* plików | JSON: `changes`, `test`, `out_of_scope` | plik ∈ pliki z triażu (C11), nie `Billing.Check` (C10), 1-2 zmiany (C09) |
| 3 patch | zwalidowany plan + treść plików z planu | diff unified | czysty diff (C13), pliki ∈ plan (C15), nie `Billing.Check` (C14), ≤ 10 linii (C17), `git apply --check` (C16) |
| bramka | - | kod wyjścia `dotnet run --project Billing.Check` | to jedyne kryterium *zachowania* |

Cztery decyzje projektowe, które robią robotę - każda ma wersję „zły → dobry":

1. **Wejście kroku N+1 to wyjście kroku N po walidacji, nie surowa odpowiedź.** Model w kroku 2 nie widzi
   prozy z kroku 1, widzi JSON, który przeszedł reguły. Zmyślony symbol nie ma jak przeciec.
2. **Kryterium akceptacji jest tylko do odczytu *w kontrakcie*, nie w prośbie.** „Nie zmieniaj testów" w prompcie
   to życzenie; reguły C10/C14 to sprawdzenie ścieżek w diffie.
3. **Błąd walidatora wraca do modelu jako lista reguł**, nie „coś jest nie tak". Prompt naprawczy buduje skrypt
   ([`prompts/repair.txt`](code/prompts/repair.txt)); prawdziwy output dla S2:
   ```
   Twoja poprzednia odpowiedz w kroku 1 narusza kontrakt. Wyniki walidatora
   (kazdy punkt to konkretna regula, nie opinia):
   - C06 symbol `InvoiceCalculator.RoundTotal` nie istnieje w indeksie
   ...
   Popraw WYLACZNIE wskazane naruszenia. Nie zmieniaj tego, co przeszlo walidacje.
   ```
   Nie wiem, czy prawdziwy model zareaguje na taki prompt poprawnie - tej pętli nie uruchamiałem
   (skrypt tylko buduje prompt, `chain.py` nie ponawia wywołań).
4. **„Nie wiem" ma miejsce w formacie** (`unknowns`). Bez niego model, któremu kazano zwrócić `suspects`,
   zwróci cokolwiek.

---

### 3️⃣ Zmierzone: łańcuch z kontraktami vs ten sam łańcuch bez

[`code/test_chain.py`](code/test_chain.py) puszcza 7 nagrań przez **dwa tryby**: z kontraktami oraz „baseline" -
te same trzy kroki, ale wyniki przechodzą dalej bez walidacji (JSON wyciągany z prozy, diff z ogrodzenia),
a jedyną weryfikacją jest bramka końcowa (`git apply` + `Billing.Check`). Prawdziwy output
(.NET 10.0.400, Python 3.10.4, git):

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
```

| Metryka | Kontrakty | Baseline | Komentarz |
|---|---|---|---|
| ✅ Fałszywe zielone | **0** | **2** | S3 (rozrost zakresu) i S4 (przerobiony test) przechodzą bramkę baseline'u - `Billing.Check` jest zielony |
| ❌ Fałszywe czerwone | 1 | 0 | S1: treść dobra, ale JSON w ```` ``` ```` - ścisły kontrakt odrzuca; to realny koszt |
| 🔁 Zmarnowane wywołania (5 złych) | 12 | 15 | zysk skromny: S4-S6 wychodzą dopiero w kroku 3 w obu trybach |

Trzy rzeczy, które z tego wynikają:

- **S4 to „zielone, bo zmieniono oczekiwania"**: baseline zaakceptował diff, który nie dotyka kodu produkcyjnego,
  a przepisał pięć wartości w `Billing.Check` na te, które daje błąd. Bramka „testy przechodzą" jest wtedy
  *prawdziwa i bezwartościowa*. To dokładnie ten scenariusz, który zły prompt (`upewnij się, że testy przechodzą`)
  zaprasza.
- **S6 pokazuje granicę**: `ToPositiveInfinity` ma dobry format i mieści się w zakresie; przechodzi wszystkie
  kontrakty i odpada dopiero w bramce końcowej (`BLEDY: 1` - przypadek `Round(-0.125)`). Kontrakty nie rozumieją
  *poprawności*, więc **bramka zachowania zostaje niezbędna**, a jej siła = siła przypadków w `Billing.Check`.
- **Kontrakt strukturalny jest drogi tam, gdzie jest sztywny** (S1). Alternatywa: tolerować ogrodzenie ``` w kroku
  1 (tak robi tryb baseline) i zostawić resztę reguł - to decyzja o tym, czy pętla naprawcza „kosztuje" więcej niż
  fałszywy alarm. Nie mierzyłem, ile to kosztuje z prawdziwym modelem.

Mała pułapka z praktyki: mój pierwszy diff dla S4 (wersja z pustym wierszem zamiast `" "` jako kontekstem)
zgłosił `error: corrupt patch`, a kolejna próba - z jedną linią kontekstu przed zmianą i zerem po - `patch failed`
(wygląda na to, że git kotwiczy takie hunki do końca pliku; to moja interpretacja, nie sprawdzałem w źródłach
gita). Obie wersje są realistycznymi błędami w diffach generowanych przez LLM-y i obie łapie reguła C16 -
bez modelu, samym `git apply --check`.

---

### 4️⃣ Czego to nie dowodzi

> - **Żaden model nie był uruchamiany.** Nagrania to moja fabrykacja typowych awarii; częstość i rodzaj
>   awarii prawdziwego modelu nieznane. „0 fałszywych zielonych" dotyczy 7 scenariuszy, które sam wymyśliłem
>   **razem z regułami** (C10/C14/C11 powstały, bo napisałem S3/S4) - wynik jest zawyżony.
> - Nie sprawdziłem pętli naprawczej: `chain.py` buduje prompt naprawczy, ale nie ponawia wywołań i nie liczy,
>   ile prób potrzeba. Limit „2 próby" w szablonie to liczba umowna.
> - Indeks symboli to regexy po `.cs` (nie Roslyn): nie widzi atrybutów, `partial`, przeciążeń (dwie metody o tej
>   samej nazwie to jeden symbol), typów zagnieżdżonych. Działa na 3 plikach.
> - Bramka końcowa ma 6 przypadków; błędna poprawka, która je spełnia, przejdzie wszystkie kontrakty i bramkę.
> - Nie mierzyłem kosztu tokenowego (liczba wywołań to tylko liczba; kroki 2-3 dostają mniej kontekstu niż
>   jeden mega-prompt, ale nie liczyłem, o ile).
> - Brak porównania z jednym promptem uruchomionym na prawdziwym modelu: „łańcuch jest lepszy niż mega-prompt" to
>   hipoteza uzasadniona *konstrukcją* (punkty kontrolne), nie pomiarem jakości.
> - Brak narzędzi agentowych: tu każdy krok to jedno wywołanie bez dostępu do repo; w Claude Code model sam
>   czyta pliki i uruchamia testy, więc część scenariuszy (np. zmyślony symbol) wystąpi rzadziej.

---

## Wspólny mianownik

Kroki łańcucha są tak dobre, jak **sprawdzenia na granicach**: tożsamość bytów (symbol istnieje), zakres (plik
z planu), nietykalność kryterium (testy tylko do odczytu) i zachowanie (bramka). Prompt mówi modelowi, czego
chcesz; kontrakt sprawdza, czy to dostałeś - zanim trafi do następnego kroku. Bez kontraktu rozbicie na kroki
tylko rozmywa odpowiedzialność.

---

## 📎 Jak zweryfikować

Zobacz [`code/README.md`](code/README.md) - komendy i prawdziwy output.

---

<div align="center">

[← wróć do wydania #18 (wszystkie rubryki)](../README.md) · [spis wydań](../../README.md)

</div>
