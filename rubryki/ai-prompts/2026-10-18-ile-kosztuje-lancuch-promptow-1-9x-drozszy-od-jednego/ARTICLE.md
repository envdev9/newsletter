<div align="center">

# 📰 TECH PRASÓWKA
### Wydanie #25 — 18 października 2026

![AI](https://img.shields.io/badge/AI_%2F_Prompty-D97757?style=for-the-badge&logo=anthropic&logoColor=white)
![.NET](https://img.shields.io/badge/.NET_10-512BD4?style=for-the-badge&logo=dotnet&logoColor=white)
![Koszt](https://img.shields.io/badge/model_kosztu-tokeny-F2C94C?style=for-the-badge)

## Ile kosztuje łańcuch promptów: 1,9x droższy od jednego promptu na małym kodzie, 0,6x na dużym - i dlaczego to drugie jest liczbą z modelu, nie z pomiaru

</div>

---

> _"Kontrakt między krokami kosztuje tokeny. Pytanie nie brzmi „czy", tylko „ile, gdzie i kiedy się zwraca"."_

Poprzednio w tej rubryce: [#25 - walidator na Roslynie](../2026-10-17-walidator-odpowiedzi-modelu-na-roslynie-10-falszywych/ARTICLE.md), a wcześniej
[łańcuch z kontraktami (#18)](../2026-10-11-jeden-wielki-prompt-vs-lancuch-trzech-kontrakt-miedzy/ARTICLE.md). W obu zostawiłem ten sam przypis:
*„koszt tokenów łańcucha vs jeden prompt - niemierzony"*. Dziś go zdejmuję. Nie omawiam ponownie kontraktów
C01-C17 ani Roslyna; biorę **ten sam łańcuch i te same 7 nagrań** i liczę, **ile tekstu naprawdę przechodzi
przez każdy krok**.

**🎯 Dlaczego to ważne:** „rozbij zadanie na kroki" brzmi jak darmowa dobra rada. Nie jest darmowa: każdy krok to
osobne wywołanie z własnym szablonem, a pliki źródłowe jadą **do kilku kroków naraz**. Zanim zbudujesz łańcuch w
produkcji, warto wiedzieć, ile płacisz za kontrakty, ile oszczędza ich fail-fast i od jakiego rozmiaru kodu
rachunek się odwraca.

> ⚠️ **Uczciwie na starcie: żaden model nie był uruchamiany i żaden tokenizer też nie.** Mierzę *długość w
> znakach* promptów, które skrypt naprawdę zbudował, i nagrań pisanych ręcznie. Tokeny = `ceil(znaki / k)` dla
> k = 3, 4, 5 - **szacunek, nie tokenizer żadnego modelu** (tekst po polsku bez ogonków, kod C# i JSON
> tokenizują się różnie). Ceny, współczynniki sukcesu i rozmiar „dużego kodu" to **parametry**, nie dane.

---

### 1️⃣ Gdzie idą tokeny: anatomia trzech wywołań

[`code/cost.py`](code/cost.py) opakowuje `ReplayModel` z #18 w rejestrator i zapisuje każdy prompt i każdą
odpowiedź. Ścieżka szczęśliwa (`s0_good`), prawdziwy output (k = 4):

```
krok      znaki we  znaki wy   tok we   tok wy
1             1034       241      259       61
2             1341       252      336       63
3             1309       407      328      102
razem         3684       900      923      226

krok      razem  szablon  zgloszenie  indeks  poprz.JSON  zrodla
krok 1     1034      580         234     220           0       0
krok 2     1341      606           0       0         265     470
krok 3     1309      558           0       0         281     470
```

Dwa spostrzeżenia, których nie widać z samego schematu „triaż → plan → patch":

- **Szablon to połowa wejścia.** 580 + 606 + 558 znaków z 3684 (**47%**) to instrukcje ról i reguł, płacone
  przy każdym wywołaniu. Kontrakty nie dokładają tokenów do promptów (reguły C01-C17 siedzą w skrypcie, nie w
  tekście) - ale *format wyjścia i „ZASADY"* tak.
- **Źródła jadą dwa razy.** `Billing/Money.cs` (470 znaków) trafia do kroku 2 **i** do kroku 3, bajt w bajt
  (`zrodla ... identyczne: True`). Przy 940 z 3684 znaków wejścia (26%) to jeszcze drobiazg; przy prawdziwych
  plikach to główny składnik rachunku.

---

### 2️⃣ Łańcuch kontra jeden prompt (ten sam materiał, ten sam diff)

Punkt odniesienia: jeden prompt z [`mega_bad.txt`](code/prompts/mega_bad.txt) + zgłoszeniem + **wszystkimi
trzema** plikami `Billing` (model bez triażu musi dostać wszystko) i odpowiedzią równą diffowi z kroku 3.
To **dolna granica** kosztu jednego promptu - prawdziwa odpowiedź zwykle dorzuca prozę.

```
wejscie 2015 znakow (504 tok), wyjscie 407 znakow (102 tok)
  k   w   lancuch    jeden  stosunek
  3   1      1530      808     1.89x
  4   1      1149      606     1.90x
  4   3      1601      810     1.98x
  4   5      2053     1014     2.02x
  5   5      1648      813     2.03x
```

(`w` = ile razy token wyjściowy kosztuje więcej niż wejściowy - **założenie**; pełna tabela w
[`code/README.md`](code/README.md).) Wynik jest stabilny: **~1,9-2,0x** niezależnie od k i w. Łańcuch ma 3
wywołania zamiast jednego, a na tak małym kodzie każdy szablon waży tyle, co cały kod.

---

### 3️⃣ Fail-fast: kiedy kontrakt się zwraca

Tokeny wydane na każdy scenariusz z #18 (k = 4, w = 1). „Doszedł do bramki" = nie odrzucony przez żadną regułę:

```
scenariusz        kontrakty            tok  baseline             tok  +naprawa(1 runda, kontrakty)
s0_good           doszedl do bramki   1149  doszedl do bramki   1149  -
s1_fenced_json    odrzucony: krok 1    343  doszedl do bramki   1172  +519
s2_halluc_symbol  odrzucony: krok 1    309  doszedl do bramki   1307  +448
s3_scope_creep    odrzucony: krok 2    737  doszedl do bramki   1316  +589
s4_test_tamper    odrzucony: krok 3   1284  doszedl do bramki   1284  +917
s5_bad_context    odrzucony: krok 3   1132  doszedl do bramki   1132  +609
s6_wrong_fix      doszedl do bramki   1126  doszedl do bramki   1126  -
suma na 6 zlych/podejrzanych scenariuszach: kontrakty 4931 tok, baseline 7337 tok
```

| Co widać | Dlaczego |
|---|---|
| **-33% łącznie (4931 vs 7337)**, ale cała oszczędność pochodzi z 3 scenariuszy | s1, s2, s3 odpadają w kroku 1-2; baseline wydaje pełne 3 wywołania i dopiero bramka (lub nikt) je łapie |
| **s4 i s5: zero oszczędności** | zły diff widać dopiero w kroku 3 - wszystko już wydane. Kontrakt tu nie oszczędza tokenów, tylko **chroni przed przyjęciem** (s4: baseline zaakceptował zmianę testów) |
| **s6: baseline = kontrakty** | zła poprawka w dobrym formacie przechodzi wszystko; łapie ją dopiero `Billing.Check` (nie kosztuje tokenów) |
| **Runda naprawcza: +448...+917 tok** | liczę prompt naprawczy **plus** oryginalny prompt kroku (API jest bezstanowe) i odpowiedź długości poprzedniej - założenie |

Wniosek, który zmienia projekt: **kolejność kroków powinna stawiać najtańsze i najczęściej odrzucane
walidacje najwcześniej**. W tym łańcuchu kontrakty najdroższych błędów (s4, s5) działają dopiero na końcu - więc
tam „oszczędność" nie istnieje, jest tylko bezpieczeństwo.

---

### 4️⃣ Kiedy łańcuch wygrywa na koszcie: dwa regulatory

**Regulator 1 - szansa sukcesu.** Przy naprawie lokalnej kroku oczekiwany koszt na zaakceptowany wynik to
`C_łańcuch / q` (q = szansa, że krok przejdzie kontrakt), dla jednego promptu `C_jeden / Q`. Łańcuch jest tańszy,
gdy `Q < q · C_jeden / C_łańcuch`. Progi (k = 4):

```
  w  stosunek    q=0.95     q=0.9     q=0.8     q=0.7
  1     1.90x      0.50      0.47      0.42      0.37
  3     1.98x      0.48      0.46      0.40      0.35
  5     2.02x      0.47      0.44      0.40      0.35
```

Czytaj: przy q = 0,9 jeden prompt musi trafiać **mniej niż w ~47% przypadków**, żeby łańcuch był tańszy na
zaakceptowany wynik. Jeśli jeden prompt trafia częściej, łańcuch jest droższy - i za to płacisz w zamian za
wykrywanie zmyśleń i naruszeń zakresu, których jeden prompt sam z siebie nie zgłosi. **q i Q nie są zmierzone**
(nie ma modelu); tabela mówi, *jakie wartości musiałbyś zmierzyć*.

**Regulator 2 - rozmiar kodu.** Zmierzony udział plików podejrzanych: f = 0,29 (470 z 1600 znaków). Model:
łańcuch ≈ stałe + 2·f·S (źródła w krokach 2 i 3), jeden prompt ≈ stałe + S:

```
  S [znaki]  lancuch tok  jeden tok  stosunek
       1600         1146        606     1.89x
       5000         1646       1456     1.13x
      20000         3849       5206     0.74x
     100000        15599      25206     0.62x
    1000000       147786     250206     0.59x
   granica dla S -> nieskonczonosc: 2f = 0.59x
```

Czyli triaż, który zawęża kod do podejrzanych plików, zaczyna się opłacać gdzieś między 5 a 20 tysiącami znaków kodu (w tym modelu; punkt przecięcia ok. 7-8 tys.).
Ale to **ekstrapolacja z 3 plików**, więc traktuj ją jako kształt krzywej, nie jako liczbę: f na prawdziwym
repo może być 0,01 albo 0,5; indeks symboli rośnie z repo (nie modelowałem - psuje przewagę łańcucha); a agent z
narzędziami i tak nie wkleja „całego repo" do jednego promptu.

---

### 5️⃣ Czego to nie dowodzi

> - **Żaden model ani tokenizer.** Znaki / k to heurystyka; k = 3-5 daje ten sam stosunek ~1,9-2,0x, ale
>   bezwzględne liczby tokenów mogą być inne.
> - **Nagrania `fixtures/` są pisane ręcznie** - ich długość to moje odpowiedzi, nie odpowiedzi modelu.
>   Prawdziwy model gada więcej (proza, uzasadnienia, „thinking"), co podbija koszt obu stron, ale
>   prawdopodobnie nierówno.
> - **Brak cache'owania promptów.** Szablony i źródła powtarzane między wywołaniami mogą być tańsze, jeśli
>   dostawca daje rabat za powtarzający się prefiks - nie modelowałem (kolejność w promptach z #18 nie jest pod to
>   układana).
> - **Brak czasu i kosztu pieniężnego.** Opóźnienie 3 wywołań sekwencyjnych vs 1 nie jest mierzone; ceny `w`
>   to założenie.
> - Runda naprawcza liczona jednorazowo i z odpowiedzią o długości poprzedniej; nie sprawdzałem, czy prompt
>   naprawczy w ogóle działa na modelu (od #18 nadal tylko budowany).
> - 7 scenariuszy to garść, napisana razem z regułami (wynik #18 jest zawyżony z tego samego powodu).

---

## Wspólny mianownik

Łańcuch nie jest tańszy - jest **bardziej przewidywalny**: płacisz ~2x na małym zadaniu, wygrywasz dopiero gdy
triaż odcina większość kodu albo gdy jeden prompt trafia za rzadko. Kontrakty oszczędzają tokeny tylko tam, gdzie
błąd widać wcześnie (3 z 6 złych scenariuszy); w pozostałych dają bezpieczeństwo, nie rabat. Zanim
rozbijesz zadanie na kroki, policz: ile wejścia to szablon, ile to źródła wysyłane wielokrotnie i na którym
kroku odpadają najczęstsze błędy.

---

## 📎 Jak zweryfikować

Zobacz [`code/README.md`](code/README.md) - komendy i prawdziwy output.

---

<div align="center">

[← wszystkie artykuły: ✍️ AI — prompty dla developera](../README.md) · [spis rubryk](../../../README.md)

</div>
