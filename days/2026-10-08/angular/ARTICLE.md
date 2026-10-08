<div align="center">

# 📰 TECH PRASÓWKA
### Wydanie #15 rubryki Angular — 8 października 2026

![Angular](https://img.shields.io/badge/Angular-DD0031?style=for-the-badge&logo=angular&logoColor=white)
![Signal Forms](https://img.shields.io/badge/Signal_Forms-debounce-1565C0?style=for-the-badge)

## Dwa różne „debounce" w Signal Forms — i dlaczego `submit()` potrafi zwalidować nieaktualny model

</div>

---

> _"Updates from the UI to the form model will be delayed until either the field is touched,
> or the most recently debounced update resolves."_
> — komentarz nad `debounce()` w `@angular/forms/signals` 22.2.1. Zwróć uwagę na słowa
> „updates from the UI **to the form model**": to opóźnia zapis do modelu, a nie wysyłkę
> requestu. W #13 poznaliśmy drugi „debounce" — w `validateHttp`. Dziś porównanie.

W #13 dodałem `debounce: 300` do `validateHttp`, żeby nie bombardować API przy każdej literze.
Zostały dwa niesprawdzone wątki: `debounce` jako **funkcja** oraz `request` zwracający
`undefined`. Przy okazji wyszło, że w Signal Forms istnieje **druga**, osobna reguła
`debounce(pole, …)`, o zupełnie innym działaniu. Dla .NET developera: to różnica między
opóźnieniem *bindingu* (`UpdateSourceTrigger=LostFocus` w WPF) a opóźnieniem *wywołania serwisu*
(`Throttle`/`Debounce` w Rx po stronie komunikacji).

| | |
|---|---|
| 🧱 Stack | `@angular/forms` **22.2.1**, `@angular/core` 22.2.1, `@angular/build`/CLI 22.2.2, TypeScript **6.0.3**, `rxjs` 7.8.2 |
| 🖥️ Środowisko | Node **v22.14.0**, npm 10.9.2, Vitest **5.0.3** + jsdom, fake timery, prawdziwe `<input>` w testach |
| ✅ Weryfikacja | `npm ci` (283 pakiety, 11 s), `ng build` OK (7,0 s, 233,03 kB), `ng test` **14/14** (2 pliki) + test mutacyjny |
| 📦 Kod | [`code/`](code/) — formularz nazwy projektu w pięciu wariantach schematu + 13 pomiarów |

**Plan:** (1) dwie reguły obok siebie, (2) pomiary reguły `debounce()`, (3) pułapka z `submit()`,
(4) `request → undefined` i `debounce` jako funkcja w `validateHttp`, (5) weryfikacja i luki.

---

## 1️⃣ Dwie reguły, dwie warstwy

### 🎣 Dlaczego to ważne

Wybór złej warstwy kończy się albo zbędnym ruchem w sieci, albo komunikatem walidacji, który
nie reaguje na to, co użytkownik wpisał. Zmierzone na prawdziwym `<input>`:

| | `debounce(p.name, …)` (reguła pola) | `debounce` w `validateHttp` |
|---|---|---|
| Co opóźnia | **zapis z UI do modelu** | start requestu (po zmianie modelu) |
| Model podczas pisania | stoi w miejscu | zmienia się przy każdym znaku |
| Walidatory sync (`required`, `minLength`) | też czekają (widzą stary model) | działają od razu |
| Argumenty | `number` \| `'blur'` \| `Debouncer` | `number` \| funkcja `(request, snapshot)` |

```typescript
// Warstwa 1: reguła pola - opóźnia ZAPIS z UI do modelu do utraty fokusu
debounce(p.name, 'blur');

// Warstwa 2: opcja validateHttp - opóźnia tylko request, model jest już aktualny
validateHttp<string, ExistsResponse>(p.name, {
  request: (ctx) => ({ url: '/api/projects/exists', params: { name: ctx.value() } }),
  debounce: 300,
  /* onSuccess, onError … */
});
```

Test „4 wpisy co 100 ms":

```text
debounce(pole, 300):          model w trakcie pisania: '', '', '', ''   -> po 300 ms 'prasow', 1 request
debounce w validateHttp:      model: 'pra','pras','prase','prasow'      -> po 300 ms 1 request
```

Efekt końcowy (1 request) jest ten sam, ale w pierwszym wariancie **cały formularz** widzi
nieaktualne dane, w drugim tylko HTTP czeka. Dlatego `'blur'` (pole w ogóle nie rusza modelu
w trakcie pisania) jest dobre dla drogich walidacji, a opcja w `validateHttp` dla komunikatów,
które mają reagować na bieżąco.

---

## 2️⃣ Co zmierzyłem w regule `debounce()`

Mechanikę przeczytałem w `_validation_errors-chunk.mjs` (UI zapisuje do `controlValue`, który
po debouncerze trafia do `value`) i sprawdziłem testami `debounce.spec.ts`.

- **`'blur'`**: wpisałem 3 wartości, odczekałem 5 s: `model().name == ''`, `value() == ''`,
  zero requestów — ale `dirty() == true` (pole „brudne" już po pierwszym znaku, choć model nietknięty).
  Po `blur`: model = `'prasow'`, `touched() == true`, **1** request.
- **Zapis programowy omija debounce**: `f.name().value.set('x')` zmienia model natychmiast.
  Debounce dotyczy tylko zapisów z kontrolki.
- **Programowy zapis kasuje oczekujący wpis z UI**: wpisane `'abc'` (czeka), potem
  `value.set('zzz')`, potem `blur` → model `'zzz'`. Wpis użytkownika przepada bez śladu.
- **Reguła na korzeniu obejmuje dzieci**: `debounce(p, 'blur')` na ścieżce głównej
  zadziałała na pole `name` (model pusty do blura). Źródło: `nodeState.debouncer` bierze regułę
  z rodzica, jeśli pole nie ma własnej.

### Własny `Debouncer` — haczyk z jednym wpisem opóźnienia

`Debouncer<TValue> = (ctx, abortSignal) => Promise<void> | void`. `void` oznacza „zapisz od razu".
Chciałem: krótkie nazwy od razu, dłuższe z 300 ms, decyzja po `ctx.value()`:

```typescript
(ctx, abortSignal) => ctx.value().length < 2 ? undefined : sleep(300)
```

Zmierzone:

```text
wpis 'abcd'   -> calls[0].modelValue = ''      -> void  -> model 'abcd' OD RAZU
wpis 'abcde'  -> calls[1].modelValue = 'abcd'  -> 300 ms
wpis 'abcdef' -> calls[1].aborted = true       -> po 300 ms model 'abcdef'
```

`ctx.value()` to wartość **z modelu**, czyli sprzed bieżącego wpisu — decyzja zapada na
podstawie poprzedniego stanu. Nowy tekst z kontrolki nie jest dostępny w kontekście
debouncera (nie znalazłem do niego publicznego dostępu w `FieldContext` — nie twierdzę, że go
nie ma). Poza tym każdy kolejny wpis wywołuje `abort` poprzedniego (`abortSignal` — używaj go
do sprzątania timerów, tak jak robi to wbudowane `debounceForDuration`).

---

## 3️⃣ ⚠️ Pułapka: `submit()` w trakcie debounce

### 🎣 Dlaczego to ważne

Klasyczny scenariusz: użytkownik wpisuje nazwę i naciska Enter albo programowo wołasz
`submit()`. Z debounce 300 ms model jest jeszcze pusty.

```text
m.type('prasowka');   // model().name == ''
await submit(f, action);
action wywołana?               nie  (błąd 'required' na starym, pustym modelu)
touched()                      true
po 300 ms: model().name        'prasowka'   // wpis i tak doleciał, ale już po submicie
```

`submit()` oznacza pola jako dotknięte, ale w moim teście **nie domknął** oczekującego wpisu
(widać po tym, że model dalej był pusty i akcja się nie odpaliła). W realnym UI klik w przycisk
najpierw rozmywa input (`blur` → `markAsTouched` → `flushSync`), więc test „blur przed submitem"
przechodzi: model aktualny, akcja wywołana raz. Ryzyko jest przy `Enter` w polu bez blura i przy
submit wywołanym z kodu. Nie sprawdzałem, czy to samo dotyczy klawisza Enter w prawdziwej
przeglądarce (brak przeglądarki).

Reguła praktyczna: `'blur'` + submit z kodu = najpierw `markAsTouched()` na polu, albo
unikaj debounce na polach, które mogą zostać zatwierdzone bez utraty fokusu.

---

## 4️⃣ `validateHttp`: `request → undefined` i `debounce` jako funkcja

**`request` zwracający `undefined`** to „nie sprawdzaj teraz" (inaczej niż `when`, ale efekt
widoczny dla pola podobny). Zmierzone (`offline = true`): zero requestów, `pending() == false`,
`valid() == true`.

Ciekawe odkrycie: gdy `request` zmieni się na `undefined` **w trakcie lotu requestu**:

```text
pending()        false   (od razu)
valid()          true
req.cancelled    false   <- request NIE został anulowany
późny flush({taken:true}) -> errors() == [], valid() == true  (odpowiedź zignorowana)
```

Przy zmianie *wartości* (z #13) request jest anulowany (`cancelled == true`); przy przejściu
na `undefined` — nie. Skutek uboczny jest tylko po stronie sieci (serwer dostaje zbędne
żądanie), stan formularza jest poprawny. Nie sprawdzałem tego w przeglądarce, tylko na
`HttpTestingController`.

**`debounce` jako funkcja** ma typ `DebounceTimer<…>` = `number | ((value, lastValue) => Promise<void> | void)`
(typ z `@angular/core`, oznaczony `@experimental 22.0`; sam `validateHttp` jest `@publicApi 22.0`).
`value` to obiekt requestu zwrócony przez `request`, `lastValue` to snapshot poprzedniego stanu.
Założyłem, że snapshot zacznie jako `'idle'` — **pomyliłem się**: zmierzony pierwszy status to
`'resolved'`, bo `debounced()` startuje z już „rozwiązaną" wartością początkową
(źródło: `core.mjs`, `computation` zwraca `status: 'resolved'`). Status `'loading'` oznacza otwarte
okno debounce.

Wzorzec „leading + trailing" (pierwszy wpis po przerwie od razu, seria z 300 ms):

```typescript
debounce: (request, last) => {
  const now = Date.now();
  const leading = now - lastStart > 1000;
  lastStart = now;
  return leading ? undefined : sleep(300);   // void = od razu
},
```

Wynik testu (`status` w kolejnych wywołaniach): `resolved, resolved, loading, resolved`;
requesty: `abc` (od razu), `abcde` (po 300 ms od ostatniego wpisu, `abcd` pominięty),
`abcdef` (od razu po 2 s przerwy).

---

## 5️⃣ Weryfikacja — prawdziwy output

Node w tej sesji: **v22.14.0**, a CLI 22.2.2 wymaga `>=22.22.3`. Obejście jak w #9/#12/#13/#14:
lokalna edycja progu w `node_modules/@angular/cli/src/utilities/node-version.js` (poza repo,
`node_modules/` w `.gitignore`), **do powtórzenia po każdym `npm ci`**. Zainstalowane wersje
zgłaszają `EBADENGINE` (warning npm).

```text
$ npm ci --no-audit --no-fund
added 283 packages in 11s

$ npm run build
main-J64AWHFI.js    | main   | 233.03 kB | 65.01 kB
Application bundle generation complete. [5.829 seconds]

$ npm test
 Test Files  2 passed (2)
      Tests  14 passed (14)
```

Test mutacyjny: usunąłem `debounce(p.name, 'blur')` z `blurSchema` → padły 2 testy
(`expected 'prasow' to be ''` i `expected 'abc' to be ''`). Po przywróceniu 14/14.

Pomyłki z tej sesji (zostawiam wprost): (1) założenie, że snapshot startuje jako `'idle'`;
(2) założenie, że `request → undefined` anuluje lot — nie anuluje; (3) pierwszy test submitu
„przechodził" tylko dlatego, że akcja po prostu się nie odpalała — zmieniłem go na jawne
sprawdzenie `action not called`; (4) w jednym logu diagnostycznym `http.match()` skonsumował
requesty i wyglądało to jak brak requestu — `match` usuwa dopasowane z kolejki.

### ⚠️ Co jest niezweryfikowane (wprost)

- **`ng serve`/przeglądarka**, w tym Enter w polu z `debounce('blur')` — brak przeglądarki.
- `debounce('blur')` na **własnej kontrolce** `FormValueControl` (wymaga wyemitowania `touch`
  na `blur`, wg komentarza w `.d.ts`) — tylko z typów, bez testu.
- Dostęp do wpisanego tekstu wewnątrz `Debouncer` (nie znalazłem publicznej drogi).
- Pozostałe opcjonalne pola `FormUiControl` (`required`/`pattern`/`readonly`/`hidden`/
  `disabledReasons`/`name`), SSR/hydration, `mapResponse()`.
- Obejście progu wersji Node nie powinno wpływać na wyniki, ale to założenie.

---

## 🧭 Do zapamiętania

| Potrzeba | Narzędzie |
|---|---|
| Model nie zmienia się w trakcie pisania | `debounce(p.pole, 'blur' \| ms)` |
| Tylko request ma czekać | `validateHttp({ debounce: ms })` |
| Własna logika opóźnienia | `Debouncer` / funkcja; `void` = od razu |
| Decyzja po aktualnym tekście | nie przez `ctx.value()` w `Debouncer` — to wartość z modelu |
| `submit()` z kodu przy `'blur'` | najpierw `markAsTouched()` |
| Wyłączyć sprawdzanie | `request → undefined` (lot nie jest anulowany) |
| Snapshot w `debounce` funkcji | `'resolved'` na start, `'loading'` w oknie debounce |

**Następnym razem (propozycja):** `debounce('blur')` na własnej kontrolce, pozostałe pola
`FormUiControl`, `mapResponse()` z `@ngrx/operators` w efektach zdarzeń, SSR/hydration.

---

## 📎 Jak uruchomić

Zobacz [`code/README.md`](code/README.md).

---

<div align="center">

[← wróć do wydania (wszystkie rubryki)](../README.md) · [spis wydań](../../../README.md)

</div>
