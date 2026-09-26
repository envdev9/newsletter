# Kod do wydania #3 — lint promptów do debugowania i code review

Pełny artykuł: [`../ARTICLE.md`](../ARTICLE.md).

## Fragment prasówki, którego dotyczy ten kod

> `prompt_lint.py` (czysty Python, stdlib) sprawdza prompt regułami: plik, linia, dowód
> błędu, warunki odtworzenia, prośba o hipotezy, kryterium sukcesu, format, zakres (dla
> review: kryteria przeglądu i skala ważności). **To heurystyka regexowa** - sprawdza, czy
> w prompcie są słowa-klucze, nie czy są sensowne; nie dowodzi jakości odpowiedzi żadnego
> modelu (w tym wydaniu nie uruchamiano modelu).

## Struktura

```
code/
├── prompt_lint.py     # lint (stdlib, bez pip)
├── prompts/           # 9 promptów: *_bad.txt / *_good.txt (debug_, review_, iter_)
└── negative/          # test negatywny: "dobry" prompt z wyciętymi elementami
```

Rodzaj reguł wynika z prefiksu (`review_*` = review, reszta = debug), oczekiwanie z sufiksu.

## Jak uruchomić

Wymaganie: Python 3 (użyto 3.10.4). Bez `pip install`. Z katalogu głównego repo
(`-B` = bez tworzenia `__pycache__`):

```bash
python3 -B days/2026-09-26/ai-prompts/code/prompt_lint.py
python3 -B days/2026-09-26/ai-prompts/code/prompt_lint.py days/2026-09-26/ai-prompts/code/negative/debug_mutant_good.txt
python3 -B days/2026-09-26/ai-prompts/code/prompt_lint.py --strict twoj_prompt_debug.txt
```

Własny prompt: nazwij plik `debug_<cos>.txt` lub `review_<cos>.txt`; z `--strict` exit 1,
gdy czegoś brakuje.

## Weryfikacja — rzeczywisty output (uruchomione 2026-09-26)

### Samotest na `prompts/` (exit 0; komunikaty „brak:" dla 0/9 skrócone znakiem […])

```
debug_dotnet_bad.txt       [debug ] 0/9  FAIL
    brak: min. 15 słów                                  -> Zbyt krótko - model musi zgadywać kontekst.
    brak: wskazany plik                                 -> Podaj plik (np. `src/Foo.cs`), inaczej model zacznie od szukania.
    […pozostałe 7 brakujących reguł, wszystkie oblane…]
debug_dotnet_good.txt      [debug ] 9/9  PASS
debug_sql_bad.txt          [debug ] 0/9  FAIL
    […9 komunikatów…]
debug_sql_good.txt         [debug ] 9/9  PASS
iter_1_bad.txt             [debug ] 0/9  FAIL
    […9 komunikatów…]
iter_2_bad.txt             [debug ] 4/9  FAIL
    brak: warunki odtworzenia (kiedy występuje)         -> Napisz kiedy występuje: zawsze/sporadycznie, od jakiej zmiany, jakie dane.
    brak: prośba o hipotezy przed poprawką              -> Poproś o ranking hipotez i sposób ich sprawdzenia ZANIM model zmieni kod.
    brak: kryterium sukcesu                             -> Napisz po czym poznać, że gotowe (np. test przechodzi, oczekiwany wynik).
    brak: format odpowiedzi                             -> Narzuć format (tabela/lista/diff/limit długości).
    brak: zakres i granice (czego nie ruszać)           -> Napisz wprost czego model NIE ma robić.
iter_3_good.txt            [debug ] 9/9  PASS
review_angular_bad.txt     [review] 0/6  FAIL
    […6 komunikatów…]
review_angular_good.txt    [review] 6/6  PASS

SAMOTEST: 9/9 wyników zgodnych z sufiksem _bad/_good.
```

(Pełny wydruk zawierał wszystkie komunikaty; tu skrócono tylko powtarzalne linie „brak:".)

### Test negatywny (exit 1)

`negative/debug_mutant_good.txt` to „dobry" prompt bez stack trace i bez prośby o hipotezy:

```
debug_mutant_good.txt      [debug ] 7/9  FAIL  <-- NIEZGODNE Z OCZEKIWANIEM (good)
    brak: dowód błędu (wyjątek/kod błędu/stack trace)   -> Wklej treść błędu/stack trace w bloku kodu, nie opisuj go własnymi słowami.
    brak: prośba o hipotezy przed poprawką              -> Poproś o ranking hipotez i sposób ich sprawdzenia ZANIM model zmieni kod.

SAMOTEST: 0/1 wyników zgodnych z sufiksem _bad/_good.
```

### Tryb `--strict` na `iter_2_bad.txt` (exit 1)

```
iter_2_bad.txt             [debug ] 4/9  FAIL
    […5 komunikatów „brak:", jak wyżej…]

STRICT: 1 z 1 promptów oblanych.
```

## Co NIE jest zweryfikowane

- Że prompty „dobre" wg lintu dają lepsze odpowiedzi modelu - żaden model nie był uruchamiany.
- Że reguły działają na cudzych promptach: dobrane pod własne przykłady, regexy są po
  polsku i łatwo je oszukać (słowo „format" w dowolnym miejscu zalicza regułę FORMAT).
- Nazwy klas/plików/tabel w promptach (`OrderService`, `dbo.Orders`) są ilustracyjne,
  a liczby (12 s, 412009 wierszy) wymyślone na potrzeby przykładu.
