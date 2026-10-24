# Kod do wydania z 26.09 — kto pożera kontekst sesji (analizator transkryptu)

Pełny artykuł: [`../ARTICLE.md`](../ARTICLE.md). Wymagania: **python3**, brak zależności.

## Fragment artykułu, którego dotyczy ten kod

> Koszt wyniku = ~tokeny wyniku x liczba tur po nim. Koszt sesji = suma po turach z
> rozmiaru kontekstu w tej turze ("token-tury"). **5 wyników z 60 (8%) odpowiada za
> 67,3% całego dźwigania.** Delegacja dużych wyników do subagenta obniżyła w symulacji
> szczyt kontekstu 4,2x, a auto-compact przy 80% okna - do 82 050 tok. kosztem 2
> kompaktowań.
>
> **Dane są syntetyczne** (odczyt `~/.claude/projects/` odrzucony przez uprawnienia, nie
> obchodziłem). Kształt rekordów jest zgodny z opisem z wydania #1, ale nie porównywany
> z żywym klientem.

## Pliki

- [`gen_transcript.py`](gen_transcript.py) — deterministyczny (seed=7) syntetyczny
  transkrypt: 60 tur, narzędzia Read/Grep/Bash/Edit/Task, wyniki z ciężkim ogonem.
- [`analyze_transcript.py`](analyze_transcript.py) — rozkład per narzędzie, ranking
  pożeraczy (rozmiar x liczba tur) i symulacja what-if (delegacja, auto-compact).
  Działa też na własnym pliku `.jsonl`; drukuje tylko agregaty (nazwy narzędzi, liczby),
  nigdy treści rozmowy. Tokeny = bajty/4 (heurystyka, nie tokenizer Claude'a).
- [`test_analyzer.py`](test_analyzer.py) — test na ręcznie policzonym mini-transkrypcie.

## Jak odpalić od zera

```bash
cd code/
python3 gen_transcript.py session.jsonl
python3 analyze_transcript.py session.jsonl --window 100000
python3 test_analyzer.py
```

Na własnej sesji: `python3 analyze_transcript.py sciezka/do/sesji.jsonl` (pola
`--base`, `--window`, `--delegate-over`, `--compact-at`, `--summary-tokens` w nagłówku
skryptu).

## Prawdziwy, uruchomiony output

```
Zapisano 121 rekordów, 602529 bajtów -> /tmp/session_synth.jsonl
```

(w tym przebiegu ścieżka wyjściowa to `/tmp/session_synth.jsonl`; sama analiza:)

```
Zdarzeń: 121, tur asystenta: 60, wyniki narzędzi = 98.5% wszystkich bajtów

1) Rozkład per narzędzie
narzędzie  wywołań    bajtów  ~tokenów  udział  max ~tok
Bash            16    289260     72315   51.4%     13840
Read            14    247584     61896   44.0%     14137
Grep            14     20145      5036    3.6%      1110
Task             6      4486      1121    0.8%       257
Edit            10       903       225    0.2%        41

2) Top 5 pożeraczy: rozmiar wyniku x liczba tur, które go dźwigały
narzędzie   ~tokenów  tur potem   token-tur
Read           14137         58      819946
Bash           13840         51      705840
Read           10025         47      471175
Bash           10867         43      467281
Bash            7228         56      404768
Te 5 wyników = 67.3% całego 'dźwigania' wyników przez kolejne tury.

3) What-if (okno 100000 tok., baza 18000 tok.)
wariant                                      szczyt ~tok    token-tur compactów
bez zmian                                         160718      5405134         0
delegacja wyników > 3000 tok. (raport 150)         38357      1538332         0
auto-compact przy 80% okna (summary 4000)          82050      2506436         2
delegacja + auto-compact                           38357      1538332         0

Szczyt kontekstu wg pól usage w pliku: 148814 tok. (do porównania z wierszem 'bez zmian')
```

```
OK: 6/6 asercji przeszło
```

Różnica 160 718 vs 148 814: pole `usage` jest zapisywane w turze asystenta, przed
ostatnim wynikiem narzędzia, więc szczyt z `usage` nie widzi jeszcze ostatniego wyniku.

## Uczciwe ograniczenia

- Dane syntetyczne, proporcje dobrane przeze mnie (ilustracja mechanizmu, nie pomiar).
- Symulacja zakłada stały rozmiar streszczenia i raportu; nie modeluje jakości ani
  kosztu tokenów samego subagenta.
- Nie sprawdzono na żywym transkrypcie Claude Code ani w żywej sesji (`/compact`).
- `__pycache__/` po teście: usunięcie było odrzucone przez uprawnienia, więc jest
  w `.gitignore`.
