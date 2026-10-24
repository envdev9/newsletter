<div align="center">

# 📰 TECH PRASÓWKA
### Wydanie #4 rubryki — 6 października 2026

![AI/Kontekst](https://img.shields.io/badge/AI_%2F_Kontekst-8A5CF6?style=for-the-badge&logo=anthropic&logoColor=white)
![Wyniki narzędzi](https://img.shields.io/badge/wyniki_narzędzi-kompresja-EF4444?style=for-the-badge)
![Budżet](https://img.shields.io/badge/budżet_kontekstu-jako_kod-0EA5E9?style=for-the-badge)

## Co dać modelowi do ręki, a czego nie: kompresja wyników narzędzi i budżet kontekstu jako kod

</div>

---

> _"Najdroższy błąd w kontekście to nie za długi wynik. To przycięcie wyniku w złym miejscu:
> model dostaje 600 tokenów i ani jednego z faktów, po które sięgnął."_

W [#2](../../2026-09-26/ai-context/ARTICLE.md) mierzyliśmy, **ile** kosztuje wynik narzędzia
(token-tury), w [#3](../../2026-09-27/ai-context/ARTICLE.md) - stałą bazę (`CLAUDE.md`, MCP).
Dziś trzecia dźwignia: **co dokładnie zostawić z wyniku, który i tak musi wejść**. Samo "mniej"
nie wystarcza - potrzebna jest druga oś: **czy fakty, na których zależy modelowi, przeżyły**.

**Hak: każda kompresja jest stratna, a strata jest niewidoczna dla modelu.** Model nie
dowie się, że przycięty log miał jeszcze jeden błąd. Dlatego kompresję trzeba oceniać
**dwiema liczbami naraz**: zyskiem w tokenach i **przeżywalnością faktów** ("igieł").

> ⚠️ **Uczciwie o danych.** Wszystko poniżej to dane **syntetyczne** generowane przez kod
> (stałe ziarno): log w stylu `dotnet build`/`test` i odpowiedź API ze 300 zamówieniami.
> Tokeny = bajty/4. **Żaden model nie był uruchamiany** - mierzę, co **zostaje w tekście**, nie
> jak model z tego skorzysta. Liczby ilustrują mechanizm, nie mierzą realnych logów. Odczyt
> `~/.claude/projects/` nadal odrzucony (nie obchodzę), a pobranie pracy naukowej o pozycji
> informacji w kontekście (WebFetch) **też zostało odrzucone** - sekcja 4 jest więc z pamięci.

---

## 1️⃣ Eksperyment: log z igłami w środku

Syntetyczny log: 2404 linii, ~53 041 tok. Tysiące powtarzalnych linii (`info`, `warning CS8618`,
`Restored ...`) i **4 igły**: błąd kompilacji (40% długości), padający test (55%),
migracja pominięta z powodu niezgodnego checksum (70% - **bez słów `error`/`fail`**) oraz
podsumowanie na końcu. Budżet na wynik: 600 tok. Prawdziwy output:

```
| strategia              |   ~tok | zysk   | igly |
|------------------------|-------:|-------:|------|
| surowy (nic)           |  53041 |    1.0x | 4/4 |
| head                   |    600 |   88.4x | 0/4 |
| head+tail              |    609 |   87.1x | 1/4 |
| dedup                  |    528 |  100.5x | 4/4 |
| tylko bledy            |     89 |  596.0x | 3/4 |
| smart (dedup+wynik)    |    541 |   98.0x | 4/4 |
| spill + wskaznik       |     47 | 1128.5x | 0/4 |
```

Co z tego wynika:

| Strategia | Czego uczy |
|---|---|
| ✂️ `head` | Zysk 88x i **0/4** igieł. Przycięcie "od początku" to rzut monetą, bo ważne rzeczy leżą tam, gdzie program skończył, nie zaczął. |
| ✂️ `head+tail` | Łapie tylko podsumowanie z końca. Błąd w **środku** ginie - klasyczna pułapka. |
| 🎯 `tylko błędy` | Najtańsze (89 tok.) i **3/4**: gubi fakt, który nie wygląda jak błąd (`skipped: checksum mismatch`). Wzorzec = założenie o formacie. |
| ♻️ `dedup` | Linie o tym samym **szablonie** (cyfry i znaczniki czasu → `<n>`) zwijają się do jednej z licznikiem `[x229]`. 4/4, bo igły mają unikalne szablony. |
| 🧠 `smart` | dedup + wybór linii po wyniku, w oryginalnej kolejności, w budżecie. 4/4. |
| 📎 `spill` | Pełny wynik na dysk, do kontekstu: statystyka + ścieżka + gotowe `grep`. 0/4 **w kontekście**, ale wszystko jest do dociągnięcia - o ile agent faktycznie sięgnie (nie testowane). |

**Hak wewnątrz haka:** `dedup` daje 100x i nie traci nic - ale tylko dlatego, że **ten
syntetyczny log jest ekstremalnie powtarzalny** (~30 szablonów). Realne logi mają więcej
różnorodności i zysk będzie mniejszy. Mechanizm jest ten sam, liczba nie przenosi się 1:1.

### Gdzie `smart` się wywraca (uczciwie)

Ten sam log, budżet zaciśnięty do 250 tok. (`demo --budget 250`):

```
| smart (dedup+wynik)    |    236 |  224.8x | 3/4 |
```

`smart` **zgubił igłę z migracją.** Powód to nie błąd w kodzie, tylko **polityka w wyniku**:
`wynik = waga_ważności + 1/liczebność`, a ostrzeżenie `warning` ma wagę 5, unikalna linia
`info` ma ok. 1,0 - więc ostrzeżenia powtórzone 98-127 razy **wygrały** z faktem unikalnym.
Funkcja oceny **jest** twoją polityką kontekstu: kto ją pisze, decyduje, co model zobaczy.
Wniosek praktyczny: **rzadkość powinna ważyć więcej niż "poważnie brzmi"** albo ostrzeżenia
trzeba zwijać do jednej linii z licznikiem (czego `dedup` nie robił, bo tu budżet nie wiązał).
Nie poprawiałem tego w kodzie celowo - to jest przykład, nie produkt.

---

## 2️⃣ JSON: filtruj najpierw, rzutuj potem

Syntetyczna odpowiedź: 300 zamówień × 14 pól (adres, linie, tagi, etag...), 3 w stanie `Failed`.
~44 102 tok. Prawdziwy output:

```
| strategia              |   ~tok | zysk   | igly | poprawny JSON |
|------------------------|-------:|-------:|------|---------------|
| surowy (nic)           |  44102 |    1.0x | 3/3  | tak           |
| head                   |    600 |   73.5x | 0/3  | NIE           |
| projekcja pol          |   3739 |   11.8x | 3/3  | tak           |
| filtr+projekcja+licznik|     80 |  551.3x | 3/3  | tak           |
```

Trzy rzeczy, które warto zapamiętać:

1. 🧨 **`head` na JSON-ie psuje składnię** (`NIE`): model dostaje ucięty dokument. Teksty
   można ciąć, struktury - nie.
2. 📐 **Sama projekcja pól** (zostaw `id,status,total`) daje 11,8x, ale wciąż płacisz za
   297 zdrowych rekordów (3739 tok.). **Kolejność ma znaczenie: najpierw wiersze, potem kolumny.**
3. 🎯 **Filtr + licznik + projekcja** to 80 tok.: `{"total":300,"by_status":{"Paid":297,
   "Failed":3},"non_paid":[...3 rekordy...]}`. Licznik jest ważny: mówi modelowi, **ile**
   wycięto, więc wie, że widzi komplet "złych", a nie próbkę.

Dla .NET deva to znajomy wzorzec: `Where` przed `Select`, a `Count` obok. Różnica jest w tym,
że "zapytanie" musi wykonać **narzędzie/hook/skrypt**, zanim wynik trafi do kontekstu - model
płaci za wynik, nie za przetwarzanie.

---

## 3️⃣ Budżet kontekstu jako kod: plecak zamiast "jak leci"

Zadanie: "napraw test `Total_Rounds_HalfUp`". Dziewięć **syntetycznych** kandydatów do kontekstu
(treść zadania, stack trace, pliki, docs, blame, log w dwóch wersjach, jedna reguła domenowa),
kolejność = kolejność nadejścia, a **wartości (`value`) to moje subiektywne oceny, nie pomiar**.
Budżet 4000 tok. (`toolcompress.py pack`):

```
FIFO (jak leci): ~3920/4000 tok., suma wartosci = 192
   + dokumentacja architektury (caly docs/)          2500 tok.  v=10
   + historia git blame calego pliku                 1200 tok.  v=12
   + tresc zadania + kryterium akceptacji             180 tok.  v=100
   + regula: kwoty to decimal, MidpointRounding        40 tok.  v=70
   odrzucone: pelny log builda (surowy); DiscountCalculator.cs (caly plik); stack trace padajacego testu; ...

plecak (value/tok): ~3870/4000 tok., suma wartosci = 387
   + regula ...(40) + tresc zadania (180) + stack trace (350) + DiscountCalculator.cs (1400)
   + log po smart_log (400) + pelny log builda (surowy) (1500)
```

Ten sam budżet, **2x więcej wartości** - bo FIFO zapchał go dokumentacją i blame, zanim doszedł
do stack trace'a. To jest właśnie scenariusz agenta, który "najpierw przeczyta wszystko".

⚠️ **Ograniczenia tego modelu (widoczne w outpucie):**
- Plecak wziął **oba** logi: surowy i po `smart_log`. To są alternatywy, a algorytm nie zna
  wykluczeń. Prawdziwy planista musi je znać.
- Wartości są wymyślone przeze mnie. W praktyce ta tabela to **narzędzie myślenia**:
  zmuszasz się do napisania, co jest warte tokenów, *zanim* wrzucisz to do kontekstu.
- Zachłanny plecak po `value/tok` nie jest optymalny w ogólnym przypadku (to NP-trudne),
  tu wystarcza do ilustracji.

---

## 4️⃣ Pozycja informacji: hipoteza, nie wynik

Co z **kolejnością** wewnątrz kontekstu? W literaturze opisano efekt "lost in the middle"
(zgodnie z moją pamięcią: wyniki modeli bywają gorsze, gdy istotna informacja leży w środku
długiego kontekstu, lepsze - na początku i na końcu). **Nie zweryfikowałem tego** (pobranie źródła
odrzucone) **i nie mierzyłem na modelu**; wielkość efektu zależy od modelu i zadania, a nowsze
modele mogą go mieć słabszy.

Kod ma funkcję `order_edges` (najważniejsze na początek i na koniec, najmniej ważne w środek):

```
   100  tresc zadania + kryterium akceptacji
    80  DiscountCalculator.cs (caly plik)
    25  pelny log builda (surowy)
    22  log builda po smart_log
    70  regula: kwoty to decimal, MidpointRounding
    90  stack trace padajacego testu
```

To jest **tylko permutacja**; **jej wpływu na odpowiedzi modelu nie sprawdzałem**. Traktuj ją
jako tanią heurystykę do własnego A/B na swoich zadaniach, nie jako przepis. Pewne jest tylko to,
co z #1: kolejność warstw wpływa na cache (stałe na początku).

---

## 5️⃣ Checklista: kompresja wyniku bez ślepej plamy

| Zasada | Dlaczego |
|---|---|
| 📏 mierz **dwie** liczby: tokeny i przeżywalność faktów | sam zysk nagradza `head`, który gubi wszystko |
| 🧩 struktury filtruj semantycznie, nie bajtowo | ucięty JSON jest bezużyteczny |
| 🔢 zawsze zostaw **licznik** tego, co wycięte | model wie, że widzi próbkę/komplet |
| 🎯 wzorce błędów to założenie o formacie | fakt bez słowa `error` przepada; dodaj kanał "rzadkie linie" |
| ⚖️ funkcja oceny = polityka | sprawdź ją na przypadku granicznym (budżet 250 w naszym teście) |
| 📎 przy dużych wynikach: spill + wskaźnik + `grep` | kontekst dostaje mapę, nie teren |
| 📝 zapisz budżet jako tabelę z wartościami | zmusza do decyzji *przed* wczytaniem |

---

## 🚫 Co niezweryfikowane (wprost)

| Twierdzenie | Status |
|---|---|
| Zachowanie modelu na skompresowanych wynikach | **nie testowane** - żaden model nie uruchamiany; mierzę wyłącznie obecność faktów w tekście |
| "Lost in the middle" i skuteczność `order_edges` | z pamięci; pobranie źródła **odrzucone**; niemierzone |
| Realne logi/odpowiedzi API | **niemierzone** - dane syntetyczne, zysk (100x) zawyżony ekstremalną powtarzalnością |
| Czy agent sięga po plik ze spill | **nie testowane** (brak żywej sesji) |
| Hooki Claude Code do filtrowania wyniku narzędzia przed kontekstem | nie sprawdzano; kod to samodzielny filtr (`filter` czyta stdin), nie integracja |
| Wartości w tabeli plecaka | moje subiektywne oceny |
| Analiza prawdziwego transkryptu | odczyt `~/.claude/projects` **odrzucony** - nie obchodzone |

---

## 📎 Jak uruchomić kod z tego wydania

[`code/README.md`](code/README.md) - komendy, prawdziwy output, test 21/21. Wymaga tylko `python3`.

---

<div align="center">

[← wydanie z 6 października (wszystkie rubryki)](../README.md) · [spis wydań](../../README.md)

</div>
