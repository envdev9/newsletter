<div align="center">

# 📰 TECH PRASÓWKA
### Wydanie #11 rubryki — 20 października 2026

![AI/Kontekst](https://img.shields.io/badge/AI_%2F_Kontekst-8A5CF6?style=for-the-badge&logo=anthropic&logoColor=white)
![ls](https://img.shields.io/badge/listing_katalogu-delta_zamiast_kopii-F59E0B?style=for-the-badge)
![Zmierzone](https://img.shields.io/badge/4_12x_mniej_tokenow-0_bledow_w_4528_porownaniach-10B981?style=for-the-badge)

## `ls` to tani wynik, który wraca jak bumerang. Delta katalogu, rzut `-1A` z `-lA` i pokusa „nie wołam, bo wiem”

</div>

---

> _"Najdroższe polecenie w sesji to nie to, które trwa długo, tylko to, które agent woła za każdym razem „dla pewności”."_

W [#9](../2026-10-14-ten-sam-plik-po-raz-piaty-dlaczego-wyrzuc-stare-odczyty-z/ARTICLE.md) i [#10](../2026-10-19-wskaznik-do-czegos-czego-juz-nie-ma-jak-oszczednosc/ARTICLE.md) zdeduplikowaliśmy odczyty
plików i wyniki `grep`. Na liście „Następne” zostało jedno, najbardziej przyziemne polecenie: **`ls`**. Agent woła je przed
edycją, po edycji, po buildzie, „żeby zobaczyć, czy powstał plik”. Każdy wynik to pełna kopia katalogu w kontekście.

**Hak:** na prawdziwym katalogu (152 wpisy) delta zamiast pełnych kopii daje **4,12× mniej tokenów** (2,46× w token-turach,
3,18× w koszcie ważonym cache) i **0 błędów** odtworzenia listingu — a drobna, „oczywista” optymalizacja (nie wołam `ls`,
bo przecież sam nic nie zmieniłem) oszczędza **0,1%** i ma **1 błąd na 11**. To ten sam wzorzec co w #10: tanio i błędnie
bywa blisko siebie.

> ⚠️ **Uczciwie o danych.** Sesja jest **skryptowana** (17 tur), ale katalog w `/tmp`, edycje, rename, delete i **`ls`**
> (GNU coreutils 8.32, `LC_ALL=C`) są **prawdziwe**. **Żaden model nie był uruchamiany.** Tokeny = bajty/4, mnożniki cache
> 0,10/1,25 to założenia z pamięci (jak w #9). „Odtwarzalność” to test mechaniczny: czy da się złożyć wynik `ls` z samego
> tekstu, który model widzi. Nie wiem, jak `claude` naprawdę obsługuje `ls`, ani czy w ogóle da się wpiąć taką warstwę.

---

## 1️⃣ Dlaczego `ls` jest inny niż odczyt pliku

Plik z #9 zmienia się tylko przez nasze edycje. Katalog zmienia się też **sam**: build tworzy `*.g.cs`, test zostawia plik
tymczasowy, `git checkout` kasuje pół drzewa. Ma też dwa wymiary, o których `read` nie wie:

- **nazwy** (kto istnieje) — to widzi `ls -1A`,
- **atrybuty** (rozmiar, czas) — to widzi `ls -lA`, i **zmienia się przy każdej edycji pliku**.

Pierwsza rzecz, którą widać w danych: pełny `ls -lA` katalogu ze 152 wpisami to **1 677 tokenów**, `ls -1A` to 383.
Pojedyncza edycja jednego pliku zmienia w tym wyniku jedną linię (w naszej sesji `total` się nie ruszył; przy zmianie liczby bloków zmieni się też on).

## 2️⃣ Sześć polityk, jedno kryterium: czy z tekstu okna da się odtworzyć listing

Wszystkie polityki są **append-only** (historia nietknięta, więc prefiks cache żyje — lekcja z #9).

| Polityka | Co zwraca narzędzie |
|---|---|
| `none` | zawsze pełny wynik |
| `same` | stub, jeśli identyczny z poprzednim wynikiem **tego samego polecenia** |
| `setdiff` | delta względem poprzedniego wyniku, porównanie **całych linii** (zmiana pliku = `-stara +nowa`) |
| `namekey` | delta z kluczem = **nazwa pliku** (zmiana atrybutów = jedna linia `~`) |
| `state` | jeden „stan katalogu” z **każdego** wariantu: `-1A` jest rzutem `-lA` |
| `evented` | `state` + **nie wywołuje `ls`**, jeśli agent sam nic nie zrobił w katalogu |

Format delty (liczy się każdy znak, bo każdy znak jest tokenem):

```
[ls -lA src: delta wzgledem tury 1: +0 ~1 -0; reszta jak w tej turze]
~-rw-r--r-- 1 151 2026-10-01 10:19 Mod007.cs
```

To **29 tokenów** zamiast 1 677. Gdyby delta wyszła większa niż pełny wynik — narzędzie zwraca pełny (kod to sprawdza).

## 3️⃣ Wyniki (prawdziwy `ls`, 17 tur, 11 listingów)

`python3 -B lsdelta.py run` — katalog `src` ze 152 wpisami:

```
| polityka | tokeny | vs none | token-tury | vs none | koszt wazony | vs none | ls ok | stub/delta/full/skip | bledne tury |
| none | 10557 | 1.00x | 95990 | 1.00x | 21740 | 1.00x | 11/11 | 0/0/11/0 | - |
| same | 8626 | 1.22x | 92358 | 1.04x | 19156 | 1.13x | 11/11 | 2/0/9/0 | - |
| setdiff | 2612 | 4.04x | 39252 | 2.45x | 6929 | 3.14x | 11/11 | 2/6/3/0 | - |
| namekey | 2572 | 4.10x | 38975 | 2.46x | 6855 | 3.17x | 11/11 | 2/6/3/0 | - |
| state | 2564 | 4.12x | 38943 | 2.46x | 6843 | 3.18x | 11/11 | 2/6/3/0 | - |
| evented | 2564 | 4.12x | 38901 | 2.47x | 6839 | 3.18x | 10/11 | 1/5/3/2 | [9] |
```

Cztery wnioski, w tym dwa rozczarowujące:

1. 🪤 **Samo „identyczny → stub” (`same`) prawie nic nie daje: 1,22×.** Listing rzadko jest identyczny — po każdej edycji
   `ls -l` się zmienia. Zyskują dopiero delty (4,04×). Stub dla `ls` to nie to samo co stub dla pliku z #9.
2. 🔬 **Klucz = nazwa vs cała linia: różnica 1,5%** (2 572 vs 2 612). Intuicja „zmiana pliku to jedna linia `~`, a nie dwie”
   jest słuszna, ale na tej sesji to drobiazg. **Nie wygrywa tu elegancja, tylko sam mechanizm delty.**
3. 🧩 **Rzut `-1A` z `-lA` (`state`) daje kolejne 0,3%** (2 564 vs 2 572). Mechanizm działa (po `create` + `ls -1A`
   późniejszy `ls -lA` dostaje `~4`, bo trzy nowe nazwy model już zna), ale w tej sesji wariantów jest mało.
   **Nie obiecuję więcej, niż zmierzyłem.**
4. 🧨 **`evented` zaoszczędził 0,1% token-tur (38 901 vs 38 943) i pomylił się raz.** Dwa pominięte wywołania zamieniły
   12-tokenowy stub i 37-tokenową deltę na 15-tokenowe „nie wykonano”. **Wywołanie `ls` nie kosztuje kontekstu** — kosztuje je wynik. Dedupikacja wyniku zjada cały zysk
   „nie wołam”, więc nie ma po co ryzykować. Pomyłka: tura 9, po zewnętrznym buildzie, który stworzył 2 pliki; agent
   „ufał zdarzeniom”, a tych dwóch nie było wśród jego zdarzeń. Naprawiła się dopiero w turze 12 — delta objęła wszystko,
   ale **trzy tury model miał nieprawdziwy obraz katalogu**.

## 4️⃣ Pułapka, której `ls -l` nie widzi

Test `demo`: edycja pliku **o tym samym rozmiarze, w tej samej minucie** (rozdzielczość `long-iso` to minuta):

```
linia Mod007.cs w `ls -lA` przed edycja : -rw-r--r-- 1 151 2026-10-01 10:19 Mod007.cs
linia Mod007.cs w `ls -lA` po edycji    : -rw-r--r-- 1 151 2026-10-01 10:19 Mod007.cs
linie identyczne: True
sha256 tresci przed: 89e72eff56170e56  po: 70e20dd284ef242b  rozne: True
```

(Zmianę mtime wymusiłem `os.utime` — to symulacja „dwóch zapisów w tej samej minucie”, nie obserwacja z żywej sesji.)
Wniosek praktyczny: stub „identyczny z wynikiem z tury 13” jest **prawdziwy co do listingu** i **nic nie mówi o treści**.
Nie wolno z niego wnioskować, że plik się nie zmienił — od tego jest dedupikacja odczytu z #9 (hash treści).
Dwa mechanizmy, dwa różne klucze świeżości.

## 5️⃣ Skala: im większy katalog, tym lepiej (ale z sufitem)

`python3 -B lsdelta.py sweep` — ta sama sesja, różna liczba wpisów w `src`:

```
| wpisow w src | none: tokeny | state: tokeny | zysk tokenow | none: koszt wazony | state: koszt wazony | zysk kosztu |
| 22 | 2107 | 809 | 2.60x | 4255 | 1984 | 2.14x |
| 152 | 10557 | 2564 | 4.12x | 21740 | 6843 | 3.18x |
| 502 | 33310 | 7290 | 4.57x | 68822 | 19927 | 3.45x |
| 2002 | 133066 | 28042 | 4.75x | 275320 | 77394 | 3.56x |
```

Zysk **nasyca się ~4,8×**, bo pierwsze trzy listingi (pełne, nieuniknione) rosną liniowo razem z katalogiem. Delty ścigają
tylko zmiany, a sesja ma ich stałą liczbę. Stąd praktyczna konkluzja: to optymalizacja dla **dużych katalogów i długich sesji**;
przy 20 plikach oszczędzasz 1,3 tys. tokenów — i tyle.

## 6️⃣ Reguły do wpięcia we własne narzędzie

| # | Reguła | Dlaczego |
|---|---|---|
| 1 | **Zawsze wywołuj prawdziwe polecenie, deduplikuj tylko wynik** | wywołanie nic nie kosztuje w kontekście; `evented` oszczędził 0,1% i skłamał |
| 2 | **Delta tylko wtedy, gdy krótsza od pełnego wyniku** | inaczej „oszczędność” kosztuje |
| 3 | **Stub/delta niosą numer tury, względem której są liczone** | bez tego nie sprawdzisz, czy cel żyje (kompakcja z #10) |
| 4 | **Klucz = nazwa; `total` to osobny „plik”** | `total` zmienia się z edycjami i nie jest nazwą |
| 5 | **Listing ≠ treść** | `ls -l` nie widzi edycji tego samego rozmiaru w tej samej minucie |
| 6 | **Mierz wprost: listing==okno, nie tylko tokeny** | `evented` wygląda najlepiej w tokenach |

**Czego ta warstwa NIE rozwiązuje:** kolejność wpisów (delta jej nie zachowuje — odtwarzam listing jako zbiór linii; dla
`ls -t` albo `-S` trzeba by dopisać pozycje), kompakcja okna (zachowałby się tak jak `ignore` z #10: wskaźnik do zniszczonego
celu — trzeba by wpiąć „epokę”), `ls -R` i symlinki (`name -> cel`; nie testowałem), nazwy z nowymi liniami.

---

## 🧪 Co zweryfikowano, a co nie

| ✅ Zmierzone (Python 3.10.4 stdlib, GNU ls 8.32) | ❓ Niezweryfikowane |
|---|---|
| Prawdziwy katalog w `/tmp`: edycje, create, delete, rename, „build” (zewnętrzne pliki), 11 listingów 6 politykami | Zachowanie jakiegokolwiek modelu wobec delty/stuba |
| Listing==okno: 11/11 dla `none`/`same`/`setdiff`/`namekey`/`state`; `evented` 10/11 (test negatywny, musi zawieść) | Czy i jak `claude` pozwala wpiąć warstwę deduplikacji wyników `ls` |
| Fuzz: 60 losowych sesji (nazwy ze spacjami, ukryte pliki), 4 528 porównań listing==okno, 0 błędów | Mnożniki cache 0,10/1,25 (z #9, założenia); kompakcja okna dla `ls` |
| Skala 22–2002 wpisów (2,60× → 4,75× tokenów) | `ls -R`, symlinki, `ls -t`/`-S`, nazwy z `\n`, inne systemy plików/BSD `ls` |
| Edycja tego samego rozmiaru: `ls -l` jej nie widzi (hash różny, linia identyczna) | Realny rozkład powtórzeń `ls` w prawdziwych sesjach (u mnie 11 listingów w 17 turach, dobrane przeze mnie) |
| 4 545 asercji (`test_lsdelta.py`) | Czas mtime jako symulacja (`os.utime`) |

## 🎯 Zapamiętaj

1. **`ls` jest tani w wywołaniu, drogi w wyniku.** Deduplikuj wynik, nie wywołanie.
2. **Sam stub „identyczny” to 1,22×; dopiero delta daje 4×.** Listing rzadko się powtarza dosłownie.
3. **Listing nie jest treścią.** Dwa różne klucze świeżości dla dwóch różnych pytań.
4. **Ufanie własnym zdarzeniom nie widzi tego, co zrobił ktoś inny** — build, hook, `git`.

### ➡️ Następne kroki
- Weryfikacja w żywym `claude`: czy da się wpiąć taką warstwę (hak na wynik narzędzia), co przeżywa `/compact`.
- Epoka kompakcji dla delt `ls` (połączenie z `chain` z #10) i `ls -R` na dużym repo.
- Prawdziwy transkrypt (gdy odczyt dozwolony): rozkład powtórzeń `ls`; reguły `CLAUDE.md` i „lost in the middle”; embeddingi.
