# Kod do wydania #6 — skill `angular-signals-review` (antywzorce Angular Signals)

Pełny artykuł: [`../ARTICLE.md`](../ARTICLE.md).

## Fragment prasówki, którego dotyczy ten kod

> **Skill `angular-signals-review`**: deterministyczny skaner `scan_signals.py` (regex +
> ręczne równoważenie nawiasów, stdlib, bez parsera TypeScript) wyłapuje sześć konkretnych
> antywzorców Angular Signals: `effect()` używany do synchronizacji stanu zamiast
> `computed()`, `effect()` czytający i zapisujący ten sam sygnał, mutację innego sygnału
> wewnątrz `computed()`, mutowanie argumentu w `.update()` zamiast zwrócenia nowej wartości,
> brak `ChangeDetectionStrategy.OnPush` w komponencie korzystającym z signals, oraz (jako
> INFO, nie WARN) brak `untracked()` przy odczycie ≥2 sygnałów w jednym `effect()`. Skaner
> daje kandydatów, `SKILL.md` prowadzi Claude przez ocenę kontekstową.

## Struktura

```
code/
├── claude-skills/angular-signals-review/   # -> .claude/skills/angular-signals-review/
│   ├── SKILL.md
│   └── scan_signals.py           # regexowy skaner .ts (stdlib, bez zależności)
├── samples/
│   ├── bad.component.ts          # 6 antywzorców, po jednym na regułę
│   └── good.component.ts         # te same funkcje, poprawione
└── run_tests.py                  # 2 przypadki: bad -> 6 reguł, good -> cisza
```

Wymagania: Python 3.8+ (tylko stdlib). Node/Angular CLI **nie** są potrzebne — skaner
czyta pliki `.ts` jako tekst, nie kompiluje ich.

## Jak uruchomić

Z katalogu `code/`:

```bash
python3 run_tests.py
python3 claude-skills/angular-signals-review/scan_signals.py samples/bad.component.ts
python3 claude-skills/angular-signals-review/scan_signals.py samples/good.component.ts
```

Użycie w prawdziwym repo:

```bash
mkdir -p .claude/skills
cp -r claude-skills/angular-signals-review .claude/skills/
```

## Weryfikacja — co uruchomiono naprawdę

Python 3.10.4:

```
$ python3 run_tests.py
OK    bad.component.ts     reguly: COMPUTED-SIDE-EFFECT, EFFECT-SELF-WRITE, EFFECT-STATE-SYNC, MUTATING-UPDATE, ONPUSH-MISSING, UNTRACKED-CANDIDATE
OK    good.component.ts    reguly: -

WYNIK: 2/2 przypadkow zgodnych
```

Pełny output skanera na `bad.component.ts` (exit 1):

```
$ python3 claude-skills/angular-signals-review/scan_signals.py samples/bad.component.ts
samples/bad.component.ts:6 | WARN | ONPUSH-MISSING | komponent uzywa signal()/computed()/input(), ale @Component nie ma changeDetection: ChangeDetectionStrategy.OnPush - bez OnPush Angular nadal sprawdza caly poddrzewo przy kazdym cyklu zone.js, tracisz glowna zalete signals
samples/bad.component.ts:35 | WARN | EFFECT-STATE-SYNC | effect() czyta ['firstName', 'lastName'] i ustawia ['fullName'] - to synchronizacja stanu wyliczanego z innych sygnalow, klasyczny przypadek dla computed(), nie effect()
samples/bad.component.ts:35 | INFO | UNTRACKED-CANDIDATE | effect() czyta 2 sygnaly (['firstName', 'lastName']) bez untracked() - jesli niektore sluzą tylko jako wartosc do odczytania (nie mają wyzwalac ponownego uruchomienia), rozwaz untracked(() => ...) dla nich
samples/bad.component.ts:43 | WARN | EFFECT-SELF-WRITE | effect() odczytuje i w tym samym ciele zapisuje ten sam sygnal (['count']) - ryzyko petli (kazdy set/update planuje kolejne wykonanie effect)
samples/bad.component.ts:53 | INFO | UNTRACKED-CANDIDATE | effect() czyta 2 sygnaly (['count', 'items']) bez untracked() - jesli niektore sluzą tylko jako wartosc do odczytania (nie mają wyzwalac ponownego uruchomienia), rozwaz untracked(() => ...) dla nich
samples/bad.component.ts:60 | WARN | COMPUTED-SIDE-EFFECT | computed() wywoluje total.set()/update() - computed() ma byc CZYSTA funkcja odczytu, mutacja innego sygnalu w środku to efekt uboczny (nieprzewidywalna liczba wywolan, zależna od tego kto i kiedy odczyta computed)
samples/bad.component.ts:72 | WARN | MUTATING-UPDATE | .update() mutuje parametr 'list' w miejscu (push) zamiast zwrocic nowy obiekt/tablice - domyslna rownosc sygnalu to referencyjna (===); mutacja w miejscu psuje wykrywanie zmian, jesli ta sama referencja trafi gdzie indziej niezmieniona
```

Na `good.component.ts` (exit 0):

```
$ python3 claude-skills/angular-signals-review/scan_signals.py samples/good.component.ts
samples/good.component.ts | brak uwag
```

### Czego NIE zweryfikowano

- **Węzeł Node.js / Angular CLI / `ng build` / `ng lint`**: brak w środowisku, w którym
  powstał ten artykuł. `bad.component.ts` i `good.component.ts` nie zostały skompilowane
  przez prawdziwy kompilator Angulara ani sprawdzone przez `tsc` — mogą zawierać drobne
  literówki składniowe, które regexowy skaner by nie wychwycił. Kod pisany ręcznie,
  wzorowany na oficjalnej dokumentacji API Signals.
- **Auto-aktywacja skilla** w żywej sesji Claude Code na podstawie `description` z
  frontmatteru oraz działanie `allowed-tools: Bash(python3 *scan_signals.py*)` — bez
  żywej sesji nie da się tego sprawdzić, tylko przeczytać dokumentację formatu skilli.
- Skaner to regex + ręczne równoważenie nawiasów, nie parser TypeScript: możliwe fałszywe
  alarmy/przeoczenia na kodzie rozbitym na wiele metod pomocniczych, z destrukturyzacją
  parametrów `update()` (`({ a, b }) => ...`) albo z `effect()`/`computed()` importowanymi
  pod aliasem (`import { effect as fx } from '@angular/core'`).
- Reguła `EFFECT-STATE-SYNC` nie odróżnia „czystej" synchronizacji stanu od `effect()`,
  który dodatkowo robi coś jeszcze (np. wywołanie API) — to ocena kontekstowa zostawiona
  modelowi w kroku 2 `SKILL.md`, nie skanerowi.
