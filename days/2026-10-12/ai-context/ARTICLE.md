<div align="center">

# 📰 TECH PRASÓWKA
### Wydanie #7 rubryki — 12 października 2026

![AI/Kontekst](https://img.shields.io/badge/AI_%2F_Kontekst-8A5CF6?style=for-the-badge&logo=anthropic&logoColor=white)
![Fold](https://img.shields.io/badge/snapshot-fold_zdarze%C5%84-F59E0B?style=for-the-badge)
![Weryfikacja](https://img.shields.io/badge/weryfikator-verify-10B981?style=for-the-badge)

## Notatki sesji: nie dopisuj, składaj. Snapshot stanu zamiast logu

</div>

---

> _"Dziennik pokładowy mówi, co się działo. Tablica rozdzielcza mówi, w jakim jesteś stanie.
> Do kolejnej zmiany wachty potrzebujesz tablicy, nie dziennika."_

W [#15](../2026-10-08/ai-context/ARTICLE.md) zapisaliśmy, że handoff to „żywe decyzje + wskaźniki”, a
polityka `boundary+all` (dopisuj wszystko) wypadła zaskakująco dobrze, ale „rośnie monotonicznie”, zaś
`all_capped` (ucinanie od najstarszych) gubiło fundamenty. Zostawiłem wtedy otwarty punkt: **jak
utrzymać plik stanu ograniczony rozmiarem bez gubienia tego, co jeszcze obowiązuje?** Dziś odpowiedź
z poziomu mechanizmu: **fold** — przepisujemy log zdarzeń na snapshot stanu, tak jak robi to
event sourcing albo `git` ze swoim indeksem.

**Hak: dopisywany plik notatek jest kosztem *i* pułapką.** Kosztem, bo rośnie liniowo i płacisz
za niego w każdej turze. Pułapką, bo po 100 nadpisanych decyzjach w pliku leżą **równocześnie** stare i
nowe wartości — a czytelnik (model czytający od góry, `grep -m1`, człowiek po urlopie) bierze pierwszą,
nie ostatnią. W naszym teście naiwny czytelnik trafia **59%** poprawnych faktów z logu, a **100%** ze
snapshotu 10,7× mniejszego.

> ⚠️ **Uczciwie o danych.** Strumień zdarzeń jest **syntetyczny** (300 zdarzeń, deterministyczny LCG,
> reguły w kodzie), tokeny = bajty/4. **Żaden model ani CLI nie były uruchamiane.** Liczby pokazują
> **strukturę** zjawiska (liniowy wzrost vs rozmiar stanu, błędy czytelnika, niezmienniki foldu), nie
> zachowanie Claude'a. To, jak dobrze **model** składa snapshot, jest **niezweryfikowane** — dlatego
> zamiast wierzyć, dostajemy weryfikator (sekcja 5).

---

## 1️⃣ Strumień zdarzeń: pięć typów, jeden stan

Zamiast prozy „co się stało” sesja zapisuje **typowane zdarzenia** (`python3 -B ctxfold.py stats`):

```
zdarzen: 300, operacje: {'add': 61, 'del': 15, 'inc': 44, 'rm': 40, 'set': 140}
klucze zmiennych: 35, nadpisanych >=2x: 17, nadpisan lacznie: 105
stan koncowy: 20 zmiennych, 21 elem. zbiorow, 1 liczniki
log w calosci: 6037 tok., snapshot: 565 tok.
```

| Op | Znaczenie | Przykład w sesji |
|---|---|---|
| `SET k = v` | ostatni zapis wygrywa | `decision/orders`, `conv/errors` |
| `DEL k` | klucz znika | notatka robocza `tmp/7` zamknięta |
| `ADD s += x` / `RM s -= x` | zbiór | lista `todo`, `pitfall` |
| `INC n += 1` | licznik | `done` (ile jednostek zamknięto) |

Z 300 zdarzeń **stan końcowy to 42 elementy**: 20 zmiennych, 21 elementów zbiorów, 1 licznik.
Pozostałe ~250 zdarzeń to historia, której kolejne okno **nie potrzebuje**, żeby działać (potrzebuje jej,
żeby *rozumieć dlaczego* — o tym w sekcji 4).

> 💡 To ten sam pomysł, który w #15 nazwałem `live`: „zabierz decyzje, których potrzebuje reszta
> pracy”. Tu jest on **mechaniczny**: nie wybierasz, co zabrać; funkcja `fold` robi to deterministycznie,
> bo każde zdarzenie wie, co unieważnia.

---

## 2️⃣ Rozmiar: liniowy log vs ograniczony stan

`python3 -B ctxfold.py sizes` (tokeny tekstu, który dostaje nowe okno; `cap` = ucinanie od najstarszych):

```
| t | append_all tok | append_cap(1500) tok | fold tok | fold_every(25) tok | stan: zm./elem./licz. |
|---|---|---|---|---|---|
| 25 | 596 | 596 | 165 | 165 | 9/3/1 |
| 50 | 1092 | 1092 | 243 | 243 | 14/5/1 |
| 100 | 2125 | 1528 | 339 | 339 | 14/13/1 |
| 150 | 3136 | 1504 | 431 | 431 | 17/19/1 |
| 200 | 4084 | 1493 | 473 | 473 | 16/19/1 |
| 250 | 5026 | 1509 | 535 | 535 | 17/21/1 |
| 300 | 6037 | 1524 | 565 | 565 | 20/21/1 |
```

(wybrane wiersze; pełna tabela ma co 25 zdarzeń). `append_all` rośnie ~20 tok. na zdarzenie. `fold`
rośnie z **liczbą żywych elementów**, nie z liczbą zdarzeń: między t=200 a t=225 snapshot nawet
**maleje** (473 → 455 tok.; zbiory się kurczą, notatki `tmp/*` są kasowane), a log rośnie o 428 tok.

Uczciwie: snapshot **nie jest** ograniczony z góry. Zbiory typu `pitfall` (tylko `ADD`) rosną do końca;
w tym teście to 18 z 21 elementów zbiorów i większość z 565 tok. Fold gwarantuje „rośnie z żywym stanem”,
a nie „nigdy nie urośnie”. Zbiory add-only trzeba przycinać świadomie (np. pułapki z numerem
jednostki, które już nie dotyczą).

---

## 3️⃣ Dwóch czytelników, pięć polityk

Rozmiar to połowa rachunku. Druga: **co czytelnik odtworzy**. Zbudowałem dwóch (`reader_correct`,
`reader_naive`), oba na tym samym tekście:

- **poprawny** — odtwarza zdarzenia po kolei (ostatni zapis wygrywa, `RM` usuwa, `INC` sumuje);
- **naiwny** — bierze **pierwszą** wzmiankę zmiennej, sumuje wszystko co kiedykolwiek `ADD`-owane
  (ignoruje `RM`), ignoruje `DEL`. To realistyczny model „model/człowiek czyta od góry i zatrzymuje się
  na pierwszym trafieniu”.

`python3 -B ctxfold.py compare --t 300` (prawda = 42 elementy; „spurious” = elementy przypisane, których
w prawdzie nie ma, np. zadanie już zamknięte, albo zły licznik):

```
| polityka | tok. | prawda: elem. | czyt. poprawny: ok | spurious | czyt. naiwny: ok | spurious |
|---|---|---|---|---|---|---|
| append_all | 6037 | 42 | 42 (100%) | 0 | 25 (59%) | 60 |
| append_cap(1500) | 1524 | 42 | 22 (52%) | 1 | 12 (28%) | 18 |
| append_cap(500) | 504 | 42 | 12 (28%) | 1 | 9 (21%) | 5 |
| fold | 565 | 42 | 42 (100%) | 0 | 42 (100%) | 0 |
| fold+dlaczego | 932 | 42 | 42 (100%) | 0 | 42 (100%) | 0 |
| fold_every(25) | 565 | 42 | 42 (100%) | 0 | 42 (100%) | 0 |
```

Co z tego wynika:

- 🪤 **`append_all`**: dla poprawnego czytelnika bezbłędny, ale dla naiwnego **60 elementów
  „widmo”** (zamknięte zadania, nadpisane decyzje) i 59% trafień. Dane są wszystkie, a użyteczność —
  zależna od tego, *kto* czyta.
- ✂️ **`append_cap`** (ucinanie od najstarszych): przy limicie 1500 tok. poprawny czytelnik odtwarza
  **52%**. Tracimy to, co nigdy nie było nadpisane i dawno temu: **konwencje z t ≤ 6**. W kodzie
  jest asercja, że przynajmniej jedna konwencja `conv/*` znika (to ten sam mechanizm co `all_capped` z #15).
  Jedyny „spurious” u poprawnego czytelnika to licznik `done` zaniżony przez uciętą historię.
- 📸 **`fold`**: 565 tok., 100% u **obu** czytelników. Snapshot ma tę zaletę, że nie wymaga od
  czytelnika żadnej logiki — to *już jest* stan.

### Haczyk: snapshot + ogon

Praktyczny wariant: składaj co `k` zdarzeń, a między foldami dopisuj surowe zdarzenia (`fold_every`).
Tu naiwny czytelnik znów się myli, bo snapshot jest **na górze**, a nadpisanie w ogonie **poniżej**.
`python3 -B ctxfold.py tail` (średnia po t = 10..300):

```
| polityka | sr. tok. | max tok. | naiwny: sr. dokladnosc | poprawny: sr. dokladnosc |
|---|---|---|---|---|
| fold (co zdarzenie) | 392 | 568 | 100.0% | 100.0% |
| fold_every(5) | 434 | 680 | 97.6% | 100.0% |
| fold_every(10) | 481 | 748 | 95.3% | 100.0% |
| fold_every(25) | 606 | 1049 | 91.1% | 100.0% |
| fold_every(50) | 841 | 1521 | 86.2% | 100.0% |
| fold_every(100) | 1296 | 2400 | 79.5% | 100.0% |
| append_all | 3161 | 6037 | 70.7% | 100.0% |
```

Dokładność naiwnego czytelnika spada **gładko wraz z długością ogona** (100% → 91% → 80%), a rozmiar
rośnie. Reguła: **ogon ma być krótki albo jawnie oznaczony** („zmiany od snapshotu — nadpisują wartości
powyżej”). Pojedynczy punkt t=290 z fold_every(25): 861 tok., naiwny 85% (34/40) i 8 elementów
spurious; poprawny 100%.

---

## 4️⃣ Co fold gubi (i czy to boli)

Fold jest **stratny z założenia**: znika historia i uzasadnienia. Zmierzyłem koszt jednego uzasadnienia
(„dlaczego”) na żywą decyzję: `fold+dlaczego` = **932 tok. vs 565** (+65%). Ten wybór jest polityką,
nie techniką:

| Wariant | Gdy |
|---|---|
| `fold` bez „dlaczego” | decyzje są oczywiste z kodu/testów, a log leży w repo pod wskaźnikiem |
| `fold` z „dlaczego” przy żywych decyzjach | nowe okno może te decyzje *kwestionować* (code review, refaktor) |
| log w repo + snapshot w kontekście | zawsze: historia jest pod `docs/log/events.log`, nie w oknie |

Dwa niezmienniki, które trzeba mieć, żeby fold był bezpieczny — oba są w testach:

1. **Asocjacyjność**: `fold(snapshot(a) + b) == fold(a + b)`. Sprawdziłem to na 200 losowych
   podziałach (4 ziarna × 50) plus łańcuch 30 foldów po 10 zdarzeń: wszystko równe. Bez tego
   „składaj co jakiś czas” zmieniałoby wynik.
2. **Kolejność**: fold **nie jest przemienny** (dwa `SET` tego samego klucza). Gdy zdarzenia
   przychodzą od kilku subagentów w złej kolejności: `python3 -B ctxfold.py order` →
   `52 elem. różnicy bez sortowania, 0 po sortowaniu po t`. Zdarzenia potrzebują znacznika
   porządku (czas/seq), inaczej „ostatni zapis wygrywa” jest przypadkowy.

---

## 5️⃣ Weryfikator: nie ufaj snapshotowi napisanemu przez model

Pomysł praktyczny, bo składanie snapshotu często robi model (prozą), a nie skrypt. Tego **nie
mierzyłem**, ale mam narzędzie, które pozwala to sprawdzić tanio: `ctxfold.py verify PLIK`
porównuje snapshot z logiem zdarzeń i klasyfikuje błędy. Poniżej `SNAPSHOT.bad.example.md` — snapshot
z 6 ręcznie wstrzykniętymi błędami (to **symulacja** błędów modelu, nie ich pomiar):

```
BLAD: BRAK: conv/tests
BLAD: PRZESTARZALA wartosc: decision/orders
BLAD: BLEDNA wartosc: decision/audit
BLAD: NADMIAR (usuniete lub zmyslone): decision/gateway
BLAD: NADMIAR elementu: todo += usun Polly retry
BLAD: LICZNIK done: jest 41, ma byc 44
6 problemow
```

Sześć wstrzykniętych, sześć wykrytych (exit code 1). Rozróżnienie `PRZESTARZALA` vs `BLEDNA` ma
znaczenie diagnostyczne: pierwsze to wartość, która **kiedyś była prawdziwa** (model skopiował z
początku logu), drugie — wartość wymyślona. Dla prawdziwego snapshotu: `OK: snapshot zgodny z logiem`.

Schemat pracy, który z tego wynika:

```
log zdarzen (repo)  --fold-->  SNAPSHOT.md  --verify-->  nowe okno
     ^                              ^
  hook / skrypt              (model może go
  dopisuje                    skladac, ale go sprawdzamy)
```

Wymaga to oczywiście, żeby zdarzenia były **typowane** — z prozy „zdecydowaliśmy się na outbox” nie
da się maszynowo wyprowadzić, które klucze to unieważnia. Ta cena jest realna: musisz mieć format
(tu: 5 operacji i klucze `decision/<moduł>`). Jeśli go nie masz, zostaje ręczne `all_capped`
z gubieniem fundamentu.

---

## 6️⃣ Checklista

| # | Reguła | Skąd |
|---|---|---|
| 1 | **Zapisuj zdarzenia typowane** (`SET/DEL/ADD/RM/INC`), nie prozę | bez tego brak foldu i weryfikatora |
| 2 | **Do okna daj snapshot, log trzymaj w repo** pod wskaźnikiem | 565 vs 6037 tok. |
| 3 | **Snapshot, nie ucinanie od najstarszych** | cap 1500: 52% stanu; fold: 100% |
| 4 | **Ogon po snapshocie krótki i oznaczony** | ogon 100 zdarzeń: naiwny 79,5% |
| 5 | **Znacznik porządku na zdarzeniu** | bez sortowania 52 elem. rozjazdu |
| 6 | **Przycinaj zbiory add-only** | `pitfall` to większość snapshotu |
| 7 | **„Dlaczego” tylko dla żywych decyzji, jeśli ma być kwestionowane** | +65% tokenów |
| 8 | **Weryfikuj snapshot napisany przez model** | `verify`: 6/6 wstrzykniętych błędów |

---

## 🧪 Co zweryfikowano, a co nie

| ✅ Zmierzone (kod, Python 3.10.4, stdlib) | ❓ Niezweryfikowane |
|---|---|
| Strumień 300 zdarzeń (SYNTETYCZNY): 6037 tok. log vs 565 tok. snapshot (10,7×) | Jak model sam składa snapshot i jak go czyta (żaden model nie uruchamiany) |
| Czytelnik poprawny/naiwny: 100%/59% na logu, 100%/100% na snapshocie | Czy realny model zachowuje się jak „czytelnik naiwny” (to mój model, nie obserwacja) |
| Cap 1500 tok.: 52% stanu; cap 500: 28% | Realne rozkłady nadpisań (tu 105 nadpisań na 35 kluczy, `decision/orders` aż 16×) |
| Ogon: 100 → 79,5% naiwnego czytelnika; asocjacyjność na 200 podziałach | Format zdarzeń w Twoim projekcie; koszty utrzymania logu |
| `verify`: 6/6 wstrzykniętych błędów, rozróżnienie przestarzała/błędna | Wstrzyknięte błędy to symulacja, nie rozkład błędów modelu |
| 31 asercji (`test_ctxfold.py`) | `claude`/`/compact`: nadal nie sprawdzano — dokumentacji i CLI nie otwierałem w tym wydaniu |

## 🎯 Zapamiętaj

1. **Dopisywanie jest tanie dziś i drogie jutro**: liniowy koszt plus widma przestarzałych wartości.
2. **Fold = log zdarzeń → stan**; rozmiar rośnie z żywym stanem, nie z historią. Ale zbiory add-only trzeba przycinać.
3. **Ucinanie od najstarszych gubi fundament** (konwencje z początku) — snapshot nie.
4. **Ogon po snapshocie to pułapka dla czytelnika od góry**: krótki i opisany.
5. **Nie ufaj snapshotowi napisanemu prozą** — `verify` kosztuje milisekundy.

### ➡️ Następne kroki
- Weryfikacja w dokumentacji i na żywym `claude`: nowa sesja, wznowienie, co realnie przeżywa `/compact` (nadal otwarte).
- Wyszukiwarka z synonimami / embeddingami na zestawie z #14.
- Analiza prawdziwego transkryptu (gdy odczyt będzie dozwolony).
- Reguły `CLAUDE.md` i „lost in the middle” (czy pozycja snapshotu w prompcie ma znaczenie).
