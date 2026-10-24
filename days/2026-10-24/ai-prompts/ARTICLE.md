<div align="center">

# 📰 TECH PRASÓWKA
### Wydanie #29 — 24 października 2026

![AI](https://img.shields.io/badge/AI_%2F_Prompty-D97757?style=for-the-badge&logo=anthropic&logoColor=white)
![Python](https://img.shields.io/badge/Python_3-3776AB?style=for-the-badge&logo=python&logoColor=white)
![Cache](https://img.shields.io/badge/uk%C5%82ad_pod_cache-prefiks-F2C94C?style=for-the-badge)

## Układ promptu pod cache prefiksu: w łańcuchu z #18 kroki 2 i 3 mają 6 wspólnych znaków; po przestawieniu 940 - i dopiero od ~8-krotnie większego kodu to się opłaca

</div>

---

> _"Cache nie nagradza dobrego promptu. Nagradza prompt, który zaczyna się tak samo jak poprzedni."_

Poprzednio w tej rubryce: [koszt tokenów łańcucha (#25)](../../2026-10-18/ai-prompts/ARTICLE.md). Zostawiłem tam
przypis: *„cache prefiksu - niemodelowany; kolejność w promptach z #18 nie jest pod to układana"*. Dziś go
zdejmuję - **na poziomie układu tekstu**, bo to jedyna część, którą da się zmierzyć bez modelu: ile bajtów
kolejnych wywołań zaczyna się identycznie.

**🎯 Dlaczego to ważne:** w łańcuchu z #25 źródła jechały dwa razy (krok 2 i krok 3), a łańcuch kosztował
~1,9x jednego promptu. Dostawcy API oferują zwykle tańszy odczyt z cache'a **dla powtórzonego początku promptu**.
Tyle że „powtórzonego" znaczy *bajt w bajt od pierwszego znaku*. Jedna linia z numerem kroku na górze potrafi
wyzerować cały zysk - i nic tego nie zgłosi, po prostu rachunek się nie zmieni.

> ⚠️ **Uczciwie na starcie: żaden model, tokenizer ani API nie były uruchamiane.** Mierzę *długość wspólnego
> prefiksu w znakach* promptów zbudowanych przez skrypt z szablonów i ręcznie pisanych nagrań. Tokeny = znaki / 4
> (szacunek). Mnożniki ceny odczytu `r`, zapisu `g` i minimalna długość cache'owanego prefiksu `m` to **parametry,
> nie wartości z cennika żadnego dostawcy** - nie weryfikowałem ich w dokumentacji; sprawdź je dla swojego modelu.
> Model cache'a jest uproszczony: trafienie tylko przy identycznym początku, punkt zapisu idealnie na granicy
> wspólnego prefiksu.

---

### 1️⃣ Trzy układy tego samego łańcucha

Te same trzy kroki (triaż → plan → patch), to samo zgłoszenie, te same nagrania odpowiedzi. Zmienia się tylko
*kolejność tekstu* w promptach ([`code/prefix.py`](code/prefix.py), szablony w [`code/prompts/`](code/prompts)):

| Układ | Co jest na początku | Co na końcu |
|---|---|---|
| **A** (jak w #18) | rola kroku (`ROLA: triaz...` / `planista...` / `wykonawca...`) | dane |
| **B** | reguły + indeks + **cały** moduł `Billing` (te same bajty w każdym kroku) | rola, JSON, zgłoszenie |
| **C** | reguły; w krokach 2-3 dodatkowo źródła **podejrzanych z triażu** | rola, JSON, zgłoszenie |

Prawdziwy output (wspólny prefiks w znakach, skala kodu x1):

```
uklad                       dl.1  dl.2  dl.3  lcp(1,2)  lcp(2,3)  lcp(1,3)
A  (#18, szablon od zera)   1034  1341  1309         6         6         6
B  (caly modul w prefiksie)  2893  2929  2846      2275      2275      2275
C  (reguly + zrodla triazu)  1190  1594  1511       366       940       366
   A: kroki 2 i 3 rozjezdzaja sie na znaku 6: 'planista zmiany. Nie piszesz' vs 'wykonawca. Realizujesz DOKLA'
   C: kroki 2 i 3 rozjezdzaja sie na znaku 940 (z 1594): 'planista zmiany. Nie piszesz' vs 'wykonawca. Realizujesz DOKLA'
```

W układzie A kroki 2 i 3 mają wspólne **6 znaków** (`ROLA: `) - mimo że 470 znaków źródeł jest w obu *identyczne*.
Leżą za rolą i za JSON-em, który różni się między krokami, więc dla cache'a nie istnieją. W układzie C wspólne
jest 940 znaków (reguły + źródła), a rozjazd następuje dokładnie na granicy `planista` / `wykonawca`.

**Haczyk projektowy w C:** krok 3 dostaje źródła **z wyniku triażu, nie z planu**. Plan może wskazać podzbiór
podejrzanych, ale wtedy blok źródeł ma inny skład i prefiks się rozjeżdża (sekcja 4). Kontrakt C11 z #18 (plan tylko
w plikach z triażu) gwarantuje, że źródła triażu są nadzbiorem - więc ta zmiana nie traci informacji.

---

### 2️⃣ Na małym kodzie cache nie zadziała wcale

```
uklad                           bez cache  cache m=0  cache m=1024
A                                    1146       1144          1146
B                                    2392       1510          2392
C                                    1299       1064          1299
```

(r = 0,1, g = 1,25 - **założenia**; jednostka = 1 token wejściowy, wyjście liczone jak wejście.) Dwie lekcje:

- **`m = 0` to fikcja.** Gdyby cache działał dla dowolnie krótkiego prefiksu, C kosztowałby 1064 zamiast 1146
  (A). Ale prefiks C to ok. 235 tokenów, B - ok. 570. Przy progu `m = 1024` (**założony**, nie sprawdzony)
  cache nie robi nic: kolumna „cache m=1024" = „bez cache". Jako ostrzeżenie: wiem, że dostawcy stawiają
  minimalną długość prefiksu, ale dokładnych progów nie sprawdzałem - zależą od modelu, sprawdź sam.
- **Układ przestawiony kosztuje bez cache'a więcej** (C: 1299 vs A: 1146), bo moje szablony C są inne niż A (wspólne
  reguły dopisane do każdego kroku, a nieco skrócone ZASADY kroków) - to nie jest czysta zmiana kolejności, tylko
  kolejność **plus** inny tekst. Porównanie jest uczciwe tylko jako „cały pakiet", nie jako izolowany efekt.

---

### 3️⃣ Kiedy układ pod cache zaczyna się zwracać

Rosnący kod: źródła powielone `x` razy (balast: ten sam tekst z etykietą `kopia i`; cache nie zna znaczenia,
liczy bajty). Koszt względem **A bez cache**, r = 0,1, g = 1,25, m = 1024:

```
 skala zrodla all        A  B bez c.  B cache  C bez c.  C cache    B/A    C/A
     1       1600     1146      2392     2392      1299     1299  2.09x  1.13x
     5       8124     2108      7285     3875      2261     2261  1.84x  1.07x
     8      13017     2830     10955     5649      2982     2282  2.00x  0.81x
    10      16279     3310     13401     6832      3463     2607  2.06x  0.79x
    12      19547     3792     15852     8016      3945     2932  2.11x  0.77x
    20      32619     5720     25656    12755      5873     4234  2.23x  0.74x
   100     163339    25000    123696    60141     25153    17248  2.41x  0.69x
   400     654439    97450    492021   238165     97603    66152  2.44x  0.68x
```

| Co widać | Dlaczego |
|---|---|
| **C przełącza się między skalą x5 a x8** | dopiero tam prefiks kroków 2-3 przekracza założone 1024 tokeny: x5 daje 1,07x (cache nieaktywny), x8 daje 0,81x |
| **C zbiega do ~0,68x** | krok 2 płaci zapis (g), krok 3 odczyt (r) za źródła podejrzanych, reszta jest mała |
| **B nigdy nie wygrywa (2,1-2,4x)** | B wkłada do prefiksu **cały** moduł do każdego kroku. Cache obniża cenę, ale nie liczbę bajtów: krok 1 płaci zapis, kroki 2-3 odczyt, czyli w granicy `g + 2r` = 1,45 jednostki na znak kodu, a A płaci ok. `2f` = 0,58 (f = 0,29, udział plików podejrzanych z #25). Pasuje do zmierzonych 2,44x |
| **Triaż z #18 zostaje wartościowy** | cache nie zastępuje zawężania kontekstu - zawężanie (f < 1) i cache (r < 1) mnożą się, a w B cache działał *przeciwko* zawężeniu |

Wrażliwość na założenia (skala x20, m = 1024), komórka = `B/A | C/A`:

```
     r           g=1.0          g=1.25           g=2.0
   0.1   1.87|0.63       2.23|0.74       3.32|1.07
  0.25   2.30|0.70       2.67|0.81       3.76|1.14
   0.5   3.03|0.81       3.39|0.92       4.48|1.25
   1.0   4.48|1.03       4.85|1.14       5.94|1.47
```

Czytaj: C wygrywa, gdy odczyt jest wyraźnie tańszy od zapisu - przy `g = 2` i `r = 0,1` już nie (1,07x), a przy `r = 1`
(brak rabatu za odczyt) płacisz tylko dopłatę za zapis. **Dlatego `r` i `g` trzeba odczytać z cennika własnego
modelu, zanim cokolwiek przestawisz.**

---

### 4️⃣ Co psuje prefiks - cztery rzeczy, które zrobiłbyś bez myślenia

Układ C, skala x1, wspólny prefiks kroków 2 i 3 (znaki):

```
   baza (C)                                                 940
   naglowek 'Krok n:' na poczatku kazdego promptu             5
   JSON z poprzedniego kroku PRZED zrodlami                 372
   zrodla kroku 3 z PLANU (1 plik), zrodla kroku 2 z triazu (2 pliki)   474
   kontrola: te same 2 pliki z triazu w obu krokach        1802
```

- **Numer kroku / identyfikator / znacznik czasu na górze:** 940 → 5. Klasyk - „dla porządku" dopisujesz `Krok 2:`
  jako pierwszą linię. Takie metadane idą **na koniec** promptu.
- **Zmienny JSON przed stałymi źródłami:** 940 → 372. Zasada ogólna: od najrzadziej zmiennego do najczęściej
  zmiennego.
- **Źródła z planu zamiast z triażu:** 1802 → 474 (przy dwóch podejrzanych i jednym pliku w planie). Wiersz kontrolny
  pokazuje, że to nie rozmiar, tylko skład bloku.
- **Runda naprawcza po promptem, nie przed:**

```
== 6. runda naprawcza kroku 2: prompt kroku = 1594 znakow, tekst naprawczy = 564 znakow
   [prompt kroku][naprawa]: wspolny prefiks z oryginalnym promptem = 1594 z 1594
   [naprawa][prompt kroku]: wspolny prefiks z oryginalnym promptem = 0 z 1594
```

  W #25 liczyłem rundę naprawczą jako „prompt naprawczy + oryginalny prompt" bez wskazania kolejności. Przy
  kolejności `[naprawa][prompt]` ponowienie nie trafia w cache w ogóle; przy `[prompt][naprawa]` cały oryginał jest
  prefiksem (o ile nie wygasł - TTL cache'a nie modelowałem).

[`code/test_prefix.py`](code/test_prefix.py) pilnuje tych zależności i ma **test negatywny**: trzy zepsute
układy (nagłówek `Krok n`, JSON przed źródłami, układ A) muszą zostać wykryte przez `check_layout`.

---

### 5️⃣ Czego to nie dowodzi

> - **Żaden model, tokenizer ani API.** Znaki / 4 to heurystyka; prawdziwe liczby tokenów (zwłaszcza dla polskiego
>   i C#) będą inne. Mierzone jest tylko to, co deterministyczne: bajty wspólnego prefiksu.
> - **`r`, `g`, `m` to założenia.** Nie sprawdzałem cennika ani dokumentacji żadnego dostawcy; nie wiem, jak
>   dokładnie działa u konkretnego dostawcy wybór punktu zapisu (u niektórych trzeba go oznaczyć jawnie), jaki jest
>   TTL, czy równoległe wywołania trafiają w cache zapisany sekundę wcześniej. Model zakłada punkt zapisu idealnie
>   na granicy wspólnego prefiksu.
> - **Szablony C nie są identyczne z A** (sekcja 2): różnica kosztu miesza efekt kolejności z efektem innego
>   tekstu. Nie sprawdziłem, czy krótsze ZASADY w C nie pogarszają jakości odpowiedzi - modelu nie ma.
> - **Balast to powielone źródła.** Rzeczywisty duży kod ma inną strukturę; wynik dla f (udział podejrzanych) jest
>   przeniesiony z #25 i wynosi 0,29 tylko dla tych 3 plików.
> - **Czas (latencja) nie jest mierzony** - cache zwykle skraca też czas do pierwszego tokena, ale to nie jest
>   tu sprawdzone. Krok 1 jest sekwencyjnie przed 2 i 3, więc zapis cache'a w kroku 2 nie jest równoległy z niczym.
> - Nagrania odpowiedzi są pisane ręcznie, a runda naprawcza została tylko zbudowana jako tekst.

---

## Wspólny mianownik

Cache prefiksu to nie „opcja do włączenia", tylko **ograniczenie na układ promptu**: stałe na górze, zmienne na
dole, żadnych metadanych kroku na początku, te same bajty źródeł między krokami (z wyniku triażu, nie z planu),
naprawa doklejana na końcu. W tym łańcuchu przestawienie zmieniło wspólny prefiks kroków 2-3 z 6 do 940 znaków - ale
korzyść kosztowa (0,68-0,81x) pojawia się dopiero od kodu rzędu kilkunastu tysięcy znaków, i znika przy drogim
zapisie. Nie wkładaj do prefiksu „na wszelki wypadek" całego repo (B): cache obniża cenę bajta, a zawężanie
kontekstu zmniejsza liczbę bajtów - potrzebujesz obu.

---

## 📎 Jak zweryfikować

Zobacz [`code/README.md`](code/README.md) - komendy i prawdziwy output.

---

<div align="center">

[← wróć do wydania #29 (wszystkie rubryki)](../README.md) · [spis wydań](../../README.md)

</div>
