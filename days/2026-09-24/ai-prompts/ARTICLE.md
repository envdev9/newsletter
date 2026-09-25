<div align="center">

# 📰 TECH PRASÓWKA
### Wydanie #1 — 24 września 2026

![AI](https://img.shields.io/badge/AI_%2F_Claude_Code-D97757?style=for-the-badge&logo=anthropic&logoColor=white)

## Zły i dobry prompt obok siebie: 5 par z komentarzem, dlaczego jeden działa, a drugi nie

</div>

---

> _"Model nie czyta w myślach - czyta dokładnie to, co napisałeś. Jeśli w prompcie
> jest miejsce na dwie interpretacje, dostaniesz jedną z nich, i nie masz gwarancji,
> że tę właściwą."_

Dobry prompt dla asystenta kodu to nie kwestia "uprzejmości" ani magicznych słów -
to inżynieria wymagań w miniaturze. Ten sam brak konkretów, który w specyfikacji dla
człowieka kończy się serią pytań wyjaśniających, w prompcie dla modelu kończy się
**cichym** podjęciem decyzji za ciebie - i dowiadujesz się o tym dopiero, patrząc na
diff. Poniżej 5 par zły/dobry prompt, każda z jedną konkretną przyczyną, dlaczego
druga wersja działa lepiej. Wszystkie pary są w [`code/examples.yaml`](code/examples.yaml),
zwalidowane i wypisane skryptem [`code/print_examples.py`](code/print_examples.py) -
prawdziwy output w [`code/README.md`](code/README.md).

---

### 1️⃣ Konkretność + wskazanie plików/linii

❌ **Zły:** _"Popraw bug w serwisie userów."_

✅ **Dobry:** _"W `src/Services/UserService.cs`, metoda `GetActiveUsersAsync`
(linie 42-58) zwraca też użytkowników z `IsDeleted=true`, bo w zapytaniu LINQ
brakuje warunku. Dodaj `.Where(u => !u.IsDeleted)` przed `.ToListAsync()` i
pokaż diff."_

**Dlaczego:** "Serwis userów" i "bug" to dwie niewiadome naraz - model musi
najpierw przeszukać repo i zgadnąć, o który plik i o jaki objaw chodzi. Podanie
pliku, zakresu linii i dokładnego objawu zamienia zadanie z detektywistycznego w
wykonawcze - jedno przejście, bez rundy pytań.

---

### 2️⃣ Podawanie "dlaczego", nie tylko "co"

❌ **Zły:** _"Zmień timeout w HttpClient na 30 sekund."_

✅ **Dobry:** _"Zwiększ timeout HttpClient w `OrderApiClient.cs` z 10s na 30s -
integracja z API dostawcy potrafi odpowiadać 15-20s przy dużych zamówieniach,
obecny timeout powoduje false-positive `TimeoutException` na produkcji. Zmień
tylko dla tego klienta, nie globalnie w `Program.cs`."_

**Dlaczego:** Sama liczba bez przyczyny zamienia model w maszynkę do
znajdź-i-zamień - nie może ocenić, czy 30s to bezpieczna wartość, czy lepszym
rozwiązaniem byłaby retry policy zamiast samego zwiększenia timeoutu. Przyczyna
daje modelowi dane do podjęcia *właściwej* decyzji, nie tylko wykonania polecenia
dosłownie.

---

### 3️⃣ Unikanie niejednoznaczności

❌ **Zły:** _"Dodaj walidację do formularza rejestracji."_

✅ **Dobry:** _"Dodaj walidatory Angular Reactive Forms do `RegisterComponent`:
email - `Validators.required` + `Validators.email`; hasło - min. 8 znaków, 1
cyfra, 1 znak specjalny; potwierdzenie hasła zgodne z polem hasło. Błędy pokazuj
w `<mat-error>` po utracie fokusu, nie przy każdym keystroke."_

**Dlaczego:** Słowo "walidacja" samo w sobie zostawia dziesiątki otwartych
decyzji (jakie reguły, kiedy pokazać błąd). Model wybierze coś swojego - zwykle
innego niż to, co miałeś na myśli - i kończy się to przeróbką. Wypisanie reguł i
zachowania UX z góry eliminuje zgadywanie po obu stronach.

---

### 4️⃣ Oczekiwany format odpowiedzi

❌ **Zły:** _"Sprawdź te trzy zapytania SQL pod kątem wydajności."_

✅ **Dobry:** _"Przeanalizuj wydajność 3 zapytań w `queries.sql` pod kątem:
brakujących indeksów, seek vs scan, N+1. Odpowiedz w formacie tabeli Markdown z
kolumnami: Zapytanie | Problem | Sugerowany indeks/fix | Szacowany wpływ. Nie
przepisuj pełnych zapytań, tylko numer z pliku."_

**Dlaczego:** Bez narzuconego formatu odpowiedź wychodzi jako luźna proza, którą
trzeba ręcznie przepisać do ticketu albo PR-a. Konkretne kolumny + limit
długości dają odpowiedź gotową do wklejenia od razu.

---

### 5️⃣ Zakres zmiany i granice (co WOLNO, a czego NIE)

❌ **Zły:** _"Zrefaktoryzuj `OrderService`, żeby był czytelniejszy."_

✅ **Dobry:** _"W `OrderService.cs` wydziel logikę liczenia rabatu (linie
80-120) do osobnej klasy `DiscountCalculator`, wstrzykiwanej jako
`IDiscountCalculator`. Nie zmieniaj publicznego API `OrderService` (używane w 6
innych miejscach) i nie dotykaj `OrderServiceTests.cs` poza dodaniem mocka."_

**Dlaczego:** "Czytelniejszy" jest subiektywne i bez granic - model może
przeprojektować połowę klasy i zepsuć miejsca wywołania, których nie widział w
danym momencie kontekstu. Zakres (co wydzielić) i twarde granice (czego nie
ruszać) ograniczają refaktor do bezpiecznego, przewidywalnego kroku.

---

## Wspólny mianownik

Wszystkie pięć "dobrych" promptów robi to samo: **zamienia domysł w fakt**. Plik
zamiast "gdzieś w kodzie", linie zamiast "ta metoda", przyczyna zamiast gołej
instrukcji, format zamiast "jakoś to podaj", granice zamiast "zrób to ładnie". Im
mniej model musi zgadywać, tym mniejsza szansa, że jego pierwsza próba to nie to,
czego potrzebowałeś.

---

## 📎 Jak zweryfikować przykłady z tego wydania

Zobacz [`code/README.md`](code/README.md) — dokładne komendy i prawdziwy output
skryptu walidującego/wypisującego przykłady.

---

<div align="center">

[← wróć do wydania #1 (wszystkie rubryki)](../README.md) · [spis wydań](../../README.md)

</div>
