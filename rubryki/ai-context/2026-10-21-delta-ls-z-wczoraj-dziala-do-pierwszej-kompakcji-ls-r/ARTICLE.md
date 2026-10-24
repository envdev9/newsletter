<div align="center">

# 📰 TECH PRASÓWKA
### Wydanie #12 rubryki — 21 października 2026

![AI/Kontekst](https://img.shields.io/badge/AI_%2F_Kontekst-8A5CF6?style=for-the-badge&logo=anthropic&logoColor=white)
![ls -R](https://img.shields.io/badge/ls_--R-delta_per_sekcja_%2B_projekcja-F59E0B?style=for-the-badge)
![Zmierzone](https://img.shields.io/badge/9_49x_mniej_tokenow-42%2F51_scenariuszy_kompakcji_psuje_delty-10B981?style=for-the-badge)

## Delta `ls` z wczoraj działa do pierwszej kompakcji. `ls -R`, projekcja poddrzewa i dwa sposoby na „wiszącą deltę”: leniwy `chain` i drogi `carry`

</div>

---

> _"Delta jest wspaniała tak długo, jak długo okno pamięta to, względem czego ją policzono."_

W [#11](../2026-10-20-ls-to-tani-wynik-ktory-wraca-jak-bumerang-delta-katalogu/ARTICLE.md) wynik `ls` jednego katalogu zamieniliśmy w deltę (4,12× mniej tokenów). Zostały trzy
dziury, które w prawdziwej pracy gryzą najmocniej: **(1)** agent woła `ls -R` na całym drzewie, a zmienia się jedna linia
w jednym podkatalogu; **(2)** po `ls -R proj` pyta jeszcze o `proj/src/m03` — czyli o coś, co już widział; **(3)** kontekst
przechodzi kompakcję i delta wskazuje na bazę, której nie ma.

**Hak:** na prawdziwym drzewie (17 katalogów, 167 wpisów) sesja 18 tur kosztuje **30 011 tokenów**, z deltą **5 231 (5,74×)**,
a z deltą **i projekcją poddrzewa 3 162 (9,49×)** — bez jednego błędu odtworzenia. Ale po kompakcji **42 z 51 scenariuszy**
(deltę z projekcją: też 42) kończy się oknem, które nie zgadza się z rzeczywistym `ls`. Dwie naprawy: leniwa (`chain`, 4,45×)
i droga (`carry`, 3,89×) — obie z zerem błędów.

> ⚠️ **Uczciwie o danych.** Sesja jest **skryptowana** (18 tur), ale drzewo plików w `/tmp`, edycje, rename, symlinki, „build”
> i **`ls`** (GNU coreutils 8.32, `LC_ALL=C`) są **prawdziwe**. Czas modyfikacji ustawiam `os.utime` (deterministyczne
> wyniki). **Żaden model nie był uruchamiany.** Tokeny = bajty/4. „Okno” to tekst, z którego skrypt odbudowuje listing;
> kompakcja jest **modelowana** (stałe podsumowanie 510 tok.), nie wzięta z prawdziwego `claude`.

---

## 1️⃣ Dlaczego `ls -R` to osobny problem

Wynik `ls -R` to **sekcje** (`proj/src/m03:` + wpisy). Zmiana pliku zmienia jedną linię w jednej sekcji, a dodanie pliku
zmienia jeszcze linię katalogu u rodzica (`total`, mtime). Dlatego klucz zmiany to para **(katalog, nazwa)**, a delta jest
zapisana jako sekcje:

```
[ls -R proj: delta wzgledem tury 5; sekcji: 6]
@proj
~total 28
+drwxr-xr-x  6 4096 2026-10-01 10:06 obj
@proj/obj =                      <- nowy katalog: cala sekcja ("=")
=total 16
=drwxr-xr-x 2 4096 2026-10-01 10:06 p00
...
```

Prawdziwa sesja pokazuje też, jak mało kosztuje zwykła zmiana (tura 2, edycja jednego pliku w `src/m03`):

```
[ls -R proj: delta wzgledem tury 1; sekcji: 1]
@proj/src/m03
~-rw-r--r-- 1 555 2026-10-01 10:02 File002.cs
```

**27 tokenów** zamiast 1 954. Pełny „build” (tura 6: 4 nowe katalogi po 15 plików) kosztuje 788 zamiast 2 739 — bo nowe sekcje
muszą zostać wysłane w całości, ale reszta drzewa nie.

## 2️⃣ Siedem polityk

| Polityka | Co zwraca narzędzie |
|---|---|
| `none` | zawsze pełny wynik |
| `same` | stub, jeśli wynik identyczny z poprzednim **tego samego polecenia** |
| `gdelta` | delta globalna (całość albo nic): jeśli delta ≥ pełny wynik → pełny |
| `sdelta` | delta **per sekcja**: dla każdej zmienionej sekcji tańsze z (delta \| cała sekcja) |
| `proj` | `sdelta` + **jeden stan drzewa** dla wszystkich poleceń: `ls -lA proj/src/m03` po `ls -R proj` wynika z wiedzy |
| `chain` | `proj` + sekcja, której łańcuch (pełna + delty) nie przeżył kompakcji, jest wysłana od nowa — **leniwie**, przy następnym `ls` |
| `carry` | `proj` + podsumowanie kompakcji zawiera **cały stan drzewa** — **gorliwie**, przy każdej kompakcji |

Wszystkie są append-only (historia nietknięta, więc prefiks cache żyje — lekcja z #21).

## 3️⃣ Wyniki bez kompakcji (prawdziwy `ls`, 18 tur)

`python3 -B lsepoch.py run`:

```
| polityka | tokeny | vs none | token-tury | vs none | stub/delta/full | bledne tury |
| none   | 30011 | 1.00x | 284009 | 1.00x | 0/0/18 | - |
| same   | 24134 | 1.24x | 241093 | 1.18x | 3/0/15 | - |
| gdelta |  5231 | 5.74x |  67694 | 4.20x | 3/9/6  | - |
| sdelta |  5231 | 5.74x |  67694 | 4.20x | 3/9/6  | - |
| proj   |  3162 | 9.49x |  49343 | 5.76x | 5/12/1 | - |
```

Cztery wnioski, w tym jeden zerowy:

1. 🪤 **`same` znowu ~1,2×.** Powtórzenie dosłowne zdarza się rzadko (tury 3, 14, 18 w tej sesji).
2. 🔬 **`sdelta` == `gdelta`, co do tokena.** Hipoteza „wyślij całą sekcję, gdy delta jej jest droższa” **nie sprawdziła się**:
   w tej sesji cała sekcja wygrała z deltą dla sekcji już znanej **0 razy** (wiersz `~` ma tę samą długość co `=`, a `-klucz`
   jest tańszy niż cała linia). Całe sekcje wysyłamy tylko wtedy, gdy są nowe — a to musimy robić zawsze. Per-sekcyjne
   wybieranie dorzuca kod i nie daje nic. **Nie wygrywa tu inteligencja, tylko sam mechanizm delty.**
3. 🧩 **Projekcja to prawdziwy skok: 5,74× → 9,49×.** Tury 4, 7, 9, 15 pytają o poddrzewo lub inny katalog; stan jest już w
   oknie, więc dostają kilkanaście tokenów (`ls -R proj/src/m03`: **11 tok.** zamiast 118).
4. 📈 **Skala: im większe drzewo, tym lepiej, z sufitem.** `python3 -B lsepoch.py sweep`:

```
| katalogow src | pelny ls -R | none  | proj  | zysk   | gdelta |
| 4   |   927 |  15973 |  2190 |  7.29x | 4.90x |
| 12  |  1954 |  30011 |  3162 |  9.49x | 5.74x |
| 40  |  5546 |  80288 |  6754 | 11.89x | 6.47x |
| 120 | 15817 | 224093 | 17026 | 13.16x | 6.80x |
```

Zysk rośnie, bo pierwszy pełny listing jest nieunikniony i rośnie liniowo; delty ścigają stałą liczbę zmian.

## 4️⃣ Kompakcja: delta, która wisi

To jest sedno wydania. Kompakcja wyrzuca stare wyniki (zostaje ogon ostatnich K tur). Jeśli delta z tury 12 liczy się
względem pełnego `ls` z tury 1, a tury 1 już nie ma — model ma „+1 plik, −1 plik” bez listingu, do którego to przyłożyć.
Dokładnie ten sam mechanizm co wiszący stub z [#26](../2026-10-19-wskaznik-do-czegos-czego-juz-nie-ma-jak-oszczednosc/ARTICLE.md), tylko groźniejszy: **delty tworzą łańcuch**, a przerwanie
dowolnego ogniwa psuje wszystko po nim.

Kompakcja przed turą 10, ogon 0 (okno = tylko podsumowanie):

```
| gdelta | 5741 | 5.32x | 41999 | 3.92x | 3/9/6  | [10,12,13,14,16,17,18]       |
| proj   | 3672 | 8.31x | 27320 | 6.02x | 5/12/1 | [10,11,12,13,14,15,16,17,18] |
| chain  | 6368 | 4.79x | 51584 | 3.19x | 5/11/2 | -                            |
| carry  | 6406 | 4.76x | 51926 | 3.17x | 5/12/1 | -                            |
```

(`token-tury` dla błędnych polityk są „tanie” z oczywistego powodu: tanie jest to, co nie niesie informacji.)

- `proj` jest **najbardziej złamany** (9 złych tur z 9 możliwych po kompakcji): jeden wspólny stan oznacza, że jedna dziura
  psuje odpowiedzi na wszystkie polecenia, także te o innych katalogach.
- `chain` robi to, co robił w #26: narzędzie wie, kiedy kompakcja zerwała łańcuch sekcji, więc wysyła ją od nowa — **ale tylko
  tę, o którą ktoś zapytał**. Tu: jeden pełny listing w turze 10 (+2 718 tok.).
- `carry` wkłada stan drzewa do podsumowania **zawsze**, także gdy `ls` już nie padnie.

Przemiatanie `python3 -B lsepoch.py compsweep` — kompakcja przed **każdą** turą 2..18 × ogon {0, 3, 6} = 51 scenariuszy:

```
| polityka | scenariuszy | z bledem | bledne tury | suma token-tur | vs none |
| none   | 51 |  0 |   0 | 11665017 | 1.00x |
| same   | 51 |  3 |   3 |  9970562 | 1.17x |
| gdelta | 51 | 42 | 243 |  2773572 | 4.21x |
| sdelta | 51 | 42 | 243 |  2773572 | 4.21x |
| proj   | 51 | 42 | 324 |  1965408 | 5.94x |
| chain  | 51 |  0 |   0 |  2619728 | 4.45x |
| carry  | 51 |  0 |   0 |  2997312 | 3.89x |
```

Tabela mówi coś, czego nie widać przy pojedynczym scenariuszu:

- Poprawny wybór to **`chain`**: 4,45× wobec 3,89× `carry`, czyli lenistwo jest ~14% tańsze, bo nie płaci za stan, którego nikt
  nie zapyta. W tej sesji `carry` nie wygrał ani razu w sumie; nie sprawdzałem, czy istnieje profil sesji (np. `ls -R` zaraz po każdej
  kompakcji), w którym by wygrał.
- **Uwaga na wniosek o zysku z `proj`:** 5,94× to koszt „błędnego” rozwiązania. Po poprawce (`chain`) zostaje 4,45×. Cena
  poprawności w tym modelu to ok. 25% oszczędności.
- `same` myli się w 3 scenariuszach — nawet naiwny stub „identyczny” może wskazywać na zniszczony cel.

> 🐞 **Pomyłka w trakcie pisania (zostawiam, bo uczy).** Pierwsza wersja `chain` zawodziła w 2 z 51 scenariuszy (kompakcja przed
> turą 11, ogon 3 i 6). Przyczyna była w **modelu okna**, nie w narzędziu: wiszące delty z ogona tworzyły *częściowe*
> sekcje (np. `proj` bez wpisu `src`), a mój `prune` uznał wtedy poprawnie odtworzoną sekcję `proj/src` za sierotę, bo jej
> rodzic „nie ma” takiego wpisu. Naprawa: delta bez bazy jest ignorowana, nie tworzy sekcji. Wniosek ogólny: **niekompletna
> wiedza jest groźniejsza niż brak wiedzy**, bo wygląda na kompletną. Jeśli prawdziwy model zachowuje się podobnie (nie wiem),
> wiszące delty w ogonie są aktywnie szkodliwe, nie tylko bezużyteczne.

## 5️⃣ Czego `ls` nie powie o kolejności

Delta traktuje listing jako **zbiór linii** (tak odtwarzamy `ls`, który sortuje alfabetycznie). Co z `ls -t` i `ls -S`? Test
`python3 -B lsepoch.py order` — 152 pliki, 40 losowych układów czasu i rozmiaru, kolejność z prawdziwego `ls` kontra kolejność
odtworzona z samego tekstu (sort po czasie/rozmiarze malejąco, remisy po nazwie):

```
| ls -t | long-iso | 0/40  | 1558 |
| ls -S | long-iso | 40/40 | 1558 |
| ls -t | full-iso | 40/40 | 2280 |
| ls -S | full-iso | 40/40 | 2280 |
```

- `-S` da się odtworzyć: rozmiar jest w linii, remis rozstrzyga nazwa.
- `-t` **z `--time-style=long-iso` (minuty) nie da się: 0/40**, bo `ls` sortuje po pełnym mtime (sekundy, nanosekundy), a my
  pokazujemy modelowi tylko minuty. Pliki z tej samej minuty mają nieodtwarzalną kolejność. **Uwaga:** test jest
  zaprojektowany nieprzyjaźnie (152 pliki w oknie 8 minut, losowe sekundy). Na prawdziwym repo, gdzie mtime-e są rozrzucone w
  czasie, mogłoby wyjść lepiej — nie sprawdzałem.
- `full-iso` naprawia `-t`, ale kosztuje **+46% tokenów** na listing (2 280 vs 1 558). Dla delt to i tak groszowa sprawa, ale
  dla pełnych listingów — nie.

## 6️⃣ Reguły do wpięcia we własne narzędzie

| # | Reguła | Dlaczego |
|---|---|---|
| 1 | **Klucz = (katalog, nazwa); `total` to osobny klucz** | zmiana pliku zmienia `total` rodzica i mtime katalogu |
| 2 | **Jeden stan drzewa na wszystkie polecenia** | `ls -lA podkatalog` po `ls -R` kosztuje ~11 tok. (5,74× → 9,49×) |
| 3 | **Delta do tury N tylko, jeśli łańcuch od ostatniej pełnej sekcji żyje** | inaczej wiszące delty (42/51 scenariuszy) |
| 4 | **Po kompakcji wysyłaj pełną sekcję leniwie** | 4,45× vs 3,89× dla `carry` |
| 5 | **Nie stosuj delty bez bazy, ani w narzędziu, ani w głowie** | częściowa wiedza zatruwa kompletną |
| 6 | **Pełny wynik zawsze, gdy delta ≥ pełny** | inaczej „oszczędność” kosztuje |
| 7 | **Kolejność inna niż alfabetyczna wymaga pełniejszego czasu (albo pozycji)** | `-t` + minuty = 0/40 |

**Czego ta warstwa NIE rozwiązuje:** stub „identyczny z turą N” dla poddrzewa wskazuje turę ostatniej zmiany **całego** drzewa,
nie turę, z której pochodzi dana sekcja — model musi to poskładać sam. `ls -R` z symlinkami do katalogów (`-L`), nazwy z
nowymi liniami lub `" -> "`, BSD `ls`, głębokie drzewa — nietestowane.

---

## 🧪 Co zweryfikowano, a co nie

| ✅ Zmierzone (Python 3.10.4 stdlib, GNU ls 8.32) | ❓ Niezweryfikowane |
|---|---|
| Prawdziwe drzewo w `/tmp` (167 wpisów, symlinki, spacje w nazwach): edycje, create, delete, rename, relink, „build”, clean | Zachowanie jakiegokolwiek modelu wobec delty, stuba, podsumowania ze stanem |
| Listing==okno: 7 polityk × 18 tur, bez kompakcji 0 błędów | Czy i jak `claude` pozwala wpiąć taką warstwę; co dokładnie przeżywa `/compact` |
| Kompakcja przed każdą turą 2..18 × ogon {0,3,6}: `chain`/`carry`/`none` 0 błędów, `gdelta`/`sdelta`/`proj` 42/51 z błędem | Kompakcja jest modelowana (podsumowanie 510 tok., ogon = ostatnie K tur) |
| Fuzz: 25 losowych sesji (127 przebiegów polityk, 1 778 porównań), 0 błędów | Rozkład wywołań `ls -R` w prawdziwych sesjach (tu: 18 tur dobranych przeze mnie) |
| Skala 4–120 modułów (7,29× → 13,16×) | `ls -R -L`, nazwy z `\n`/`" -> "`, BSD, inne systemy plików, drzewa >2 poziomów |
| Kolejność: `-S` 40/40, `-t` long-iso 0/40, `-t` full-iso 40/40 | Realne rozkłady mtime w repo (test `-t` celowo trudny) |
| 171 asercji (`test_lsepoch.py`), test negatywny (`gdelta`/`sdelta`/`proj` MUSZĄ się mylić) | mtime ustawiany `os.utime`; brak sprawdzenia, czy `/tmp/lsepoch-*` zostaje po przerwaniu |

## 🎯 Zapamiętaj

1. **Delta to łańcuch.** Kompakcja zrywa ogniwa; bez świadomości okna delta kłamie.
2. **Lenistwo bije gorliwość:** `chain` (4,45×) tańszy niż `carry` (3,89×), oba bez błędów.
3. **Jeden stan drzewa daje więcej niż cwaniactwo w deltach:** projekcja 5,74× → 9,49×, per-sekcyjne „cała sekcja zamiast delty” 0 zysku.
4. **Częściowa wiedza jest gorsza niż brak wiedzy** — i w narzędziu, i (prawdopodobnie) w modelu.

### ➡️ Następne kroki
- Weryfikacja w żywym `claude`: hak na wynik narzędzia, co przeżywa `/compact`.
- Ta sama maszyneria dla `git status`/`git diff --stat` (stan z zewnętrznym źródłem prawdy) i `find`.
- Prawdziwy transkrypt (gdy odczyt dozwolony): rozkład powtórzeń; reguły `CLAUDE.md` i „lost in the middle”; embeddingi.
