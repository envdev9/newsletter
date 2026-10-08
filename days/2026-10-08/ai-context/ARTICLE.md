<div align="center">

# 📰 TECH PRASÓWKA
### Wydanie #6 rubryki — 8 października 2026

![AI/Kontekst](https://img.shields.io/badge/AI_%2F_Kontekst-8A5CF6?style=for-the-badge&logo=anthropic&logoColor=white)
![Okna](https://img.shields.io/badge/okna_kontekstu-handoff-F59E0B?style=for-the-badge)
![Cięcie](https://img.shields.io/badge/kryteria_cięcia-granica_jednostki-10B981?style=for-the-badge)

## Zadanie 2,8× większe niż okno: gdzie ciąć i co zabrać do następnego okna

</div>

---

> _"Nowe okno kontekstu to nie reset. To przeprowadzka: zabierasz tylko to, co zmieści się w
> kartonie, a resztę musisz odkopać od nowa."_

W [#13](../../2026-10-06/ai-context/ARTICLE.md) uczyliśmy się **kompresować wyniki narzędzi**, w
[#14](../../2026-10-07/ai-context/ARTICLE.md) **odraczać definicje narzędzi**. Obie sztuczki
zmniejszają to, co leci w kontekście, ale długie zadanie (migracja 24 modułów, wielka refaktoryzacja)
i tak w końcu przestaje się mieścić w jednym oknie. Dziś ostatnia linia obrony z listy "Następne":
**dzielenie zadania na okna** - kiedy ciąć, co zapisać do pliku handoff i jak to zmierzyć.

**Hak: o koszcie decyduje nie liczba okien, tylko to, co się zgubi przy przejściu.** W naszym modelu
próg cięcia ma szeroki, płaski dołek (30-90 tys. tok. różni się o ~14%), a polityka handoffu
potrafi zmienić koszt o 20-60%. Większość ludzi stroi to, co mało się liczy (kiedy ciąć), a
nie to, co się liczy (czy w nowym oknie jest wszystko, czego dalsze kroki potrzebują).

> ⚠️ **Uczciwie o danych.** To jest **model kosztów, nie pomiar Claude'a**. Zadanie jest
> **syntetyczne**: 24 jednostki pracy, deterministyczne rozmiary tur (LCG), zależności zadane
> regułą w kodzie. **Żaden model ani CLI nie były uruchamiane** - nie wiem, jak dobrze model
> pisze handoff ani jak go czyta. Mnożniki ceny cache (odczyt 0,1x, zapis 1,25x) to **moje
> założenie z pamięci, niezweryfikowane**; model ignoruje wygasanie cache (TTL) i cenę tokenów
> wyjściowych. Wnioski dotyczą **struktury kosztu**, nie konkretnych liczb w Twoim projekcie.

---

## 1️⃣ Zadanie: 553 784 tokenów w oknie 200 000

`python3 -B ctxsplit.py plan` (prawdziwy output, fragment):

```
jednostek: 24, suma tokenow pracy: 543784, srednio 22657 / jednostke (min 13458, max 32507)
okno 200000, baza 10000: praca bez ciec to 553784 tok. = 2.77x okna
zaleznosci: 64 (odleglosc <=1: 23, >3: 34)
```

Jednostka = moduł do przeniesienia: 4-8 tur, po 1500-6000 tok. (odczyty, wyniki testów, diffy).
**Baza 10 000 tok.** to system + narzędzia + pamięć - z [#3](../../2026-09-27/ai-context/ARTICLE.md)
i [#14](../../2026-10-07/ai-context/ARTICLE.md) wiesz, że to parametr, który możesz mocno
zmieniać. Każda jednostka **zostawia po sobie decyzję** (120-300 tok.), a późniejsze jednostki jej
potrzebują. Z 64 zależności tylko 23 dotyczą poprzednika; **34 sięgają dalej niż 3 jednostki
wstecz** (np. wszystkie zależą od konwencji z jednostki 0). To jest sedno: **streszczenie "tego
co było ostatnio" gubi dokładnie te zależności, które są najdalej**.

---

## 2️⃣ Co mierzymy: dwie liczby kosztu i jedna jakości

| Metryka | Co znaczy |
|---|---|
| 🧮 **token-tury** | suma rozmiaru kontekstu po każdej turze (jak w [#2](../../2026-09-26/ai-context/ARTICLE.md)) - bez cache |
| 💰 **koszt ważony cache** | tura płaci 0,1x za prefiks z poprzedniej tury i 1,25x za nowe tokeny; nowe okno startuje z zimnym prefiksem (założenie!) |
| 🕳️ **brakujące fakty / rework** | ile decyzji nie przeszło przez handoff i ile tokenów kosztuje ich odtworzenie (40% tokenów jednostki, która je wytworzyła) lub powtórka pracy w toku |

Dlaczego dwa koszty? Bo **surowe token-tury kłamią w jedną stronę**: nie widzą kosztu zimnego
startu, więc zawsze "opłaca się" ciąć co jednostkę. Sprawdziłem (`python3 -B ctxsplit.py base`):

```
| baza | T (wazony) | okien | koszt wazony | jedno okno bez limitu (wazony) | T (surowe token-tury) | okien |
|---:|---:|---:|---:|---:|---:|---:|
| 5000 | 45000 | 21 | 1197654 | 4570235 | 20000 | 24 |
| 10000 | 60000 | 15 | 1376367 | 4647485 | 20000 | 24 |
| 30000 | 110000 | 8 | 1950975 | 4956485 | 20000 | 24 |
| 60000 | 140000 | 8 | 2676975 | 5419985 | 20000 | 24 |
```

Wg surowych token-tur optymalne `T` = 20 000 (najniższa wartość w skanie): ciąć co jednostkę, zawsze.
Wg kosztu ważonego `T` **rośnie z bazą**: 45 tys. przy bazie 5 tys., 140 tys. przy bazie 60 tys.
Wniosek praktyczny: **im cięższa baza (eager MCP, wielki CLAUDE.md), tym drożej każde nowe okno,
więc tym rzadziej warto ciąć** - to kolejny argument za odchudzaniem bazy z #3 i #14. (Ważone
`T` ma sens tylko jeśli założenia o cache są choć z grubsza prawdziwe - nie sprawdzałem.)

---

## 3️⃣ Osiem strategii, ten sam próg T = 90 000

Strategia = **kiedy ciąć** x **co zabrać**. `python3 -B ctxsplit.py run`:

```
odniesienie (jedno okno bez limitu): 40106334 token-tur, koszt wazony 4647485, max kontekst 553784
| strategia | okien | token-tury | koszt wazony cache | vs bez limitu (wazony) | rework tok | brakujace fakty | wymuszone ciecia | max kontekst | handoffy tok |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| never+recent3 (auto-kompakcja) | 4 | 17033461 | 2553196 | 0.55x | 148986 | 11 | 3 | 199998 | 2985 |
| mid+live | 9 | 8633996 | 1719658 | 0.37x | 85889 | 0 | 0 | 92402 | 11931 |
| boundary+none | 9 | 10620381 | 2106761 | 0.45x | 274671 | 32 | 0 | 133222 | 0 |
| boundary+recent3 | 8 | 10024052 | 1915699 | 0.41x | 155363 | 20 | 0 | 124480 | 7198 |
| boundary+all | 7 | 8847149 | 1635295 | 0.35x | 0 | 0 | 0 | 114864 | 18637 |
| boundary+all_capped | 7 | 9314861 | 1748510 | 0.38x | 74859 | 10 | 0 | 122527 | 10452 |
| boundary+live | 7 | 8684137 | 1595253 | 0.34x | 0 | 0 | 0 | 111580 | 8745 |
| predictive+live | 8 | 7241734 | 1466975 | 0.32x | 0 | 0 | 0 | 90983 | 10604 |
```

Jak czytać, od góry:

- 🪦 **`never+recent3`** modeluje "czekam, aż okno się zapełni, i zostaje streszczenie ostatnich
  rzeczy" (to **mój model** auto-kompakcji, nie opis jej realnego działania). 3 cięcia wymuszone w
  środku jednostki, 11 zgubionych faktów, 149 tys. tok. powtórzonej pracy: **+74% kosztu** względem
  najlepszej strategii. Pracujesz pod ścianą (max kontekst 199 998 z 200 000) i tniesz wtedy, kiedy
  stan jest najbardziej rozgrzebany.
- ✂️ **`mid+live`** tnie w środku jednostki przy `T`: handoff jest dobry (0 zgubionych faktów),
  ale **praca w toku przepada** i jest powtarzana: 85 889 tok. reworku.
- 🕳️ **`boundary+none`** (nowe okno bez niczego): 32 brakujące fakty, 274 671 tok. reworku, **+44%**
  kosztu wobec `predictive+live`. Najbardziej "czysta" higiena okna, najgorszy wynik.
- 🧠 **`boundary+recent3`**: pamięta ostatnie trzy decyzje - gubi 20 faktów, bo 34 z 64 zależności
  sięgają dalej niż 3 jednostki.
- 📚 **`boundary+all`** (handoff dopisywany bez końca) wypada **dobrze: 1 635 295, tylko 2,5%
  drożej niż `live`**. Uczciwie: w modelu decyzje są małe (120-300 tok.), więc 24 z nich to
  tylko ~5 tys. tok. Handoff rośnie jednak monotonicznie (18 637 tok. łącznie vs 8745) i przy
  realnych, dłuższych decyzjach ta przewaga zniknie. `all_capped` (limit 2000 tok.) pokazuje, co
  się dzieje, gdy ucinasz od najstarszych: 10 zgubionych faktów, +9,6% kosztu.
- 🎯 **`live`** zabiera tylko decyzje, których potrzebuje którakolwiek **pozostała** jednostka.
  To wymaga czegoś, co w kodzie nazywa się "plan deklaruje zależności" - **to jest pole w
  PLAN.md, nie magia modelu** (patrz sekcja 5).
- 🔮 **`predictive`** tnie na granicy jednostki, gdy `kontekst + szacunek następnej jednostki > T`;
  szacunek = średnia, nie wyrocznia. Efekt: najniższy koszt (1 466 975) **i** niższy max kontekst
  (90 983 vs 111 580), bo nie dopuszcza do przerośnięcia progu o całą jednostkę.

> 📏 Skala efektów (T=90 000, koszt ważony): `predictive+live` = 1,00; `boundary+live` = 1,09;
> `boundary+recent3` = 1,31; `boundary+none` = 1,44; `never+recent3` = 1,74.

---

## 4️⃣ Pokrętło T: szeroki dołek, stroma ściana po obu stronach

`python3 -B ctxsplit.py sweep` (komórka: okien / token-tury / koszt ważony / rework;
`*` = najlepsze wg kosztu ważonego):

```
| T | mid | boundary | predictive |
|---:|---|---|---|
| 30000 | 62 / 6208685 / 3156832 / 852461 | 20 / 4733299 / 1397238 / 0 | 24 / 4378940 / 1420138 / 0 |
| 50000 | 22 / 6155972 / 1848006 / 241955 | 11 / 6072477 / 1396422 / 0 * | 21 / 4616208 / 1399904 / 0 |
| 70000 | 12 / 7341902 / 1681137 / 125253 * | 8 / 7241734 / 1466975 / 0 | 12 / 5828937 / 1386335 / 0 * |
| 90000 | 9 / 8633996 / 1719658 / 85889 | 7 / 8684137 / 1595253 / 0 | 8 / 7241734 / 1466975 / 0 |
| 110000 | 6 / 9913495 / 1752366 / 41330 | 5 / 10262688 / 1724812 / 0 | 7 / 8684137 / 1595253 / 0 |
| 130000 | 6 / 11286302 / 1937561 / 83752 | 5 / 11452521 / 1841498 / 0 | 5 / 10262688 / 1724812 / 0 |
| 150000 | 5 / 12217955 / 1977532 / 50677 | 4 / 12318898 / 1915165 / 0 | 5 / 10588254 / 1756283 / 0 |
| 170000 | 4 / 13777250 / 2106824 / 40321 | 4 / 14597123 / 2141962 / 0 | 4 / 12318898 / 1915165 / 0 |
| 190000 | 4 / 14785710 / 2200395 / 34095 | 4 / 16031694 / 2318148 / 28666 | 4 / 13454731 / 2028088 / 0 |
```

Trzy obserwacje:

1. 📉 **Dołek jest płaski**: dla `boundary` koszt przy T=30k, 50k i 70k to 1,397 / 1,396 / 1,467 mln -
   różnica 5%. Przy T=190k jest to już 2,318 mln (+66% względem minimum). Nie trzeba trafić w
   optimum, trzeba **nie być po stronie "za duże"**.
2. 💥 **`mid` przy małym T eksploduje**: T=30 000 to 62 okna i 852 tys. tok. reworku, bo jednostka
   (13-32 tys.) sama nie mieści się w progu i każde cięcie w środku każe zaczynać ją od nowa. **Próg
   mniejszy niż typowa jednostka pracy + baza = cięcie w pętli.** Kod nie ma zabezpieczenia
   przed zapętleniem poza tym, że po cięciu przechodzi dalej - w prawdziwej sesji to byłaby
   spirala.
3. 🏁 **`predictive` wygrywa lub remisuje na całej skali**, bo nie czeka, aż jednostka przekroczy
   próg. Rachunek: koszt cięcia (zimny start + handoff) jest znany z góry, a koszt przerośnięcia
   to nadprogramowa jednostka ciągnięta w drogim kontekście.

> 🧪 **Czego tu nie mierzę - jakości.** Długi kontekst może pogarszać jakość odpowiedzi
> (hipoteza "lost in the middle" - **niezweryfikowana**, jak w #13). Ten model ocenia tylko
> koszt, więc **optymalne T wg kosztu jest górną granicą tego, co sensowne**; jeśli jakość
> spada szybciej, tnij wcześniej.

---

## 5️⃣ Plik handoff: co ma zawierać i jak to sprawdzić maszynowo

Plik, który wyrenderował `python3 -B ctxsplit.py handoff --after 12` (to też
[`HANDOFF.example.md`](code/HANDOFF.example.md), treść decyzji jest syntetyczna):

```markdown
# HANDOFF - okno 3 -> 4

## Cel
Migracja 24 modulow na nowy wzorzec obslugi bledow. Plan: PLAN.md (zaleznosci per modul).

## Zrobione
- U00..U11 (12/24), testy zielone na koniec kazdej jednostki.

## Decyzje obowiazujace
- D00 Orders: wynik przeniesiony do wspolnej konwencji; szczegoly w pliku. -> docs/decisions/00-orders.md
- D05 Shipping: wynik przeniesiony do wspolnej konwencji; szczegoly w pliku. -> docs/decisions/05-shipping.md
- D11 Audit: ... -> docs/decisions/11-audit.md        (skrócone; w pliku jest 9 decyzji)

## Nastepny krok
- U12 Notifications: zaleznosci D00, D05, D07, D11; zacznij od odczytu docs/decisions/, nie od przegladu repo.

## Pulapki
- Nie rob refaktoru poza zakresem jednostki; nie ruszaj modulow z PLAN.md oznaczonych jako zamrozone.

## Weryfikacja
- `dotnet test --filter Category=Migrated` musi byc zielone przed zamknieciem jednostki.
```

Dlaczego tak:

| Sekcja | Po co | Co pójdzie źle bez niej |
|---|---|---|
| **Cel** | jedno zdanie + wskaźnik do planu | nowe okno nie wie, co jest "poza zakresem" |
| **Zrobione** | zakres w liczbach, nie opis | model "odkrywa" skończoną pracę i robi ją drugi raz |
| **Decyzje obowiązujące** | tylko żywe (potrzebne pozostałym jednostkom) + **wskaźnik do pliku** | tu leży 34 z 64 zależności; handoff bez nich = `recent3`/`none` z tabeli |
| **Następny krok** | **dokładnie jeden** | dwa kroki = nowe okno wybiera sobie, od którego zacząć |
| **Pułapki** | zakazy i negatywna wiedza | ta wiedza nie jest w repo, nigdzie indziej jej nie ma |
| **Weryfikacja** | polecenie, które rozstrzyga "zrobione" | "wydaje mi się, że gotowe" |

Zasada zapisana w kodzie: **handoff to wskaźniki, nie treść**. Decyzja ma 1 linię i ścieżkę (`->
docs/...`); szczegóły żyją w repo, a nowe okno czyta je na żądanie (ta sama idea co leniwe
ładowanie w #14).

### Linter handoffu

`python3 -B ctxsplit.py lint PLIK [--cap 1500] [--root KATALOG]` sprawdza (heurystyka dobrana pod
ten format): komplet sekcji w kolejności; rozmiar ≤ cap (bajty/4); żadna linia > 240 znaków i
żaden blok kodu > 15 linii (to wygląda na wklejony log); każda decyzja kończy się `-> plik`;
**dokładnie jeden** punkt w "Następny krok"; polecenie w backtickach w "Weryfikacja"; z `--root`
także czy pliki ze wskaźników istnieją.

```
$ python3 -B ctxsplit.py lint HANDOFF.example.md
HANDOFF.example.md: 383 tok. (bajty/4), limit 1500
OK
```

Z `--root` na katalogu `code/` linter zwraca **błąd** (exit 1), bo `docs/decisions/*.md` w
tym przykładzie nie istnieją - to jest oczekiwany wynik, bo przykład jest syntetyczny:

```
BLAD: wskaznik do nieistniejacego pliku: docs/decisions/00-orders.md
... (9 bledow)
```

Testy (36 asercji) obejmują 8 przypadków negatywnych lintu (brak sekcji, zła kolejność, brak
wskaźnika, dwa kroki, za duży, długa linia, długi blok, brak weryfikacji) i sprawdzenie `--root`
na prawdziwych plikach w katalogu tymczasowym.

---

## 6️⃣ Kryteria cięcia - checklista

| # | Reguła | Skąd |
|---|---|---|
| 1 | **Tnij na granicy jednostki pracy, nigdy w środku** (praca w toku przepada) | `mid` vs `boundary`: 85 889 vs 0 tok. reworku |
| 2 | **Tnij zanim następna jednostka się nie zmieści** (`kontekst + szacunek > T`), nie po fakcie | `predictive` -8% kosztu i niższy szczyt |
| 3 | **`T` większe niż jednostka + baza** (inaczej pętla cięć) | `mid` przy T=30k: 62 okna |
| 4 | **Cięższa baza = rzadsze cięcia** | T optymalne 45k → 140k przy bazie 5k → 60k |
| 5 | **Handoff = decyzje potrzebne pozostałej pracy**, nie "ostatnie wydarzenia" | `recent3` +31%, `none` +44% |
| 6 | **Zależności zadeklaruj w planie, zanim zaczniesz** - bez tego nie wiesz, które decyzje są "żywe" | `live` wymaga pola zależności |
| 7 | **Handoff ma rozmiar ograniczony i sprawdzany**, ale ucinanie od najstarszych gubi fundamenty | `all_capped`: 10 zgubionych faktów |
| 8 | **Wskaźniki zamiast treści**, weryfikacja poleceniem | lint |

---

## 🧪 Co zweryfikowano, a co nie

| ✅ Zmierzone (kod, Python 3.10.4, stdlib) | ❓ Niezweryfikowane |
|---|---|
| Model kosztów 24 jednostek w oknie 200 000: 8 strategii, 3 wyzwalacze x 9 progów | Czy i jak dobrze model sam pisze handoff i go czyta |
| Zależności: 64, z czego 34 dalej niż 3 jednostki wstecz (zadane regułą w kodzie) | Realne rozkłady zależności w Twoim repo (tu: syntetyczne) |
| Rozmiary: tury 1500-6000 tok., jednostka 13-32 tys., suma 543 784 | Realna auto-kompakcja Claude Code (`never+recent3` to MÓJ model, nie opis) |
| Optymalne T rośnie z bazą (45k → 140k) przy założeniach cache | Mnożniki cache 0,1x/1,25x i brak TTL (założenia z pamięci) |
| Linter handoffu: 8 reguł negatywnych, `--root` na plikach | Wpływ długiego kontekstu na jakość ("lost in the middle") |
| 36 asercji; w tym 3 scenariusze policzone ręcznie (4000 / 5450 / 5120 token-tur) | Komendy i zachowanie `claude` (nowa sesja, `--resume`, `/clear`) - CLI nie uruchamiałem |

## 🎯 Zapamiętaj

1. **Cięcie to przeprowadzka**: koszt = zimny start + to, co zgubisz. Tnij na granicy jednostki i *przed* przepełnieniem.
2. **Próg T ma szeroki dołek; polityka handoffu ma stromą ścianę.** Zacznij od handoffu.
3. **Handoff to żywe decyzje + wskaźniki + jeden następny krok + polecenie weryfikacji** - i da się go zlintować.
4. **Zależności dalekie są najgroźniejsze**, a streszczenie "ostatnich zdarzeń" gubi je pierwsze.
5. **Cięższa baza = rzadsze cięcia** - wracamy do odchudzania bazy z #3 i #14.

### ➡️ Następne kroki
- Snapshot stanu zamiast dopisywania (`fold`): handoff ograniczony rozmiarem bez gubienia fundamentów.
- Wyszukiwarka z synonimami / embeddingami na zestawie z #14 (nadal otwarte).
- Weryfikacja w dokumentacji i na żywym `claude`: nowa sesja, wznowienie, co przeżywa `/compact`.
- Analiza prawdziwego transkryptu (gdy odczyt będzie dozwolony).
