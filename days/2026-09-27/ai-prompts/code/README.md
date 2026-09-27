# Kod do wydania #4 — prompty do refaktoryzacji, migracji, few-shot i CLAUDE.md

Pełny artykuł: [`../ARTICLE.md`](../ARTICLE.md).

## Fragment prasówki, którego dotyczy ten kod

> Przy zmianach hurtowych (refaktoryzacja, migracja) prompt ma kazać **najpierw zbudować
> sposób sprawdzenia** — testy charakteryzujące, inwentarz użyć, schemat — a dopiero potem
> zmieniać kod. `prompt_lint2.py` (czysty Python, stdlib) sprawdza to regułami dla czterech
> rodzajów promptów; jedyna reguła, która coś realnie parsuje, to walidacja przykładów
> few-shot względem bloku `<schema>`. Reszta to regexy po słowach kluczowych — **heurystyka,
> nie dowód jakości odpowiedzi modelu** (w tym wydaniu nie uruchamiano żadnego modelu).
> `golden-master/` pokazuje siatkę bezpieczeństwa: stara i nowa `CalculateTotal` porównane
> na 672 kombinacjach wejść, plus wersja z subtelnym błędem, którą test wykrywa.

## Struktura

```
code/
├── prompt_lint2.py        # lint: refactor_/migrate_/fewshot_/claudemd_ (stdlib, bez pip)
├── prompts/               # 8 promptów: *_bad.txt / *_good.txt
├── negative/              # test negatywny: few-shot z zepsutymi przykładami
└── golden-master/         # projekt .NET 10: stary vs nowy kod na siatce wejść
```

Rodzaj reguł wynika z prefiksu pliku, oczekiwanie z sufiksu (`_bad` / `_good`).

## Jak uruchomić

Wymagania: Python 3 (użyto 3.10.4), .NET SDK (użyto 10.0.400). Bez `pip install`.
Z katalogu głównego repo (`-B` = bez `__pycache__`):

```bash
python3 -B days/2026-09-27/ai-prompts/code/prompt_lint2.py
python3 -B days/2026-09-27/ai-prompts/code/prompt_lint2.py days/2026-09-27/ai-prompts/code/negative/fewshot_mutant_good.txt
python3 -B days/2026-09-27/ai-prompts/code/prompt_lint2.py --strict days/2026-09-27/ai-prompts/code/prompts/fewshot_bad.txt

dotnet run --project days/2026-09-27/ai-prompts/code/golden-master
dotnet run --project days/2026-09-27/ai-prompts/code/golden-master -- mutant
```

Własny prompt: nazwij plik `refactor_<x>.txt`, `migrate_<x>.txt`, `fewshot_<x>.txt` lub
`claudemd_<x>.txt`; z `--strict` exit 1, gdy czegoś brakuje.

## Weryfikacja — rzeczywisty output (uruchomione 2026-09-27)

### Samotest na `prompts/` (exit 0)

```
claudemd_bad.txt         [claudemd] 1/7  FAIL
    brak: min. 2 komendy w backtickach                       -> Podaj dokładne komendy build/test.
    brak: reguły z uzasadnieniem                             -> Przy regułach dopisz „bo/ponieważ”.
    brak: granice (czego nie ruszać)                         -> Napisz wprost, czego model NIE ma robić.
    brak: brak ogólników (clean code/SOLID/best practices)   -> Usuń ogólniki - model już je zna; zostaw to, czego nie da się wywnioskować.
    brak: brak historii firmy/zespołu                        -> Historia i personalia zjadają kontekst bez pożytku.
    brak: warunek „gotowe” (build+testy)                     -> Zapisz, jak agent ma sprawdzić własną pracę.
claudemd_good.txt        [claudemd] 7/7  PASS
fewshot_bad.txt          [fewshot ] 3/7  FAIL
    brak: jawny blok <schema>                                -> Opisz format wyjścia schematem, nie tylko przykładem.
    brak: przykłady zgodne ze schematem                      -> Każde <output> musi przechodzić schemat.
    brak: przykłady różnicują wartości enuma                 -> Przykłady muszą pokrywać różne wartości enum.
    brak: polecenie „odpowiedz wyłącznie…”                   -> Zakaż tekstu poza formatem.
fewshot_good.txt         [fewshot ] 7/7  PASS
migrate_bad.txt          [migrate ] 3/10  FAIL
    brak: min. 15 słów                                       -> Zbyt krótko - model musi zgadywać kontekst.
    brak: etap inwentarza przed zmianą                       -> Najpierw poproś o inwentarz użyć, potem o zmiany.
    brak: etapy / zakaz zaczynania od kodu                   -> Podziel na etapy z punktem akceptacji.
    brak: różnice zachowania do sprawdzenia                  -> Wypisz, co w nowej bibliotece/wersji zachowuje się inaczej.
    brak: kryterium sukcesu                                  -> Napisz po czym poznać, że gotowe.
    brak: kiedy się zatrzymać i zapytać                      -> Wskaż moment, w którym model ma przerwać i spytać.
    brak: granice (czego nie ruszać)                         -> Napisz wprost, czego model NIE ma robić.
migrate_good.txt         [migrate ] 10/10  PASS
refactor_bad.txt         [refactor] 0/9  FAIL
    brak: min. 15 słów                                       -> Zbyt krótko - model musi zgadywać kontekst.
    brak: wskazany plik                                      -> Podaj plik (np. `src/Foo.cs`).
    brak: zakres kodu (metoda/linie)                         -> Wskaż metodę i linie; „zrefaktoryzuj serwis” to setki decyzji.
    brak: konkretny cel refaktoryzacji                       -> Napisz CO ma być inaczej po refaktoryzacji (nie „czyściej”).
    brak: zachowanie bez zmian                               -> Zadeklaruj, że zachowanie ma zostać identyczne.
    brak: siatka bezpieczeństwa (testy przed zmianą)         -> Każ napisać testy charakteryzujące ZANIM ruszy kod produkcyjny.
    brak: małe kroki + test po każdym                        -> Wymuś małe kroki i uruchomienie testów po każdym.
    brak: granice (czego nie ruszać)                         -> Napisz wprost, czego model NIE ma robić.
    brak: format odpowiedzi                                  -> Narzuć format (lista kroków/tabela/diff).
refactor_good.txt        [refactor] 9/9  PASS

SAMOTEST: 8/8 wyników zgodnych z sufiksem _bad/_good.
```

Uwaga: `claudemd_bad.txt` zalicza regułę „<= 60 linii" (bo jest krótki) — zły prompt może być
krótki; lint tego nie ukrywa (1/7).

### Test negatywny (exit 1)

```
fewshot_mutant_good.txt  [fewshot ] 6/7  FAIL  <-- NIEZGODNE Z OCZEKIWANIEM (good)
    brak: przykłady zgodne ze schematem                      -> Każde <output> musi przechodzić schemat.
    walidator: przykład #1: `line` ma być int, jest str ('42')
    walidator: przykład #2: brak pola `comment`
    walidator: przykład #2: pole spoza schematu `text`
    walidator: przykład #2: `severity` = 'high' spoza enum ['krytyczne', 'wazne', 'nit']

SAMOTEST: 0/1 wyników zgodnych z sufiksem _bad/_good.
```

### Tryb `--strict` na `fewshot_bad.txt` (exit 1)

```
fewshot_bad.txt          [fewshot ] 3/7  FAIL
    brak: jawny blok <schema>                                -> Opisz format wyjścia schematem, nie tylko przykładem.
    brak: przykłady zgodne ze schematem                      -> Każde <output> musi przechodzić schemat.
    brak: przykłady różnicują wartości enuma                 -> Przykłady muszą pokrywać różne wartości enum.
    brak: polecenie „odpowiedz wyłącznie…”                   -> Zakaż tekstu poza formatem.

STRICT: 1 z 1 promptów oblanych.
```

### Golden master (.NET 10.0.400)

`dotnet run --project days/2026-09-27/ai-prompts/code/golden-master` (exit 0):

```
tryb=Refactored przypadkow=672 roznic=0
```

`... -- mutant` (exit 1; wypisuje pierwsze 5 różnic, tu wszystkie 5 i podsumowanie):

```
ROZNICA: cena=0.01 ilosc=10 lojalny=True kupon=- dzien=12/31/2026 stary=0.09 nowy=0.10
ROZNICA: cena=0.01 ilosc=10 lojalny=True kupon=- dzien=01/01/2027 stary=0.09 nowy=0.10
ROZNICA: cena=0.01 ilosc=10 lojalny=True kupon=SAVE10 dzien=12/31/2026 stary=0.08 nowy=0.09
ROZNICA: cena=0.01 ilosc=10 lojalny=True kupon=SAVE10 dzien=01/01/2027 stary=0.09 nowy=0.10
ROZNICA: cena=0.01 ilosc=10 lojalny=True kupon=save10 dzien=12/31/2026 stary=0.09 nowy=0.10
tryb=Mutant przypadkow=672 roznic=37
```

## Co NIE jest zweryfikowane

- Że prompty „dobre" wg lintu dają lepsze odpowiedzi modelu — żaden model nie był uruchamiany.
- Że few-shot faktycznie poprawia zgodność formatu u jakiegokolwiek konkretnego modelu.
- Że reguły działają na cudzych promptach: dobrane pod własne przykłady, regexy po polsku,
  łatwo je oszukać. Próg 60 linii dla CLAUDE.md jest umowny.
- `golden-master` dowodzi tylko zachowania mojej refaktoryzacji i mojej mutacji, nie tego,
  jak refaktoryzuje model. Format daty w output zależy od kultury systemu.
- Nazwy klas/plików/linii w promptach (`OrderService`, `Orders.Api`, „linie 40-118") są ilustracyjne.
