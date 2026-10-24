<div align="center">

# 📰 TECH PRASÓWKA
### Wydanie #10 rubryki — 19 października 2026

![AI/Kontekst](https://img.shields.io/badge/AI_%2F_Kontekst-8A5CF6?style=for-the-badge&logo=anthropic&logoColor=white)
![Kompakcja](https://img.shields.io/badge/wiszacy_stub-po_kompakcji-EF4444?style=for-the-badge)
![Zmierzone](https://img.shields.io/badge/108_scenariuszy-1512_sprawdzen_na_polityke-10B981?style=for-the-badge)

## Wskaźnik do czegoś, czego już nie ma. Jak „oszczędność” kontekstu po kompakcji zamienia się w ciche kłamstwo

</div>

---

> _"Stub „bez zmian od tury 11” jest tak samo prawdziwy jak adres, pod którym ktoś właśnie zburzył dom."_

Tydzień temu ([#9: powtórzone odczyty](../2026-10-14-ten-sam-plik-po-raz-piaty-dlaczego-wyrzuc-stare-odczyty-z/ARTICLE.md)) zbudowaliśmy narzędzie, które
przy ponownym odczycie pliku zwraca zamiast 7 962 tokenów **14-tokenowy stub** („bez zmian”) albo **33-tokenowy
diff**. Wygrało z wycinaniem starych odczytów, bo nie psuło prefiksu cache. Zostawiliśmy w „Następnych krokach” jedną
dziurę: *a co, gdy po drodze przyjdzie kompakcja?* Dziś ją zapychamy — i wychodzi coś gorszego niż „trochę drożej”.

**Hak:** kompakcja (okno → podsumowanie) wyrzuca z okna wszystko, na co wskazywały stuby. Wersja z #9, która
o kompakcji nie wie, jest na naszej sesji **2,11× tańsza** niż brak dedupikacji… i **4 z 14 sprawdzanych wyników jest
nie do odtworzenia z okna**. Wersja poprawna kosztuje **1,48×** mniej niż nic-nierobienie. Różnica 2,11 vs 1,48
to nie „strata efektywności” — to cena **prawdziwości**. A najgroźniejsza wersja po drodze („sprawdź, czy ostatnie
zdarzenie żyje”) wygląda na poprawną i **też** kłamie.

> ⚠️ **Uczciwie o danych.** Sesja jest **skryptowana** (19 kroków): pliki, edycje, testy (`subprocess`) i `grep`
> są prawdziwe, ale **żaden model nie był uruchamiany**. Kompakcja jest **modelowana**, nie zaobserwowana:
> podsumowanie to stały tekst syntetyczny (510 tok., zakładam, że nie niesie treści plików), „ogon” to ostatnie *k*
> zdarzeń. Nie wiem, co i jak zostawia prawdziwy `/compact` ani auto-kompakcja w `claude` — nie uruchamiałem żywej
> sesji. „Odtwarzalność” to test **mechaniczny** (czy da się złożyć wynik z tekstu w oknie), nie test zachowania modelu.

---

## 1️⃣ Anatomia kłamstwa

Stub ma sens tylko, jeśli **cel jest w oknie**. Narzędzie z #9 trzyma `last_seen[plik] = (tura, treść)` i na tej
podstawie decyduje: ta sama treść → stub, zmieniona → diff. Po kompakcji `last_seen` dalej mówi „widziałem”. Efekt na
prawdziwej sesji (`python3 -B ctxledger.py show ignore 0` — okno na końcu sesji, kompakcja przed turą 12, ogon 0):

```
T00 [summary]   510 tok.  [podsumowanie kompakcji - SYNTETYCZNE] zadanie: zmiana k w rrf, ...
T12 [same]       14 tok.  [plik bez zmian od odczytu w turze 11 - tresc jak wyzej]
T13 [full]       39 tok.  [pominieto 18 z 18 linii - widoczne wyzej, numery: ctxsearch.py: 324,341,342,...
```

(Wycinek wyjścia; pełne linie są dłuższe.)

Tury 11 już nie ma. „Jak wyżej” — nie ma żadnego „wyżej”. A `grep`, który „pominął 18 z 18 linii”, oddał modelowi
**pustą odpowiedź w eleganckim opakowaniu**. Wszystko się zgadza w metrykach tokenów — i dokładnie dlatego nikt tego
nie zauważy.

Co zrobiłby model — **nie wiem** (zapytałby ponownie? zgadywał?). Ta sekcja mówi tylko tyle:
*treść, na którą wskazuje wskaźnik, nie istnieje w tekście okna*.

---

## 2️⃣ Co jeszcze dedupikujemy: wyniki `grep`

Zadanie było z listy „Następne”: oprócz plików, deduplikacja wyników `grep`. Mechanizm jest bliźniaczy, ale
drobniejszy: księga `(plik, numer linii) → (tekst, id zdarzenia)`. Linia, którą model już widział i która nadal
**jest taka sama**, trafia do nagłówka `[pominieto 4 z 18 linii - widoczne wyzej, numery: ...]`; reszta idzie w całości.
Pominięcie wolno zrobić tylko, jeśli nagłówek jest tańszy od linii (kod to sprawdza).

Drobiazg, który wyszedł z prawdziwej sesji: po wstawieniu jednej linii na początku pliku **wszystkie numery
przesuwają się o 1** (test: każdy wynik `grep` z `ctxsearch.py` przesunięty o dokładnie +1). Klucz `(plik, nr, tekst)` sam
unieważnia przestarzałe wpisy — w tej turze z 18 linii dało się pominąć tylko 4 (z pliku testowego, którego edycja nie
dotknęła). **Porównanie tekstu to tani test wersji**; nie trzeba osobnego licznika edycji.

---

## 3️⃣ Pięć sposobów na obsługę kompakcji

| Polityka | Co robi księga po kompakcji | Intuicja |
|---|---|---|
| `none` | nie dedupikuje | baseline |
| `ignore` | **nic** (zachowanie z #9) | „przecież pamiętam” |
| `epoch` | zeruje wszystko przy każdej kompakcji | młotek |
| `last` | wpis ważny, gdy **ostatnie zdarzenie z treścią** żyje w oknie | „sprawdzam, czy cel istnieje” |
| `chain` | wpis ważny, gdy żyją **wszystkie** zdarzenia łańcucha (pełny odczyt + wszystkie diffy) | diff jest ważny tylko razem z bazą |

Czemu `last` to pułapka? Diff z tury 11 jest *zdarzeniem*, które żyje — leży w ogonie okna. Ale jego **baza**
(pełny odczyt z tury 3) została wycięta. Diff bez bazy to ciąg znaków `+/-` bez pliku, do którego go przyłożyć.
Dlatego `chain`.

---

## 4️⃣ Wyniki (prawdziwa sesja, modelowana kompakcja)

`python3 -B ctxledger.py run`, baza 8000 tok., mnożniki cache 0,10/1,25 (**założenia z #9, niezweryfikowane**).
Kompakcja przed turą 12. Przypadek 1: ogon 0 (całe okno → podsumowanie).

```
| polityka | token-tury | vs none | koszt wazony | vs none | odczyty ok/dangl/wrong | grep ok/dangl/wrong |
| none | 361048 | 1.00x | 79945 | 1.00x | 6/0/0 | 8/0/0 |
| ignore | 247041 | 1.46x | 37842 | 2.11x | 4/2/0 | 6/2/0 |
| epoch | 313023 | 1.15x | 53975 | 1.48x | 6/0/0 | 8/0/0 |
| last | 313023 | 1.15x | 53975 | 1.48x | 6/0/0 | 8/0/0 |
| chain | 313023 | 1.15x | 53975 | 1.48x | 6/0/0 | 8/0/0 |
| chain-bez-grep | 320189 | 1.13x | 56216 | 1.42x | 6/0/0 | 8/0/0 |
| chain-tylko-grep | 353882 | 1.02x | 77704 | 1.03x | 6/0/0 | 8/0/0 |
```

Przypadek 2: ogon 6 zdarzeń (ostatnie 3 tury przeżywają kompakcję: edycja, `grep`, odczyt-jako-diff):

```
| none | 428072 | 1.00x | 96282 | 1.00x | 6/0/0 | 8/0/0 |
| ignore | 250305 | 1.71x | 38637 | 2.49x | 4/2/0 | 6/2/0 |
| epoch | 316287 | 1.35x | 54770 | 1.76x | 6/0/0 | 8/0/0 |
| last | 251005 | 1.71x | 38822 | 2.48x | 4/2/0 | 8/0/0 |
| chain | 314565 | 1.36x | 54315 | 1.77x | 6/0/0 | 8/0/0 |
```

Cztery wnioski:

1. 🧨 **Najtańsze są dokładnie te polityki, które kłamią.** `ignore` (2,11× / 2,49×) i `last` w przypadku 2 (2,48×)
   „oszczędzają”, bo odmawiają ponownego wczytania pliku (7 959 tok.) — czyli odmawiają dania modelowi tego, czego
   potrzebuje. Poprawny `chain` kosztuje o ~41% więcej niż `ignore` (54 315 vs 38 637), bo **po kompakcji musi jeden raz
   wczytać plik w całości**.
2. 🪤 **`last` ratuje grep, ale nie pliki.** W przypadku 2 `last` ma 8/8 grepów OK, a odczyty 4/6: tura 11 w ogonie to
   *osierocony diff* (baza w turze 3 poszła do kosza), a następny odczyt zwrócił na nim „bez zmian”.
3. 🔬 **Ogon pomaga, jeśli księga umie z niego korzystać.** `chain` z ogonem 6 pominął 113 linii grep, `epoch` (młotek)
   tylko 99; w koszcie ważonym 54 315 vs 54 770 — różnica **0,8%**. Niewiele: tu to nie jest główny zysk.
4. 📉 **Sam grep to drobiazg, plik to sedno.** `chain-tylko-grep` daje 1,03×, `chain-bez-grep` 1,42× z 1,48×. Wynik
   `grep` na tym pliku ma 385 tok.; pominięcie obniża go do 139 (po kompakcji) lub 49 (T17). Nie wiem, jak to wygląda
   przy `grep -r` po dużym repo — **nie mierzyłem**.

---

## 5️⃣ A jeśli kompakcja wypadnie gdzie indziej? Przemiatanie

Jedna kompakcja w jednym miejscu to anegdota. `python3 -B ctxledger.py sweep`: kompakcja po *każdym* z kroków 1–18 ×
ogon 0/2/4/6/8/12 zdarzeń = **108 scenariuszy**, w każdym 14 sprawdzanych wyników (1 512 sprawdzeń na politykę):

```
| polityka | kombinacji | z bledem | bledne wyniki (suma) | sprawdzen | sredni koszt wazony / none |
| none | 108 | 0 | 0 | 1512 | 1.00 |
| ignore | 108 | 91 | 354 | 1512 | 0.45 |
| epoch | 108 | 0 | 0 | 1512 | 0.58 |
| last | 108 | 15 | 20 | 1512 | 0.54 |
| chain | 108 | 0 | 0 | 1512 | 0.55 |
| chain-bez-grep | 108 | 0 | 0 | 1512 | 0.59 |
| chain-tylko-grep | 108 | 0 | 0 | 1512 | 0.97 |
```

- `ignore`: błąd w **91 ze 108** scenariuszy, 354 niepoprawne wyniki. To nie rzadki przypadek brzegowy — to norma.
- `last`: błąd w 15 scenariuszach, 20 wyników. Rzadszy, więc **trudniejszy do wykrycia** — a to gorsza własność.
- `epoch` i `chain`: **0 błędów** we wszystkich 108. `chain` średnio 0,55 vs 0,58 `epoch` (−5%).

Zastrzeżenie: „0 błędów” to wynik **testu mechanicznego** w jednej, 19-krokowej sesji i jednym zestawie plików; nie jest
dowodem na poprawność w ogólności. Dowód nie zastępuje testów na innych sesjach.

---

## 6️⃣ Co z tego wynika dla Twojego narzędzia

| # | Reguła | Dlaczego |
|---|---|---|
| 1 | **Każdy wskaźnik przechowuje identyfikatory zdarzeń, na które wskazuje** | bez tego nie sprawdzisz, czy cel żyje |
| 2 | **Wpis ważny ⇔ wszystkie elementy łańcucha żyją** (nie tylko ostatni) | diff bez bazy = `last` |
| 3 | **Przy braku wiedzy o kompakcji: `epoch`** (zeruj wszystko) | 0/108 błędów, tylko ~5% drożej niż `chain` |
| 4 | **Metryka „tokeny” nie wystarcza — dodaj test odtwarzalności** | `ignore` ma najlepszy wynik w tokenach i 354 błędne wyniki |
| 5 | **Porównuj tekst, nie licznik wersji** | numery linii przesunięte o 1 odsiewają się same |
| 6 | **Nagłówek pominięcia tylko, gdy tańszy od pominiętych linii** | inaczej „oszczędność” kosztuje |

**Skąd narzędzie ma wiedzieć o kompakcji?** To otwarte. Z pamięci: `claude` ma haki cyklu życia sesji, w tym jeden
związany z kompakcją, ale **nie sprawdzałem tego** (nie uruchamiałem żywej sesji ani nie czytałem dokumentacji w tym
przebiegu) — traktuj jako hipotezę do weryfikacji. Bez żadnego sygnału `epoch` nie ma na czym się oprzeć, a `chain`
potrzebuje listy żywych zdarzeń okna, której zewnętrzne narzędzie prawdopodobnie nie widzi (też niezweryfikowane).

---

## 🧪 Co zweryfikowano, a co nie

| ✅ Zmierzone (kod, Python 3.10.4, stdlib, `grep` = ugrep 7.8.4) | ❓ Niezweryfikowane |
|---|---|
| Prawdziwa 19-krokowa sesja: edycje, testy (`OK: 40`), 8× `grep` z niezależnie sprawdzonym wynikiem | Zachowanie jakiegokolwiek modelu wobec stuba/pustego grepa |
| 7 polityk × 2 scenariusze: tokeny, koszt ważony, odtwarzalność z okna (ok/dangling/wrong) | Co robi prawdziwy `/compact`, auto-kompakcja i co zawiera podsumowanie (u mnie: stałe 510 tok.) |
| 108 scenariuszy kompakcji (pozycja × ogon), 1 512 sprawdzeń na politykę | Mnożniki cache 0,10/1,25 i baza 8000 tok. (z #9, założenia) |
| 54 asercje (`test_ctxledger.py`), w tym testy negatywne (`ignore`, `last` muszą zawodzić) | Haki `claude`, skąd narzędzie dowie się o kompakcji; żywa sesja `claude` |
| Przesunięcie numerów o +1 po wstawieniu linii wykryte bez licznika wersji | `ls`/`grep -r` na dużym repo; rozkład powtórzeń w prawdziwych sesjach |

## 🎯 Zapamiętaj

1. **Wskaźnik w kontekście jest prawdziwy tylko, dopóki jego cel jest w oknie.** Kompakcja to zdarzenie, które to łamie.
2. **Łańcuch, nie ogniwo:** diff żyje tylko razem z bazą i poprzednimi diffami.
3. **Najlepszy wynik w tokenach może oznaczać najgorszy w prawdziwości.** Mierz obie osie.
4. **Tani test wersji:** porównaj treść/linię, zamiast liczyć edycje.

### ➡️ Następne kroki
- Weryfikacja w żywym `claude`: co dokładnie przeżywa `/compact` i czy jest sygnał, na którym można oprzeć `epoch`.
- Prawdziwy transkrypt (gdy odczyt dozwolony): rozkład powtórzeń i realne rozmiary wyników `grep`.
- Reguły `CLAUDE.md` i „lost in the middle”; embeddingi, gdy dostępny model; niezależny zestaw zapytań.
