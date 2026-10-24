# Kod do wydania #29 — układ promptów łańcucha pod cache prefiksu

Pełny artykuł: [`../ARTICLE.md`](../ARTICLE.md).

## Fragment prasówki, którego dotyczy ten kod

> Łańcuch triaż → plan → patch z #18/#25, trzy układy promptów (A = jak w #18, B = cały moduł w prefiksie,
> C = reguły + źródła podejrzanych z triażu, zmienne na końcu). Wspólny prefiks kroków 2 i 3: A 6 znaków, B 2275,
> C 940. Model cache'a (r = 0,1, g = 1,25, m = 1024 tok. — **założenia, nie cennik**): na małym kodzie cache nie robi
> nic (prefiks < m); C zaczyna wygrywać z A między skalą x5 a x8 (0,81x) i zbiega do ~0,68x; B nigdy (2,1-2,4x,
> bo wkłada do prefiksu cały kod). Prefiks psują: nagłówek `Krok n:` na górze (940 → 5), JSON przed źródłami
> (940 → 372), źródła kroku 3 z planu zamiast z triażu, naprawa przed promptem zamiast po nim (prefiks 0).
> **Żaden model, tokenizer ani API nie były uruchamiane; r, g, m i TTL to parametry.**

## Struktura

```
code/
├── prefix.py            # układy A/B/C, pomiar wspólnego prefiksu, model kosztu, mutanty (sekcje 1-6)
├── test_prefix.py       # niezmienniki + test negatywny (3 zepsute układy muszą zostać wykryte)
├── prompts/             # szablony: a1-a3 (układ #18), rules/src_all/src_suspects/s1-s3 (B, C), repair
├── recordings/          # 3 odpowiedzi PISANE RĘCZNIE (nie output modelu), jak s0_good z #18
├── Billing/             # 3 pliki .cs z #18 — używane wyłącznie jako TEKST do promptów (nie są kompilowane)
└── bug_report.txt       # zgłoszenie z #18
```

## Jak uruchomić od zera

Wymagania: Python 3 (stdlib; testowane na 3.10.4). Nie jest potrzebny .NET, `git`, sieć ani klucz API.
Komendy z katalogu głównego repo; `-B` = bez `__pycache__`.

```bash
# 1. pomiar + model kosztu (deterministyczny, <1 s)
python3 -B days/2026-10-24/ai-prompts/code/prefix.py

# 2. niezmienniki i test negatywny
python3 -B days/2026-10-24/ai-prompts/code/test_prefix.py
```

## Weryfikacja — rzeczywisty output (uruchomione 2026-10-24, Python 3.10.4)

### `prefix.py` (exit 0)

```
== 1. wspolny prefiks kolejnych wywolan (znaki, bajt w bajt), skala kodu x1
uklad                       dl.1  dl.2  dl.3  lcp(1,2)  lcp(2,3)  lcp(1,3)
A  (#18, szablon od zera)   1034  1341  1309         6         6         6
B  (caly modul w prefiksie)  2893  2929  2846      2275      2275      2275
C  (reguly + zrodla triazu)  1190  1594  1511       366       940       366
   A: kroki 2 i 3 rozjezdzaja sie na znaku 6: 'planista zmiany. Nie piszesz' vs 'wykonawca. Realizujesz DOKLA'
   C: kroki 2 i 3 rozjezdzaja sie na znaku 940 (z 1594): 'planista zmiany. Nie piszesz' vs 'wykonawca. Realizujesz DOKLA'

== 2. koszt lancucha na tym (malym) kodzie: r=0.1, g=1.25 (ZALOZENIA), jednostka = 1 token wejsciowy
uklad                           bez cache  cache m=0  cache m=1024
A                                    1146       1144          1146
B                                    2392       1510          2392
C                                    1299       1064          1299
   m=0: gdyby cache dzialal dla dowolnie krotkiego prefiksu; m=1024: prefiksy ponizej 1024 tok. nie sa keszowane

== 3. rosnacy kod (balast = powielone zrodla), r=0.1, g=1.25, m=1024; koszt wzgledem A bez cache
 skala zrodla all        A  B bez c.  B cache  C bez c.  C cache    B/A    C/A
     1       1600     1146      2392     2392      1299     1299  2.09x  1.13x
     5       8124     2108      7285     3875      2261     2261  1.84x  1.07x
     8      13017     2830     10955     5649      2982     2282  2.00x  0.81x
    10      16279     3310     13401     6832      3463     2607  2.06x  0.79x
    12      19547     3792     15852     8016      3945     2932  2.11x  0.77x
    20      32619     5720     25656    12755      5873     4234  2.23x  0.74x
   100     163339    25000    123696    60141     25153    17248  2.41x  0.69x
   400     654439    97450    492021   238165     97603    66152  2.44x  0.68x

== 4. wrazliwosc na r i g (skala x20, m=1024); komorka = koszt wzgledem A bez cache (B/A | C/A)
     r           g=1.0          g=1.25           g=2.0
   0.1   1.87|0.63       2.23|0.74       3.32|1.07    
  0.25   2.30|0.70       2.67|0.81       3.76|1.14    
   0.5   3.03|0.81       3.39|0.92       4.48|1.25    
   1.0   4.48|1.03       4.85|1.14       5.94|1.47    

== 5. co psuje prefiks (uklad C, skala x1): lcp(2,3) w znakach
   baza (C)                                                 940
   naglowek 'Krok n:' na poczatku kazdego promptu             5
   JSON z poprzedniego kroku PRZED zrodlami                 372
   zrodla kroku 3 z PLANU (1 plik), zrodla kroku 2 z triazu (2 pliki)   474
   kontrola: te same 2 pliki z triazu w obu krokach        1802

== 6. runda naprawcza kroku 2: prompt kroku = 1594 znakow, tekst naprawczy = 564 znakow
   [prompt kroku][naprawa]: wspolny prefiks z oryginalnym promptem = 1594 z 1594
   [naprawa][prompt kroku]: wspolny prefiks z oryginalnym promptem = 0 z 1594
```

### `test_prefix.py` (exit 0)

```
  negatywny 'naglowek Krok n na poczatku': wykryty (2 naruszen)
  negatywny 'JSON przed zrodlami': wykryty (1 naruszen)
  negatywny 'uklad A': wykryty (1 naruszen)
OK: niezmienniki spelnione, 3/3 zepsute uklady wykryte
```

## Co NIE jest zweryfikowane

- **Żaden model, tokenizer ani API.** Tokeny = znaki / 4; mierzone jest tylko to, co deterministyczne (bajty wspólnego prefiksu).
- **`r`, `g`, `m` to założenia**, nie dane z cennika/dokumentacji. Nie sprawdzałem: minimalnej długości cache'owanego
  prefiksu dla żadnego modelu, TTL, tego jak dostawca wybiera punkt zapisu (model zakłada idealny, na granicy wspólnego
  prefiksu), ani zachowania przy wywołaniach równoległych.
- Szablony C nie są identyczne z A (wspólne reguły dopisane, ZASADY krótsze): różnica kosztu miesza kolejność z
  innym tekstem; wpływu na jakość odpowiedzi nie da się ocenić bez modelu.
- Balast (powielone źródła) i f = 0,29 z 3 plików to ekstrapolacja kształtu krzywej, nie pomiar na dużym repo.
- Latencja nie jest mierzona. Nagrania w `recordings/` są pisane ręcznie; runda naprawcza tylko zbudowana jako tekst.
- Pliki `Billing/*.cs` nie były tu kompilowane (służą jako tekst); ich działanie sprawdzano w #18.
