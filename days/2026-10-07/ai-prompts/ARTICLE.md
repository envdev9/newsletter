<div align="center">

# 📰 TECH PRASÓWKA
### Wydanie #14 — 7 października 2026

![AI](https://img.shields.io/badge/AI_%2F_Prompty-D97757?style=for-the-badge&logo=anthropic&logoColor=white)
![.NET](https://img.shields.io/badge/.NET_10-512BD4?style=for-the-badge&logo=dotnet&logoColor=white)
![TUnit](https://img.shields.io/badge/TUnit-1.72.16-2E7D32?style=for-the-badge)

## „Napisz testy" to za mało: prompty do generowania testów, które sprawdzamy mutacjami

</div>

---

> _"Zielone testy wygenerowane przez model dowodzą tylko tego, że model napisał testy, które przechodzą.
> Czy wykryłyby błąd - to osobne pytanie. Da się je zadać kodem."_

Poprzednie artykuły tej rubryki: [#1 - pięć zasad](../../2026-09-24/ai-prompts/ARTICLE.md),
[#3 - debugowanie i review](../../2026-09-26/ai-prompts/ARTICLE.md),
[#4 - refaktoryzacja, migracja, few-shot, CLAUDE.md](../../2026-09-27/ai-prompts/ARTICLE.md).
W #4 padło zdanie „najpierw zbuduj sposób sprawdzenia". Dziś przypadek, w którym
**testy są tym sposobem sprawdzenia** - więc jakość promptu generującego testy to jakość
całej siatki bezpieczeństwa.

**🎯 Dlaczego to ważne:** model z promptem „napisz testy" chętnie odda pięć zielonych testów
ścieżki szczęśliwej i `Assert.NotNull`. Pokrycie linii pokaże wysokie, CI będzie zielone, a
zmiana `<=` na `<` na granicy miesiąca przejdzie niezauważona. Tu pokazuję, jak to
**zmierzyć** (testem mutacyjnym) i jak sformułować prompt, który tych dziur nie robi.

> ⚠️ **Uczciwie na starcie: żaden model nie był uruchamiany.** Oba zestawy testów w tym
> wydaniu napisałem **ja, ręcznie**: „naiwny" naśladuje typowy wynik promptu „napisz testy",
> „dobry" realizuje listę z dobrego promptu. To **nie jest zmierzony output modelu** - mierzę
> tu *jak dobrze testy łapią błędy*, a nie *czy model z danym promptem napisze takie testy*.

---

### 1️⃣ Kod pod testami: mały, ale z prawdziwymi brzegami

[`code/Billing/Prorator.cs`](code/Billing/Prorator.cs) (.NET 10, zero pakietów) ma dwie metody:

| Metoda | Kontrakt (z XML-doc) | Gdzie są pułapki |
|---|---|---|
| `Charge(price, year, month, activation)` | aktywacja w 1. dniu = pełna cena; po ostatnim = 0; inaczej cena × dni *włącznie* / dni w miesiącu, `AwayFromZero` do groszy; cena ujemna → `ArgumentOutOfRangeException` | ostatni dzień, luty (przestępny), połówka grosza, `+ 1` we wzorze |
| `Split(total, parts)` | suma == kwota co do grosza, reszta po 1 gr do **pierwszych** pozycji; `parts <= 0` / kwota < 0 → `ArgumentOutOfRangeException`; > 2 miejsc → `ArgumentException` | kontrakt „komu reszta", typy wyjątków |

---

### 2️⃣ Zły prompt vs dobry prompt

❌ **Zły** ([`prompts/tests_bad.txt`](code/prompts/tests_bad.txt)), cały tekst:
_"Napisz testy jednostkowe dla klasy Prorator."_

✅ **Dobry** (skrót; pełny tekst: [`prompts/tests_good.txt`](code/prompts/tests_good.txt)):
_"Plik `Billing/Prorator.cs`, metody `Charge` i `Split`; TUnit; `dotnet run --project Billing.GoodTests`.
**KONTRAKT** (testuj specyfikację, nie implementację): … **PRZYPADKI BRZEGOWE**: 1. dzień, OSTATNI dzień,
dzień po ostatnim, luty przestępny, połówka grosza, cena 0, ujemna … **WŁAŚCIWOŚCI** na stałym ziarnie,
min. 1000 iteracji … **ZAKAZY**: bez słabych asercji, bez zmiany kodu produkcyjnego, oczekiwanie liczone ręcznie.
**WERYFIKACJA**: zmień operator i sprawdź, że test czerwieni się. **FORMAT**: jeden plik."_

| Element promptu | Dlaczego |
|---|---|
| 📜 **Kontrakt wpisany w prompt** | Bez niego model wyprowadza „oczekiwane" z implementacji - a wtedy test przepisuje błąd kodu jako wzorzec. Ten sam mechanizm co „testy charakteryzujące" z #4, tylko tu chcemy testować *zamierzone* zachowanie. |
| 🎯 **Lista kategorii brzegów** | Model zna pojęcie „edge case", ale nie wie, które są *tu* groźne. Wymień: ostatni dzień, rok przestępny, połówka grosza. |
| 🧾 **Typy wyjątków z nazwy** | „Sprawdź błędy" daje `Throws<Exception>` albo nic; `ArgumentOutOfRangeException` vs `DivideByZeroException` to różnica, którą wykrywa mutant M11 (niżej). |
| 🎲 **Właściwości + ziarno + liczba iteracji** | Test właściwości bez ziarna jest niepowtarzalny, bez liczby iteracji - model da 3. „Bez nowych pakietów" - inaczej doda FsCheck, którego nie masz w projekcie. |
| 🚫 **Zakaz słabych asercji z przykładem** | `IsNotNull` i `Count == 3` to asercje, które przechodzą dla prawie każdej implementacji. |
| ✋ **„Nie zmieniaj kodu produkcyjnego"** | Inaczej na niezgodność z kontraktem model „naprawi" kod pod swój test - zamiast ją zgłosić. |
| 🔴 **Weryfikacja przez zmianę operatora** | Zamienia „napisałem testy" w „sprawdziłem, że testy coś łapią". To ręczna wersja tego, co niżej robi skrypt. |

---

### 3️⃣ Zmierzone: ile mutantów łapie każdy zestaw

[`code/mutate.py`](code/mutate.py) kopiuje projekt do `/tmp`, podmienia **jeden fragment** `Prorator.cs`
(14 mutantów: `<=`→`<`, usunięte `+ 1`, `AwayFromZero`→`ToEven`, 30 dni zamiast `DaysInMonth`,
reszta groszy do ostatnich pozycji, osłabiona walidacja…) i uruchamia oba zestawy. Mutant „zabity" =
któryś test czerwony. Prawdziwy wynik (TUnit 1.72.16, .NET 10.0.400; baseline zielony: 5/5 i 24/24):

```
M01  naive=pass        good=pass        Charge: `activation <= first` -> `<` (aktywacja 1. dnia)
M02  naive=pass        good=fail        Charge: `activation > last` -> `>=` (ostatni dzien => 0)
M03  naive=fail        good=fail        Charge: usuniete `+ 1` (dni liczone wlacznie)
M04  naive=pass        good=fail        Charge: AwayFromZero -> ToEven
M05  naive=pass        good=fail        Charge: `monthlyPrice < 0` -> `<= 0` (cena 0 rzuca)
M06  naive=pass        good=fail        Charge: stala liczba dni 30 zamiast DaysInMonth
M07  naive=pass        good=fail        Charge: zaokraglenie do 3 miejsc zamiast 2
M08  naive=pass        good=pass        Charge: kolejnosc dzialan cena/dni*pozostale zamiast cena*pozostale/dni
M09  naive=fail        good=fail        Split: `i < rem` -> `i <= rem` (jedna pozycja z nadwyzka za duzo)
M10  naive=pass        good=fail        Split: reszta groszy do OSTATNICH pozycji zamiast pierwszych
M11  naive=pass        good=fail        Split: `parts <= 0` -> `parts < 0` (parts=0 => DivideByZero zamiast ArgumentOutOfRange)
M12  naive=pass        good=fail        Split: usunieta walidacja >2 miejsc po przecinku
M13  naive=pass        good=fail        Split: `total < 0` -> `total < -1000` (walidacja kwoty ujemnej oslabiona)
M14  naive=pass        good=fail        Split: `cents % parts` -> `cents % (parts + 1)` (zla reszta)

PODSUMOWANIE (mutanty niekompilowalne pominiete)
  Billing.NaiveTests: zabite 2/14 = 14%  przezyly: M01, M02, M04, M05, M06, M07, M08, M10, M11, M12, M13, M14
  Billing.GoodTests: zabite 12/14 = 86%  przezyly: M01, M08
```

| Zestaw | Testów | Zabite mutanty |
|---|---|---|
| ✍️ „naiwny" (ścieżka szczęśliwa, `Count`, `IsNotNull`) | 5 | **2/14 (14%)** |
| 🎯 „dobry" (tabela brzegów, wyjątki z typem, property, kontrakt) | 24 | **12/14 (86%)** |

**Co z tego wynika:**
- Naiwny zestaw jest **zielony i ma sensownie wyglądające nazwy**, a nie łapie nawet zmiany
  „ostatni dzień miesiąca = 0 zamiast 1/30" (M02) ani zaokrąglenia `ToEven` (M04).
- **M10 pokazuje, po co jest kontrakt w prompcie.** Testy właściwości (suma, rozrzut ≤ 1 gr) przechodzą,
  gdy reszta groszy trafia do *ostatnich* pozycji - kogo ona dotyczy, mówi tylko spec. Zabija go dopiero
  test przykładowy `Split(100, 3) == [33.34, 33.33, 33.33]`. Property tests **nie zastępują** przykładów.
- **Dwa przeżyte mutanty „dobrego" zestawu nie są (zapewne) dziurami:**
  M01 jest **równoważny** (dla 1. dnia wzór `cena × dni / dni` daje dokładnie `cena`, więc `<=`/`<` nie
  zmienia wyniku). M08 (inna kolejność mnożenia i dzielenia) **przeżył i uznaję go za praktycznie
  równoważny po zaokrągleniu do groszy** - ale tego **nie udowodniłem**; to hipoteza oparta na
  tym, że `decimal` ma 28 cyfr. Żaden z dwóch nie jest dowodem dziury w testach, ale oba wymagają decyzji człowieka.
  W prompcie dla modelu to właśnie klauzula „mutant równoważny: nie pisz testu, czekaj na decyzję".

> 💡 Skrypt `mutate.py` ma też `--survivors-out plik.md`: zapisuje przeżyte mutanty jako diffy,
> gotowe do wklejenia w `<mutants>…</mutants>` w prompcie z punktu 4. (Plik wygenerował się w
> `/tmp`, ale **odczyt go został odrzucony przez środowisko**, więc jego treści tu nie cytuję.)

---

### 4️⃣ Pętla zwrotna: raport mutacyjny jako dane do promptu

Drugi prompt ([`prompts/mutfix_good.txt`](code/prompts/mutfix_good.txt)) bierze raport przeżytych
mutantów i każe wzmocnić testy. Element po elemencie:

❌ **Zły** ([`mutfix_bad.txt`](code/prompts/mutfix_bad.txt)): _"Testy mają za niskie pokrycie, popraw je
i dodaj brakujące, żeby wszystko było przetestowane."_

✅ **Dobry:**
- raport w znaczniku `<mutants>` - **dane oddzielone od instrukcji**;
- **jeden mutant po kolei**: zdanie „co zmienił", jeden test, linia „zabija: Mxx" - recenzowalne;
- **kryterium testu**: zielony na oryginale, czerwony na zmutowanym (to da się sprawdzić ponownym
  uruchomieniem `mutate.py`, bez wiary modelowi na słowo);
- **mutant równoważny → bez testu, uzasadnienie i czekaj** (bez tego model napisze test, którego
  nie da się spełnić, albo naciągnie asercję);
- **zakaz zmiany kodu i osłabiania istniejących testów**;
- **„gotowe, gdy"** z konkretną komendą.

Dlaczego mutacje, a nie „pokrycie"? Pokrycie linii mówi, że kod *został wykonany*, nie że wynik został
*sprawdzony*. Naiwny zestaw wykonuje większość `Charge` i `Split`; sprawdza prawie nic.

---

### 5️⃣ Lint #3 - prompt vs kod, i czego NIE dowodzi

[`code/testprompt_lint.py`](code/testprompt_lint.py) (stdlib) ma 13 reguł dla promptów „tests_" i
9 dla „mutfix_". Nowość wobec lintów z poprzednich wydań: część reguł **sprawdza prompt względem kodu**:
czy wskazany plik `.cs` istnieje, czy projekt z `dotnet run --project` istnieje, czy wymienione metody
są w źródle, czy typy wyjątków z kontraktu są w `<exception cref>` XML-doc. Reszta to nadal regexy po słowach.

Samotest: **4/4 zgodnych** (`tests_bad` 0/13, `tests_good` 13/13, `mutfix_bad` 0/9, `mutfix_good` 9/9).
Test negatywny: prompt „pusty w środku" ([`negative/tests_hollow_good.txt`](code/negative/tests_hollow_good.txt) -
same hasła „edge cases, property, seed, TUnit", bez ścieżek, kontraktu i typów wyjątków) dostaje **2/13, FAIL, exit 1**.

> ⚠️ **To nie dowód skuteczności.** Reguły napisałem pod własne prompty i własny kod; łatwo je oszukać
> (wystarczy wkleić poprawną ścieżkę do pliku i słowa kluczowe). Że prompt zalicza lint, nie znaczy,
> że model napisze dobre testy - **tego nie sprawdzałem**.

---

### 6️⃣ Niezweryfikowane i wprost zastrzeżone

> - **Żaden model nie był uruchamiany.** Oba zestawy testów to mój ręczny kod. 14% vs 86% mówi o *testach*,
>   nie o *promptach*. Nie wiem, czy model z `tests_good.txt` napisze coś zbliżonego do `ProratorGoodTests.cs`,
>   ani czy z `tests_bad.txt` napisze coś zbliżonego do naiwnego zestawu.
> - 14 mutantów to **mój wybór**, nie pełny katalog operatorów (Stryker.NET, którego nie uruchamiałem, generuje ich
>   znacznie więcej). Wynik procentowy zależy od tej listy; naiwny zestaw pisałem, znając ją - to poważne
>   obciążenie na korzyść wniosku. Nie przeceniaj liczb, patrz na *które* mutanty uciekają i dlaczego.
> - M08 uznany za równoważny z domysłu (patrz wyżej).
> - Klasa `Prorator` jest sztuczna i mała; wnioski o skali (duże klasy, zależności, I/O) nie są sprawdzone.
> - Testy pisane przez model do kodu *z zależnościami* (mocki, baza) - poza zakresem.
> - Czasu wykonania mutacji nie mierzyłem precyzyjnie: każda para `dotnet run` + budowanie to rząd ~minuty
>   na mutanta w tym środowisku, całość to wielominutowy przebieg.
> - Dokumentacja (XML-doc, README, ADR) - **jeszcze nie omówiona**, zostaje na następny raz.
> - Uruchamiałem `dotnet run --project`, nie `dotnet test`: `dotnet test --project …` wymaga `global.json`
>   z runnerem Microsoft.Testing.Platform i uruchomienia z katalogu z tym plikiem, a ja nie mogłem zmienić
>   katalogu roboczego w poleceniu. Pierwsza próba `dotnet test --project` spoza tego katalogu
>   skończyła się `MSB1001: Unknown switch`.

---

## Wspólny mianownik

Poprzednio: „najpierw zbuduj sposób sprawdzenia". Dziś o oczko głębiej: **sprawdź samo sprawdzanie** -
prompt do testów powinien zawierać kontrakt, brzegi, zakazy słabych asercji i weryfikację zmianą kodu,
a jakość wyniku mierz mutacjami, nie pokryciem. Przeżyte mutanty karm z powrotem do modelu jako dane,
po jednym, z klauzulą „równoważny → zapytaj".

---

## 📎 Jak zweryfikować

Zobacz [`code/README.md`](code/README.md) - komendy i prawdziwy output.

---

<div align="center">

[← wróć do wydania #14 (wszystkie rubryki)](../README.md) · [spis wydań](../../README.md)

</div>
