---
name: angular-signals-review
description: Review komponentow Angular korzystajacych z Signals (signal(), computed(), effect(), input()) pod katem antywzorcow - effect() uzywany do synchronizacji stanu zamiast computed(), mutacja sygnalu wewnatrz computed(), efekt czytajacy i zapisujacy ten sam sygnal, mutowanie argumentu w update() zamiast zwracania nowej wartosci, brak ChangeDetectionStrategy.OnPush. Uzyj gdy ktos dodaje/edytuje komponent .ts z signals, prosi o review pod katem signals albo pyta "czemu ten efekt/computed dziwnie sie zachowuje".
allowed-tools: Read, Glob, Grep, Bash(python3 *scan_signals.py*)
---

# angular-signals-review

Dwa kroki: **deterministyczny skaner** (regex + rownowazenie nawiasow, nic nie umyka w
oczywistych przypadkach), potem **ocena kontekstowa** - skaner nie zna intencji autora
ani reszty aplikacji, tylko wskazuje kandydatow.

## Krok 1 - skaner

```bash
python3 .claude/skills/angular-signals-review/scan_signals.py <plik.component.ts> [...]
```

Wyjscie: linie `plik:linia | WARN/INFO | REGULA | opis`, exit 1 = jest choc jeden WARN.
INFO to sugestia do rozwazenia, nie blad.

Reguly:

| Regula | Poziom | Co wykrywa |
|---|---|---|
| `EFFECT-STATE-SYNC` | WARN | `effect()` czyta inne sygnaly i `.set()`/`.update()` na sygnale wyliczanym z nich - to zadanie dla `computed()` |
| `EFFECT-SELF-WRITE` | WARN | `effect()` czyta i w tym samym ciele zapisuje ten sam sygnal - ryzyko petli/nadmiarowych przebiegow |
| `COMPUTED-SIDE-EFFECT` | WARN | `computed()` wywoluje `.set()`/`.update()` na innym sygnale - `computed()` ma byc czyste |
| `MUTATING-UPDATE` | WARN | `.update(x => ...)` mutuje `x` w miejscu (`push`/`splice`/`sort`/`x[i]=`/...) zamiast zwrocic nowa wartosc |
| `ONPUSH-MISSING` | WARN | plik uzywa signals, ale `@Component` nie ma `changeDetection: ChangeDetectionStrategy.OnPush` |
| `UNTRACKED-CANDIDATE` | INFO | `effect()` czyta >=2 sygnaly bez `untracked()` w ciele - warto sprawdzic, czy wszystkie maja wyzwalac ponowne uruchomienie |

Ograniczenia (wazne, zeby nie ufac skanerowi bezkrytycznie): to regex na tekscie, nie
parser TypeScript. Nie rozumie warunkow, nie wie czy `effect()` faktycznie powinien tylko
czytac, i moze przeoczyc wzorce rozbite na wiele funkcji pomocniczych (np. mutacja w
osobnej metodzie wywolanej z `update()`).

## Krok 2 - ocena kontekstowa

1. **`EFFECT-STATE-SYNC`.** Sprawdz, czy `effect()` robi TYLKO to (przepisz na `computed()`),
   czy tez ma dodatkowy, prawdziwy efekt uboczny (np. wywolanie API, `localStorage`,
   nawigacja) - wtedy `effect()` zostaje, ale rozwaz rozdzielenie: `computed()` dla
   wartosci + `effect()` tylko dla akcji.
2. **`EFFECT-SELF-WRITE`.** Czy warunek (`if`) faktycznie chroni przed nieskonczona petla,
   czy tylko odracza problem o jeden krok? Zaproponuj przepisanie bez odczytu wlasnej
   wartosci sygnalu w tym samym efekcie (np. przez `untracked()` albo `computed()`).
3. **`COMPUTED-SIDE-EFFECT`.** To zawsze do poprawy - `computed()` moze zostac policzone
   0 razy (nikt nie czyta) albo wielokrotnie (kilku konsumentow, re-ewaluacja), efekt
   uboczny w srodku jest z definicji niedeterministyczny. Wydziel drugi `computed()` albo
   przenies logike do `effect()`.
4. **`MUTATING-UPDATE`.** Sprawdz typ danych: dla tablic/obiektow zawsze zwracaj nowa
   referencje (`[...arr, x]`, `{ ...obj, key: val }`). Dla `Map`/`Set` rozwaz `signal`
   z customowa funkcja `equal` albo jawne kopiowanie (`new Map(m)`).
5. **`ONPUSH-MISSING`.** Sprawdz, czy komponent nie polega gdzies na mutacji obiektow
   przekazywanych przez `@Input()` bez signals (OnPush wtedy nie zauwazy zmiany) - jesli
   tak, to najpierw trzeba naprawic te mutacje, dopiero potem dodac OnPush.
6. **`UNTRACKED-CANDIDATE`.** To tylko INFO - czesto oba odczyty MAJA wyzwalac ponowne
   uruchomienie i tak jest poprawnie. Zapytaj/sprawdz w kodzie wywolujacym, czy autor
   chcial reagowac na oba sygnaly, czy tylko na jeden.

## Format odpowiedzi

| Plik:linia | Ryzyko | Problem | Proponowana poprawka (fragment kodu) |
|---|---|---|---|

Pod tabela: jedno zdanie o tym, czego skaner nie sprawdza (np. logika rozbita na wiele
plikow/serwisow) i czy warto dodatkowo spojrzec na testy komponentu.
