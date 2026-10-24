<div align="center">

# 📰 TECH PRASÓWKA
### Wydanie #8 rubryki — 13 października 2026

![AI/Kontekst](https://img.shields.io/badge/AI_%2F_Kontekst-8A5CF6?style=for-the-badge&logo=anthropic&logoColor=white)
![Wyszukiwanie](https://img.shields.io/badge/tool_search-synonimy_i_aliasy-F59E0B?style=for-the-badge)
![Ewaluacja](https://img.shields.io/badge/ewaluacja-dev%2Ftest%2Ffresh-10B981?style=for-the-badge)

## „Wycisz pager”, a narzędzie nazywa się `acknowledge_alert`. Jak naprawić wyszukiwarkę narzędzi i jak nie oszukać samego siebie

</div>

---

> _"Wyszukiwarka, która zna tylko słowa z nazwy narzędzia, zadziała świetnie dla autora katalogu.
> Dla wszystkich pozostałych użytkowników jest loterią."_

W [#14](../2026-10-07-264-narzedzia-w-kontekscie-z-ktorych-uzyjesz-12-eager/ARTICLE.md) leniwe ładowanie definicji narzędzi (tool search) obniżyło koszt
kontekstu 5,6–38×, ale zostawiło brzydki wynik: BM25 trafiał **10 z 18** zapytań i **wyższe `k` prawie
nie pomagało** (11/18 przy k=10). Zapowiedziałem wtedy synonimy i embeddingi. Dziś: co z tego da się
**zmierzyć** bez modelu embeddingowego i bez sieci — oraz coś ważniejszego niż sam wynik: jak
**ewaluować wyszukiwarkę, żeby liczby nie kłamały**.

**Hak:** w dwóch ruchach (słownik synonimów po stronie zapytania, aliasy po stronie dokumentu) recall@5 na
zbiorze „obejrzanym” skacze z 10/18 do 18/18. Na zapytaniach napisanych *po* zamrożeniu słownika jest już
tylko **26/30** (@5; @1: 21/30), a na trzecim zestawie 13/15 (@1: 8/15). Różnica między pierwszą a drugą
liczbą to efekt strojenia na obejrzanym zbiorze; drugą a trzecią — głównie *trudność* zestawu. Obie
lekcje są w artykule.

> ⚠️ **Uczciwie o danych.** Katalog jest **syntetyczny** (264 narzędzia, 8 serwerów — ten sam co w #14,
> skopiowany do kodu), tokeny = bajty/4. Zapytania, słownik i aliasy napisałem **ja** — jedna osoba, jeden
> styl, to nie jest niezależny benchmark. **Żaden model, API ani `claude` nie były uruchamiane.** Mierzę
> *jakość wyszukiwania* (czy narzędzie jest w top-k), nie to, czy model je potem dobrze wywoła.

---

## 1️⃣ Problem w jednym zapytaniu

`python3 -B ctxsearch.py query "silence the pager" --k 3` (szukane: `monitoring__acknowledge_alert`):

```
bm25                   ['monitoring__update_silence', 'monitoring__delete_silence', 'monitoring__create_silence']
ngram                  ['monitoring__list_silence', 'monitoring__create_silence', 'monitoring__update_silence']
bm25+syn               ['monitoring__acknowledge_alert', 'monitoring__list_silence', 'monitoring__list_alert']
bm25+alias             ['monitoring__acknowledge_alert', 'monitoring__delete_silence', 'monitoring__update_silence']
rrf(syn,alias,ngram)   ['monitoring__acknowledge_alert', 'monitoring__delete_silence', 'monitoring__list_silence']
```

Użytkownik (i model) mówi „silence” — jest w katalogu narzędzie `*_silence`, ale to **inna rzecz**
(reguła wyciszania w systemie monitoringu). Narzędzie, które realnie zatrzymuje powiadomienia, nazywa
się `acknowledge_alert`, a słowo „pager” pojawia się w jego opisie jako „paging”. Czysty BM25 jest
poprawny matematycznie i bezużyteczny praktycznie. To nie bug rankingu, tylko **luka słownikowa**.

---

## 2️⃣ Pięć retrieverów, każdy z innym zrozumieniem „podobieństwa”

| Retriever | Co robi | Czego **nie** potrafi |
|---|---|---|
| `bm25` | tokeny słów, nazwa ×3 + opis (jak w #14) | synonimów, fleksji (poza `-s`) |
| `ngram` | TF-IDF na trigramach znaków + cosinus | synonimów (ale łapie fleksję/literówki) |
| `bm25+syn` | **słownik synonimów dopisuje słowa do zapytania** (wyszukiwarka, 0 tokenów w kontekście) | słów spoza słownika |
| `bm25+alias` | **aliasy w opisie narzędzia** („Also known as: land ship integrate squash main”) | zmienia definicję — kosztuje tokeny |
| `rrf(...)` | fuzja rankingów (Reciprocal Rank Fusion, k=60) | naprawić słaby ranking składowy |

Dwa ważne rozróżnienia, które w praktyce się myli:

- **Słownik po stronie zapytania** żyje w wyszukiwarce. Nie dotyka kontekstu modelu, ale musi go ktoś
  utrzymywać po stronie *klienta/hosta* (nie po stronie serwera MCP).
- **Aliasy po stronie dokumentu** żyją w opisie narzędzia, czyli może je dodać **autor serwera** — ale
  każda załadowana definicja robi się większa: **26 380 → 29 750 tok. (+3 370, +12,8%)** dla całego katalogu,
  śr. 99,9 → 112,7 tok. Płacisz tylko za załadowane narzędzia, ale płacisz w każdej turze.

> 💡 To ta sama dwoistość co w bazach pełnotekstowych: *query expansion* vs *document expansion*.
> Embeddingi to w istocie „słownik synonimów nauczony z danych” — którego tu **nie testowałem**
> (bez modelu embeddingowego, stdlib). Wniosek poniżej o „synonimach” jest więc dolną granicą wiedzy,
> nie opisem embeddingów.

---

## 3️⃣ Wyniki: trzy zestawy zapytań, trzy różne prawdy

Zestawy (`ctxsearch.py`): **dev** = 18 zapytań z #14 (słownik budowałem, *wiedząc* o nich),
**test** = 30 zapytań napisanych po zamrożeniu słownika i aliasów, przed pierwszym uruchomieniem,
**fresh** = 15 zapytań również napisanych przed pierwszym uruchomieniem, ale **nieużytych** do dopisywania
haseł po obejrzeniu błędów testu (sekcja 4). Różnica test/fresh to więc nie „przeuczenie”, tylko inny
skład: w fresh 6 z 15 zapytań nie ma wspólnego słowa z celem (40%), w test 9 z 30 (30%).

`python3 -B ctxsearch.py eval` (cele: czy narzędzie w top-1 / top-3 / top-5; MRR):

```
| retriever | dev: @1 / @3 / @5 / MRR | test: @1 / @3 / @5 / MRR | fresh: @1 / @3 / @5 / MRR |
|---|---|---|---|
| bm25 | 10/18 / 10/18 / 10/18 / 0.56 | 8/30 / 14/30 / 17/30 / 0.41 | 5/15 / 8/15 / 11/15 / 0.49 |
| ngram | 7/18 / 9/18 / 9/18 / 0.45 | 10/30 / 17/30 / 19/30 / 0.45 | 3/15 / 4/15 / 4/15 / 0.28 |
| bm25+syn | 18/18 / 18/18 / 18/18 / 1.00 | 21/30 / 24/30 / 26/30 / 0.77 | 8/15 / 11/15 / 13/15 / 0.67 |
| bm25+alias | 15/18 / 17/18 / 17/18 / 0.88 | 20/30 / 21/30 / 24/30 / 0.72 | 8/15 / 12/15 / 12/15 / 0.65 |
| rrf(bm25,ngram) | 8/18 / 9/18 / 9/18 / 0.48 | 8/30 / 16/30 / 17/30 / 0.41 | 2/15 / 7/15 / 8/15 / 0.31 |
| rrf(syn,alias,ngram) | 17/18 / 18/18 / 18/18 / 0.97 | 21/30 / 25/30 / 27/30 / 0.77 | 5/15 / 11/15 / 11/15 / 0.51 |
| bm25+stop | 9/18 / 9/18 / 9/18 / 0.51 | 10/30 / 14/30 / 17/30 / 0.44 | 6/15 / 8/15 / 9/15 / 0.47 |
| rrf(syn,alias,ngram)+stop | 17/18 / 18/18 / 18/18 / 0.97 | 22/30 / 24/30 / 27/30 / 0.79 | 7/15 / 11/15 / 11/15 / 0.60 |
```

Co z tego wynika:

1. 🎭 **Ta sama metoda: 100% (dev) → 70% (test) na @1** (`bm25+syn`: 18/18 vs 21/30; @5: 18/18 vs 26/30).
   Zbiór, na którym projektowałeś słownik, jest bezużyteczny do oceny słownika. Trzeci zestaw (fresh: 8/15 @1,
   13/15 @5) jest jeszcze niższy, ale to głównie zestaw trudniejszy (więcej zapytań bez wspólnego słowa),
   nie dowód kolejnego przeuczenia — nie umiem tego rozdzielić na 15 zapytaniach.
2. 🧮 **Słownik wygrywa** (`bm25+syn`): z bazowego 17/30 do 26/30 @5 na teście. To nie embeddingi i nie
   magia — to kilkadziesiąt ręcznych haseł.
3. 🔀 **Fuzja z n-gramami nie pomogła**, a miejscami zaszkodziła: `rrf(bm25,ngram)` ≈ `bm25`
   (17/30 @5 test), a `rrf(syn,alias,ngram)` na fresh ma 11/15 przy 13/15 samego `bm25+syn`.
   Fuzja uśrednia, więc **słaby składnik rozcieńcza silny**. RRF działa, gdy składniki są
   *komplementarne i porównywalnie dobre* — tu jeden jest słaby.
4. 🔤 **N-gramy znaków** nie rozwiązują synonimów, tylko fleksję (`merged` → `merge`): 19/30 @5 na teście
   (więcej niż bm25 17/30), ale na fresh tylko 4/15.
5. 🧹 **Lista stop-słów** (dodana *po* obejrzeniu pierwszych wyników, więc traktuj jako post-hoc):
   dla `bm25` zmiana −1/0/−2 @5 na dev/test/fresh — nic dobrego. Zdziwiło mnie to, bo błędne trafienia
   `calendar__delete_*` wyglądały na skutek słowa „this” z opisów `delete` („This action cannot be undone”).
   Jego usunięcie nie pomogło; prawdopodobnie pozostałe słowa zapytania nadal nie mają dopasowania
   (przyczyny osobno nie badałem).

### Najważniejszy podział: czy zapytanie dzieli słowo z celem?

`python3 -B ctxsearch.py overlap` (63 zapytania razem; „wspólne słowo” = token nie-stop z nazwy lub opisu celu):

```
| podzbior | n | bm25 | ngram | bm25+syn | bm25+alias | rrf(bm25,ngram) | rrf(syn,alias,ngram) |
| ze wspolnym slowem (recall@5) | 40 | 34/40 | 29/40 | 38/40 | 36/40 | 34/40 | 38/40 |
| bez wspolnego slowa (recall@5) | 23 | 4/23 | 3/23 | 19/23 | 17/23 | 0/23 | 18/23 |
```

**BM25 trafia 34/40, gdy zapytanie dzieli słowo z narzędziem, i 4/23, gdy nie dzieli.** Cała „jakość”
wyszukiwarki to w praktyce ten drugi wiersz. Średnia (38/63) ukrywa dwa zupełnie różne światy.
Dlatego `recall@k` bez takiego podziału jest myląca. (Podział automatyczny, nie moje ręczne etykiety.)

---

## 4️⃣ Gdzie nadal pada

`python3 -B ctxsearch.py failures` (fragment listy porażek `rrf(syn,alias,ngram)` poza top-5; polecenie
drukuje też `bm25`, gdzie porażek jest 17):

```
[fresh] 'hand the task over to Carol' -> jira__assign_ticket: pozycja 71; top-3: ['jira__transition_ticket', ...]
[fresh] 'spin up extra copies of the api' -> kubernetes__scale_deployment: pozycja 6; top-3: ['jira__update_sprint', ...]
[fresh] 'post to the engineering room' -> slack__post_message: pozycja 7; top-3: ['calendar__get_room', ...]
[test]  'what indexes does the database have' -> postgres__list_index: pozycja 47; ...
```

Trzy rodzaje porażek, każdy z innym lekarstwem:

- **Luka słownikowa** („hand over”, „copies”): trzeba dopisać hasło. Zawsze będzie następna.
- **Pułapka słowa-nośnika**: „engineering **room**” → `calendar__*_room`, bo „room” to rzeczownik w
  innym serwerze. Lekarstwo „room → channel” w słowniku (nie testowane) psułoby z kolei zapytania o salę
  w kalendarzu. Synonimy bez kontekstu serwera to broń obosieczna.
- **Fleksja `-es`**: `indexes` nie sprowadza się do `index` (test w kodzie dokumentuje tę lukę
  jawnie: `check("index" not in lookup_forms("indexes"))`).

### Co daje „podglądanie” błędów

`python3 -B ctxsearch.py peek` — po obejrzeniu błędów testu dopisałem **4 hasła** (`indexes`, `restart`,
`mute`, `alarm`):

```
| zestaw | bm25+syn przed (@5) | po dopisaniu (@5) | zmiana |
| test (OBEJRZANY) | 26/30 | 28/30 | +2 |
| fresh (swiezy) | 13/15 | 14/15 | +1 |
```

Na obejrzanym zbiorze +2, na świeżym +1 (najpewniej `restart` pokrył „restarting pods” — nie sprawdzałem
które zapytanie). Reszta świeżych porażek („hand over”, „copies”) nie ma hasła i nie będzie miała, dopóki
ktoś ich nie zobaczy. Na fuzji `rrf(syn,alias,ngram)` na fresh efekt to **0** (test: +1). Zysk z dopisywania
haseł po błędach jest wiarygodny tylko w takim stopniu, w jakim nowe zapytania wpadają na te same słowa —
a na obejrzanym zbiorze zawsze wygląda lepiej.

---

## 5️⃣ Ile to kosztuje w tokenach

`python3 -B ctxsearch.py cost` (63 zapytania; „tok. przy k” = k × śr. definicja; k = minimalne, przy którym
recall ≥ 90%):

```
| retriever | recall@1 | @3 | @5 | @10 | k dla recall>=90% | tok. przy tym k |
| bm25 | 23/63 | 32 | 38 | 44 | >264 | - |
| ngram | 20/63 | 30 | 32 | 38 | 226 | 22583 |
| bm25+syn | 47/63 | 53 | 57 | 60 | 5 | 500 |
| bm25+alias | 43/63 | 50 | 53 | 57 | 10 | 1127 |
| rrf(bm25,ngram) | 18/63 | 32 | 34 | 39 | 180 | 17986 |
| rrf(syn,alias,ngram) | 43/63 | 54 | 56 | 60 | 6 | 676 |
```

To jest ekonomia, o której zrobiliśmy cały cykl: **kiedy retriever jest słaby, kupujesz recall tokenami**.
`bm25` nie dobija do 90% nawet przy k=264 (część zapytań nie ma żadnego trafienia, pozycja „brak”; recall
rośnie wolno: 38/63 przy k=5, 44/63 przy k=10), więc
„załaduj więcej wyników” nie jest remedium — zgodnie z obserwacją z #14. `bm25+syn` osiąga 90%
przy k=5 (~500 tok.). Aliasy w opisach są droższe (k=10, ~1127 tok.) i, w tym teście, gorsze od słownika
po stronie zapytania. Uwaga: te liczby to 63 zapytania z trzech zestawów (w tym `dev`, na którym słownik jest
dopasowany), więc **są optymistyczne** — wiarygodniejszy jest wiersz `fresh` z sekcji 3.

---

## 6️⃣ Prior sesji: wyszukiwarka, która wie, czego dziś używasz

Kolejna luka: niejednoznaczność. `comment` jest i w `jira`, i w `github` (`review_comment`).
Wyszukiwarka może **podbić** wynik narzędzi z serwerów już użytych w sesji (mnożnik 1 + boost).
`python3 -B ctxsearch.py prior` (12 zapytań: 8 niejednoznacznych + 4 wprost nazywające serwer):

```
| boost | bm25 | rrf(syn,alias,ngram) |
| 0.0 | 8/12 @1 | 8/12 @1 |
| 0.1 | 12/12 @1 | 12/12 @1 |
| 0.25 | 12/12 @1 | 12/12 @1 |
| 1.0 | 12/12 @1 | 12/12 @1 |
| 3.0 | 11/12 @1 | 11/12 @1 |

boost=0.0: 'create comment' sesja=['github']: top-1 = jira__create_comment, oczekiwane github__create_review_comment
boost=3.0: 'postgres run sql' sesja=['jira', 'github']: top-1 = github__search_workflow_run, oczekiwane postgres__run_sql
```

Dwie lekcje:

1. 🕳️ **Bez priora wygrywa `jira` za każdym razem** — również gdy sesja jest w `github`. To ukryte
   obciążenie rankingu (prawdopodobnie normalizacja długości BM25; przyczyny osobno nie badałem). Nikt
   nie zaprogramował „preferuj Jirę” — a system ją preferuje.
2. 💣 **Za mocny prior zjada jawne intencje**: przy boost 3,0 zapytanie „postgres run sql” przegrywa z
   narzędziami serwerów już otwartych w sesji. Zakres 0,1–1,0 działał na tym małym zbiorze, ale **12
   zapytań, jedna rodzina niejednoznaczności** to za mało, żeby ufać konkretnej wartości. Traktuj to
   jako demonstrację mechanizmu, nie rekomendację stałej.

---

## 7️⃣ Checklista

| # | Reguła | Dlaczego |
|---|---|---|
| 1 | **Ewaluuj na zapytaniach, których nie widziałeś przy strojeniu** | dev 18/18 vs test 26/30 @5 |
| 2 | **Dziel zapytania: ze wspólnym słowem vs bez** | bm25: 34/40 vs 4/23 |
| 3 | **Mierz @1 i @5, nie tylko @10** | @1 pokazuje różnicę ostrzej (dev 100% vs test 70%) |
| 4 | **Synonimy w wyszukiwarce, nie w kontekście** — o ile masz na to kontrolę | 0 tok. vs +12,8% przy aliasach |
| 5 | **Jeśli piszesz własny MCP: dodaj w opisie „kiedy użyć” słowami użytkownika** | autor serwera jest jedyną stroną, która może to zrobić |
| 6 | **Nie fuzuj słabego z silnym bez pomiaru** | rrf(bm25,ngram) ≈ bm25; rrf3 < syn na fresh |
| 7 | **Prior sesji ostrożnie** | 0 → 8/12, 0,1–1,0 → 12/12, 3,0 → 11/12 |
| 8 | **Loguj porażki wyszukiwania (zapytanie → co wybrał model)** | jedyne źródło prawdziwych luk słownikowych |

---

## 🧪 Co zweryfikowano, a co nie

| ✅ Zmierzone (kod, Python 3.10.4, stdlib) | ❓ Niezweryfikowane |
|---|---|
| 8 retrieverów × dev/test/fresh na katalogu 264 narzędzi (SYNTETYCZNYM) | Embeddingi / realny model (brak w stdlib; „semantyka” = ręczny słownik) |
| Różnica obejrzany vs nieobejrzany zbiór (dev 100% vs test 70% @1) | Że moje zapytania przypominają zapytania prawdziwych użytkowników / modelu |
| Podział na ze/bez wspólnego słowa (34/40 vs 4/23 bm25) | Jak model **sam** formułuje zapytanie do `tool_search` (może używać słów z nazw!) |
| Koszt aliasów: +3 370 tok. (+12,8%) | Realna dokumentacja i zachowanie narzędzia tool search w Claude Code (WebFetch odrzucone) |
| Prior sesji: 8/12 → 12/12, a za mocny psuje | Wpływ priora na prompt cache, niejednoznaczność poza rodziną `comment` |
| 40 asercji (`test_ctxsearch.py`) | Autor jeden: zbiory test/fresh nie są niezależne; wartości stop-listy dodane post-hoc |

## 🎯 Zapamiętaj

1. **Luka słownikowa to główna porażka wyszukiwania narzędzi**: 4/23, gdy zapytanie nie dzieli słowa z celem.
2. **Słownik synonimów daje dużo, ale mierz go na świeżych zapytaniach** — zbiór „obejrzany” zawyża wynik.
3. **Fuzja nie jest darmowym lunchem**: słaby składnik rozcieńcza silny.
4. **Prior sesji** naprawia niejednoznaczność, ale za duży zjada jawne intencje.
5. **Zbiór testowy z logów prawdziwych porażek** jest warty więcej niż każdy sprytny retriever.

### ➡️ Następne kroki
- Prawdziwy model embeddingowy lub choćby embeddingi zapytań z dokumentacji (poza stdlib) — i ta sama ewaluacja dev/test/fresh.
- Zapytania pisane **przez model** (nie przeze mnie) do tego samego katalogu — czy używa słów z nazw narzędzi?
- Weryfikacja w żywym `claude`/dokumentacji: nowa sesja, wznowienie, `/compact`.
- Reguły `CLAUDE.md` i „lost in the middle” (nadal otwarte).
