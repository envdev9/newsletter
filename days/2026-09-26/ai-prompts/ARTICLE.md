<div align="center">

# 📰 TECH PRASÓWKA
### Wydanie #3 — 26 września 2026

![AI](https://img.shields.io/badge/AI_%2F_Prompty-D97757?style=for-the-badge&logo=anthropic&logoColor=white)

## Prompt do debugowania i code review: wklej dowód, poproś o hipotezy, zdefiniuj skalę uwag

</div>

---

> _"Kiedy każesz modelowi „naprawić błąd", każesz mu zgadywać. Kiedy dajesz mu stack
> trace i prosisz o hipotezy, każesz mu rozumować."_

W [poprzednim artykule tej rubryki](../../2026-09-24/ai-prompts/ARTICLE.md) było 5 ogólnych
zasad (plik/linia, „dlaczego", brak dwuznaczności, format, granice). Dziś dwa zadania,
przy których zły prompt kosztuje najwięcej: **debugowanie** i **code review**, oraz
trzecia umiejętność: **dopracowywanie promptu w trakcie sesji**, zamiast pisać od nowa.
Na koniec skrypt, który wyłapuje typowe braki w promptach - z uczciwym zastrzeżeniem, czego
nie dowodzi.

---

### 1️⃣ Debugowanie .NET: stack trace + warunki odtworzenia + hipotezy PRZED poprawką

❌ **Zły:** _"Endpoint zamówień czasem wywala 500, napraw to."_

✅ **Dobry** (skrót; pełny tekst w [`code/prompts/debug_dotnet_good.txt`](code/prompts/debug_dotnet_good.txt)):
_"POST /api/orders zwraca 500. Stack trace: `NullReferenceException ... at OrderService.ApplyDiscount ... OrderService.cs:line 87`.
Występuje tylko przy wygasłym kodzie rabatowym, od commita „Discounts v2". **Zanim cokolwiek
zmienisz:** podaj 3 hipotezy uszeregowane od najbardziej prawdopodobnej i jak każdą
sprawdzić. Sukces: nowy test z wygasłym kodem przechodzi (`dotnet test --filter ...`).
Odpowiedz: lista hipotez, potem diff. Nie zmieniaj publicznego API."_

**Dlaczego to ważne:**
- **Dowód zamiast opisu.** „Czasem wywala 500" niesie zero informacji; stack trace wskazuje
  plik i linię. Wklejaj go w bloku kodu, dosłownie - własne streszczenie błędu gubi
  szczegóły (nazwę wyjątku, wewnętrzny `InnerException`), na których model oprze diagnozę.
- **Warunki odtworzenia** („tylko przy wygasłym kuponie") zawężają przestrzeń przyczyn
  bardziej niż jakakolwiek analiza kodu. Jeśli nie umiesz odtworzyć - napisz to, model
  wtedy zaproponuje minimalny repro (np. test jednostkowy), zamiast udawać pewność.
- **Hipotezy przed poprawką.** Model, który od razu edytuje, leczy pierwszy objaw, jaki
  znajdzie (np. dopisze `?.` i „naprawi" wyjątek, chowając prawdziwy błąd: rabat nie jest
  liczony). Prośba o uszeregowane hipotezy + sposób sprawdzenia daje ci punkt kontrolny:
  możesz odrzucić złą hipotezę zanim powstanie diff.

---

### 2️⃣ Debugowanie SQL: dane z planu wykonania zamiast „jest wolne"

❌ **Zły:** _"Zapytanie o raport sprzedaży jest wolne, zoptymalizuj je."_

✅ **Dobry** ([`debug_sql_good.txt`](code/prompts/debug_sql_good.txt)): plik i linie
zapytania, rozmiar tabeli, wycinek `SET STATISTICS IO` / planu (Estimated 3 vs Actual
412009 wierszy), kiedy występuje (szeroki zakres dat), prośba o 2 hipotezy z zapytaniem
diagnostycznym do każdej, mierzalny sukces („logical reads poniżej 5000, ta sama liczba
wierszy") i zakaz zmiany schematu.

**Dlaczego to ważne:** „zoptymalizuj" bez liczb to zaproszenie do wklejenia losowego
indeksu. Rozjazd estymacji (3 vs 412009) sugeruje statystyki lub parameter sniffing -
inną klasę problemu niż brak indeksu. Kryterium **„ta sama liczba wierszy"** chroni przed
„optymalizacją", która przyspiesza, bo zwraca mniej danych.

---

### 3️⃣ Code review: skala ważności i „czego nie komentować"

❌ **Zły:** _"Zrób code review tego komponentu i powiedz, co o nim sądzisz."_

✅ **Dobry** ([`review_angular_good.txt`](code/prompts/review_angular_good.txt)): konkretne
pliki (`order-list.component.ts` + `.html`, diff względem `main`), lista tego, czego
szukać (wycieki subskrypcji RxJS, wywołania w szablonie przy każdym cyklu detekcji,
obsługa null), **skala wag** (krytyczne / ważne / nit), limit nitów, format tabeli
`Plik:linia | Waga | Problem | Poprawka` i zakaz komentowania formatowania i nazw.

**Dlaczego to ważne:** bez skali dostajesz 25 równorzędnych uwag i musisz sam odsiać 2
istotne od 23 kosmetycznych. Bez „czego nie komentować" model chętnie zajmie się
stylem, bo to najłatwiejsze do wygenerowania. `Plik:linia` w kolumnie sprawia, że każdą
uwagę da się zweryfikować w 5 sekund - a **weryfikować trzeba**: model potrafi zgłosić
problem, którego w kodzie nie ma.

---

### 4️⃣ Iteracja: nie pisz od nowa, dokładaj brakujący element

Realny przebieg pracy to nie „jeden idealny prompt", tylko 2-3 tury. Trzy wersje tego samego
zadania (test, który pada tylko na CI) są w `code/prompts/iter_*`:

| Wersja | Co dodano | Wynik lintu |
|---|---|---|
| `iter_1` | „Test ... czasem pada, popraw." | 0/9 |
| `iter_2` | nazwa pliku, treść asercji, „pada tylko na CI" | 4/9 |
| `iter_3` | częstotliwość (co trzeci przebieg), hipoteza „zegar", prośba o hipotezy przed zmianą, kryterium (20 razy zielony), format, zakaz ruszania kodu produkcyjnego | 9/9 |

**Dlaczego to ważne:** każda kolejna wersja dodaje **jedną kategorię informacji, której
model nie mógł znać**, zamiast przepisywać całość innymi słowami. Praktyczna reguła w
trakcie sesji: gdy odpowiedź jest zła, zapytaj najpierw *czego modelowi zabrakło* (nie
„jak go zmusić"), i dopisz właśnie to. Jeśli sesja jest już długa i pełna nieudanych prób,
lepiej zacząć nową z dopracowanym promptem niż kontynuować (zobacz rubrykę o zarządzaniu
kontekstem).

---

### 5️⃣ Lint promptów - i czego NIE dowodzi

[`code/prompt_lint.py`](code/prompt_lint.py) (czysty Python, stdlib) sprawdza prompt regułami:
plik, linia, dowód błędu, warunki odtworzenia, prośba o hipotezy, kryterium sukcesu, format,
zakres (dla review: kryteria przeglądu i skala ważności). Uruchomiony na 9 plikach z
[`code/prompts/`](code/prompts/) daje **9/9 zgodnych wyników** (złe oblane, dobre zaliczone),
a test negatywny - dobry prompt z wyciętym stack tracem i prośbą o hipotezy - jest
wykryty (7/9, exit 1). Prawdziwy output: [`code/README.md`](code/README.md).

> ⚠️ **Niezweryfikowane i wprost zastrzeżone:** to heurystyka regexowa. Sprawdza, czy w
> prompcie *są* słowa-klucze, nie czy są *sensowne*. Nie testowałem, czy prompty „dobre"
> według lintu dają lepsze odpowiedzi jakiegokolwiek modelu - nie uruchamiałem żadnego
> modelu w tym wydaniu. Przykłady kodu w promptach (`OrderService`, tabele) są
> ilustracyjne, nie pochodzą z prawdziwego projektu. Reguły dobrałem pod własne przykłady,
> więc 9/9 to test spójności skryptu, nie dowód jego skuteczności na cudzych promptach.

---

## Wspólny mianownik

Artykuł #1 mówił: „zamień domysł w fakt". Ten dodaje: **przy debugowaniu daj dowody i
zażądaj hipotez, przy review daj skalę i granice, a przy poprawkach dokładaj brakującą
informację zamiast przepisywać.**

---

## 📎 Jak zweryfikować

Zobacz [`code/README.md`](code/README.md) - komendy i prawdziwy output.

---

<div align="center">

[← wróć do wydania #3 (wszystkie rubryki)](../README.md) · [spis wydań](../../README.md)

</div>
