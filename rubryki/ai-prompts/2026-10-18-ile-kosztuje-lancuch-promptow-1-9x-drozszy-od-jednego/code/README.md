# Kod do wydania #25 — koszt tokenowy łańcucha promptów

Pełny artykuł: [`../ARTICLE.md`](../ARTICLE.md).

## Fragment prasówki, którego dotyczy ten kod

> Łańcuch z kontraktami z #18 (triaż → plan → patch) na tych samych 7 nagraniach, ale z rejestratorem długości
> promptów. Ścieżka szczęśliwa: 3 wywołania, ~923 tok. wejścia + ~226 wyjścia (szacunek znaki/4) vs jeden prompt
> z tym samym materiałem ~504 + ~102: łańcuch ~1,9-2,0x droższy niezależnie od k (3-5) i wagi tokenu wyjściowego (1-5).
> Szablony to 47% wejścia, źródła jadą dwa razy (krok 2 i 3). Fail-fast: na 6 scenariuszach 4931 vs 7337 tok. (-33%),
> ale całość z 3 scenariuszy odrzuconych w kroku 1-2; s4/s5 odpadają w kroku 3 bez oszczędności. Model: łańcuch
> tańszy, gdy Q < q·C_jeden/C_łańcuch; przy rosnącym kodzie stosunek spada z 1,9x do granicy 2f = 0,59x (ekstrapolacja
> z f = 0,29, nie pomiar). **Żaden model ani tokenizer nie był uruchamiany; nagrania pisane ręcznie; q, Q, w to parametry.**

## Struktura

```
code/
├── chain.py            # KOPIA chain.py z #18 (2026-10-11), logika bez zmian (zmieniony tylko docstring)
├── bug_report.txt      # zgłoszenie z #18
├── prompts/            # szablony kroków 1-3, repair.txt, mega_bad.txt (jak w #18)
├── fixtures/           # 7 nagrań PISANYCH RĘCZNIE (nie output modelu), jak w #18
├── Billing/            # biblioteka z #18 (banker's rounding w Money.Round)
├── Billing.Check/      # kryterium akceptacji z #18
├── cost.py             # NOWE: rejestrator + model kosztu (sekcje 1-6)
└── test_cost.py        # NOWE: niezmienniki (7 scenariuszy, kontrakty <= baseline, repair_cost)
```

## Jak uruchomić od zera

Wymagania: Python 3 stdlib (3.10.4), `git` (tylko `git apply` w walidacji kroku 3), .NET SDK 10.0.400 (tylko do
kontroli kopii `chain.py run`; `cost.py` dotnet **nie** używa — bramka końcowa jest tam stubem). Komendy z katalogu
głównego repo; `-B` = bez `__pycache__`.

```bash
# 1. model kosztu (sekcje 1-6), deterministyczny, ~0,5 s
python3 -B rubryki/ai-prompts/2026-10-18-ile-kosztuje-lancuch-promptow-1-9x-drozszy-od-jednego/code/cost.py

# 2. niezmienniki
python3 -B rubryki/ai-prompts/2026-10-18-ile-kosztuje-lancuch-promptow-1-9x-drozszy-od-jednego/code/test_cost.py

# 3. kontrola, że kopia łańcucha zachowuje się jak w #18 (7 scenariuszy; używa dotnet w bramce)
python3 -B rubryki/ai-prompts/2026-10-18-ile-kosztuje-lancuch-promptow-1-9x-drozszy-od-jednego/code/chain.py run s0_good
python3 -B rubryki/ai-prompts/2026-10-18-ile-kosztuje-lancuch-promptow-1-9x-drozszy-od-jednego/code/chain.py run s4_test_tamper
python3 -B rubryki/ai-prompts/2026-10-18-ile-kosztuje-lancuch-promptow-1-9x-drozszy-od-jednego/code/chain.py run s4_test_tamper --no-contracts
```

## Weryfikacja — rzeczywisty output (uruchomione 2026-10-18, .NET 10.0.400, Python 3.10.4)

### `cost.py` (exit 0)

```
== 1. sciezka szczesliwa (s0_good), k=4 znaki/token, w=1 (tokeny wyjsciowe liczone jak wejsciowe)
krok      znaki we  znaki wy   tok we   tok wy
1             1034       241      259       61
2             1341       252      336       63
3             1309       407      328      102
razem         3684       900      923      226

== 2. z czego sklada sie wejscie (znaki)
krok      razem  szablon  zgloszenie  indeks  poprz.JSON  zrodla
krok 1     1034      580         234     220           0       0
krok 2     1341      606           0       0         265     470
krok 3     1309      558           0       0         281     470
zrodla w krokach 2 i 3 sa identyczne: True; zrodla = 940/3684 znakow wejscia (26%), z czego powtorzone w kroku 3: 470 znakow

== 3. jeden prompt (mega_bad + zgloszenie + 3 pliki Billing) -> ten sam diff
wejscie 2015 znakow (504 tok), wyjscie 407 znakow (102 tok)
  (dolna granica: realna odpowiedz modelu zwykle zawiera tez prose/uzasadnienie - nie liczone)
  k   w   lancuch    jeden  stosunek
  3   1      1530      808     1.89x
  3   3      2132     1080     1.97x
  3   5      2734     1352     2.02x
  4   1      1149      606     1.90x
  4   3      1601      810     1.98x
  4   5      2053     1014     2.02x
  5   1       920      485     1.90x
  5   3      1284      649     1.98x
  5   5      1648      813     2.03x

== 4. tokeny wydane na kazdy scenariusz (k=4, w=1): kontrakty vs baseline (bez kontraktow)
scenariusz        kontrakty            tok  baseline             tok  +naprawa(1 runda, kontrakty)
s0_good           doszedl do bramki   1149  doszedl do bramki   1149  -
s1_fenced_json    odrzucony: krok 1    343  doszedl do bramki   1172  +519
s2_halluc_symbol  odrzucony: krok 1    309  doszedl do bramki   1307  +448
s3_scope_creep    odrzucony: krok 2    737  doszedl do bramki   1316  +589
s4_test_tamper    odrzucony: krok 3   1284  doszedl do bramki   1284  +917
s5_bad_context    odrzucony: krok 3   1132  doszedl do bramki   1132  +609
s6_wrong_fix      doszedl do bramki   1126  doszedl do bramki   1126  -
suma na 6 zlych/podejrzanych scenariuszach: kontrakty 4931 tok, baseline 7337 tok

== 5. kiedy lancuch jest tanszy od jednego promptu (oczekiwany koszt na zaakceptowany wynik)
   lancuch z naprawa lokalna kroku: koszt ~ C_lancuch / q  (q = szansa, ze krok przechodzi kontrakt)
   jeden prompt:                    koszt ~ C_jeden / Q    (Q = szansa, ze jedna odpowiedz jest dobra)
   lancuch tanszy <=> Q < q * C_jeden / C_lancuch.  q i Q to PARAMETRY, nie pomiar.
  w  stosunek    q=0.95     q=0.9     q=0.8     q=0.7
  1     1.90x      0.50      0.47      0.42      0.37
  3     1.98x      0.48      0.46      0.40      0.35
  5     2.02x      0.47      0.44      0.40      0.35
   (komorka = prog Q: jesli jeden prompt trafia czesciej niz prog, jest tanszy niz lancuch)

== 6. ekstrapolacja: co jesli kod jest wiekszy (w=1, k=4). Zmierzony udzial plikow podejrzanych f = 0.29
   model: lancuch = stale + 2 * f * S   (zrodla podejrzanych w kroku 2 i 3),  jeden = stale + S   (cale S)
   NIE modelowane: indeks symboli rosnie z repo (psuje przewage lancucha), a agent z narzedziami nie czyta calego repo.
  S [znaki]  lancuch tok  jeden tok  stosunek
       1600         1146        606     1.89x
       5000         1646       1456     1.13x
      20000         3849       5206     0.74x
     100000        15599      25206     0.62x
    1000000       147786     250206     0.59x
   granica dla S -> nieskonczonosc: 2f = 0.59x
```

### `test_cost.py` (exit 0)

```
OK: 7 scenariuszy, niezmienniki spelnione
```

### Kontrola kopii `chain.py` (zgodnie z #18)

```
chain.py run s0_good                       -> accepted=True stage=- calls=3 detail=WSZYSTKO OK
chain.py run s1_fenced_json                -> stage=krok 1 [C01 ...]
chain.py run s2_halluc_symbol              -> stage=krok 1 [C06 symbol `InvoiceCalculator.RoundTotal` nie istnieje w indeksie]
chain.py run s3_scope_creep                -> stage=krok 2 [C11 plik Billing/Discounts.cs poza zakresem triazu]
chain.py run s4_test_tamper                -> stage=krok 3 [C14 diff zmienia Billing.Check/Program.cs ...]
chain.py run s5_bad_context                -> stage=krok 3 [C16 git apply --check: error: patch failed: Billing/Money.cs:5]
chain.py run s6_wrong_fix                  -> stage=bramka detail=BLEDY: 1
--no-contracts: s1 OK (3 wywolania), s2 C16 w bramce, s3 OK, s4 OK, s5 C16 w bramce
```

(skrócony zapis; wszystkie 12 uruchomień dało etapy i werdykty zgodne z #18.)

## Co NIE jest zweryfikowane

- **Żaden model ani tokenizer.** Tokeny = `ceil(znaki/k)`, k ∈ {3,4,5}; to szacunek, a nie liczba z API żadnego dostawcy.
- Nagrania `fixtures/` i ich długości są pisane ręcznie; prawdziwy model odpowiada dłużej (proza, rozumowanie).
  Baseline „jeden prompt" to dolna granica kosztu.
- Waga tokenu wyjściowego `w`, szanse sukcesu `q` i `Q`, długość odpowiedzi naprawczej (= poprzedniej) i jedna runda
  naprawcza to **założenia/parametry**, nie pomiary. Prompt naprawczy nie został uruchomiony na modelu.
- Ekstrapolacja z sekcji 6 opiera się na jednym zmierzonym f = 0,29 z 3 plików; indeks symboli rosnący z repo i
  cache'owanie promptów nie są modelowane; czas/opóźnienie nie są mierzone.
- `cost.py` używa stubowej bramki końcowej (koszt tokenowy od niej nie zależy); bramkę z `dotnet run` sprawdzono tylko
  przez `chain.py run`. Fixtures przepisane ręcznie z #18 — zgodność etapów potwierdzona, bajtowa tożsamość nie.
- Test negatywny `test_cost.py` (celowe zepsucie niezmiennika) nie był wykonany.
- Stryker.NET, ślepy zestaw, ewaluacja na prawdziwym modelu — dalej niewykonane.
