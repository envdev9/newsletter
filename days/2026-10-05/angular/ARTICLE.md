<div align="center">

# 📰 TECH PRASÓWKA
### Wydanie #12 rubryki Angular — 5 października 2026

![Angular](https://img.shields.io/badge/Angular-DD0031?style=for-the-badge&logo=angular&logoColor=white)
![NgRx](https://img.shields.io/badge/NgRx-BA2BD2?style=for-the-badge&logo=ngrx&logoColor=white)

## `tapResponse()` z `@ngrx/operators`: dlaczego "wsadź gdziekolwiek w `rxMethod`" jest złą radą — i czym NAPRAWDĘ różni się od ręcznego `tap`+`catchError`

</div>

---

> _"Handles the response in ComponentStore effects in a safe way, without additional
> boilerplate. It enforces that the error case is handled and that the effect would still be
> running should an error occur."_ — komentarz nad `tapResponse()` w `@ngrx/operators`
> 22.0.1. Brzmi jak "użyj mnie i strumień nigdy nie umrze". To NIEPRAWDA w sensie
> dosłownym — i dziś to pokazuję na realnym, failującym teście, zanim przejdę do tego, co
> `tapResponse()` faktycznie daje (czytając skompilowane źródło `ngrx-operators.mjs`, nie
> tylko komentarz).

Wydanie #4 (26.09) nauczyło `catchError` **wewnątrz** `switchMap` jako sposobu, żeby błąd
jednego żądania nie zabijał całego strumienia `rxMethod` — i poprzestało na tym, bez
pokazania, co się stanie, jeśli ktoś to umieści źle. Dziś biorę ten sam wzorzec
wyszukiwania produktów (`debounceTime` → `distinctUntilChanged` → `switchMap`) i robię trzy
rzeczy: (1) odtwarzam realistyczny błąd — wyciągnięcie `tap`/`catchError` PO `switchMap` —
i dowodzę testem, że to faktycznie zabija `rxMethod` na zawsze; (2) obalam mit, że
`tapResponse()` z nowego pakietu `@ngrx/operators` sam z siebie chroni przed tym błędem
(nie chroni — to wciąż tylko `tap`+`catchError` w środku, umieszczony źle psuje się
identycznie); (3) pokazuję, co `tapResponse()` NAPRAWDĘ daje: `error` wymagany przez typy
(nie da się o nim "zapomnieć" tak jak przy gołym `tap`) i `finalize`, które odpala się
**także** dla żądania anulowanego przez `switchMap` — czego żaden ręczny `tap`/`catchError`
nie zrobi, bo `next`/`error` po anulowaniu po prostu nigdy nie wystrzelą.

| | |
|---|---|
| 🧱 Stack | `@angular/core`/`@angular/common` **22.2.0**, `@angular/cli` **22.2.1**, `@ngrx/signals` **22.0.1**, `@ngrx/operators` **22.0.1** (NOWY pakiet w tej rubryce), TypeScript **6.0.3** |
| 🖥️ Środowisko | Node **v22.14.0**, npm **10.9.2**, testy: Vitest **5.0.3** + jsdom, `HttpTestingController` |
| ✅ Weryfikacja | `npm ci` (283 pakiety, 11s), `ng build` OK (5.76s, 148.75 kB), `ng test` **9/9** (4 pliki) — sekcja 4 |
| 📦 Kod | [`code/`](code/) — wyszukiwarka produktów: TRZY warianty tego samego `rxMethod` do porównania |

**Plan:** (1) realistyczny błąd — `tap`/`catchError` PO `switchMap`, dowód testem że
`rxMethod` umiera po jednym błędzie na zawsze, (2) ten sam błąd z `tapResponse()` — mit
obalony cytatem ze źródła i testem, (3) gdzie `tapResponse()` naprawdę pomaga: wymuszony
`error` + `finalize` na żądaniu anulowanym przez `switchMap`, (4) realna weryfikacja —
`npm ci`/`ng build`/`ng test`, ta sama (znana z poprzednich wydań) niespodzianka z wersją
Node, i nowy wariant pułapki "goły `vitest run`".

---

## 1️⃣ Realistyczny błąd: `tap`/`catchError` PO `switchMap`, nie w środku

### 🎣 Dlaczego to ważne

Wydanie #4 pokazało POPRAWNY wzorzec: `catchError` **wewnątrz** `switchMap`, czyli na
strumieniu JEDNEGO żądania. To, co tam NIE zostało pokazane: co się dzieje, jeśli ktoś —
przy "upraszczającej" refaktoryzacji, bo zagnieżdżony `.pipe()` w `.pipe()` wygląda
nieczytelnie — wyciągnie `tap` (sukces) i `catchError` na płaski, jeden poziom, PO
`switchMap`. To jest dokładnie taki kod, jaki pisze się, gdy się nie myśli o tym, że
`switchMap` tworzy WEWNĘTRZNY strumień per żądanie:

```typescript
// search-broken-outer-catch.store.ts (wycinek - ANTY-PRZYKŁAD)
search: rxMethod<string>(
  pipe(
    map((q: string) => q.trim()),
    debounceTime(300),
    distinctUntilChanged(),
    tap((query) => patchState(store, { query, loading: true, error: null })),
    switchMap((query) => api.search(query)),
    // BUG: to są operatory na strumieniu OUTER, nie na strumieniu, który switchMap
    // wyprodukował dla JEDNEGO żądania.
    tap((products) => patchState(store, { products, loading: false })),
    catchError(() => {
      patchState(store, { loading: false, error: 'Nie udało się pobrać produktów', products: [] });
      return of(null);
    }),
  ),
),
```

Mechanika: `rxMethod` subskrybuje się na całym `pipe()` **raz**, na całe życie store'a.
Kiedy `api.search()` zwróci błąd, propaguje się on przez `switchMap` w górę do
zewnętrznego `catchError`, który go łapie i zwraca `of(null)` — ale to `of(null)` jest
teraz OSTATNIM elementem CAŁEGO zewnętrznego strumienia. Emituje `null`, kompletuje się —
a RxJS przy komplecie automatycznie odpina (unsubscribe) CAŁY łańcuch w górę, aż do
jedynej, długożyjącej subskrypcji `rxMethod`. Subject, do którego `search()` robi
`.next(query)`, nadal istnieje — ale nikt już go nie słucha.

Dowód — test, który najpierw wywołuje błąd, potem wysyła kolejne, poprawne zapytanie:

```typescript
// search-broken-outer-catch.store.spec.ts
store.search('boom');
vi.advanceTimersByTime(300);
http.expectOne('/api/products?q=boom').flush('x', { status: 500, statusText: 'Server Error' });
expect(store.error()).toBe('Nie udało się pobrać produktów');

store.search('mysz'); // poprawne zapytanie, PO błędzie
vi.advanceTimersByTime(300);
http.expectNone('/api/products?q=mysz'); // DOWÓD: żadne żądanie nie wyszło
```

Żeby sprawdzić, czy ten test jest wartościowy (a nie przechodzi "przypadkiem"), zamieniłem
na chwilę `expectNone` na `expectOne` i odpaliłem ponownie — i dostałem realny fail:

```text
Error: Expected one matching request for criteria "Match URL: /api/products?q=mysz", found none.
```

To jest JEDYNY dowód, jakiego potrzeba: żądanie naprawdę nie wyszło, nie jest to błąd w
asercji. W aplikacji produkcyjnej ten bug wygląda tak: "wyszukiwarka przestała działać po
jednym błędzie sieci" — bez wyjątku w konsoli, bez crasha, bo `catchError` "zadziałał"
(złapał błąd) — tylko że przy tym ubił strumień, który miał żyć wiecznie.

---

## 2️⃣ Mit: `tapResponse()` NIE jest "bezpieczny niezależnie od miejsca w `pipe`"

### 🎣 Dlaczego to ważne

Dokumentacja `tapResponse()` (komentarz w `.d.ts`/źródle) mówi: *"enforces that the error
case is handled and that the effect would still be running should an error occur"*. Łatwo
to przeczytać jako "użyj `tapResponse()` i nie musisz już myśleć o miejscu w pipe'ie". To
jest pułapka — sprawdziłem skompilowane źródło (`node_modules/@ngrx/operators/fesm2022/
ngrx-operators.mjs`), żeby zobaczyć, co `tapResponse()` faktycznie ROBI, nie tylko co
obiecuje:

```javascript
// ngrx-operators.mjs - cała implementacja tapResponse()
function tapResponse(observer) {
    return (source) => source.pipe(
      tap({ next: observer.next, complete: observer.complete }),
      catchError((error) => {
        observer.error(error);
        return EMPTY;
      }),
      observer.finalize ? finalize(observer.finalize) : (source$) => source$,
    );
}
```

To jest **dosłownie** `tap` + `catchError` (zwracający `EMPTY` zamiast `of(null)` —
funkcjonalnie to samo: "pochłoń błąd, dokończ ten strumień cicho") + opcjonalny
`finalize`. Żadnej magii, żadnego specjalnego traktowania pozycji w `pipe()`. Więc jeśli
umieszczę go PO `switchMap`, dokładnie tak jak w anty-przykładzie #1:

```typescript
// search-broken-outer-tap-response.store.ts (wycinek - ANTY-PRZYKŁAD #2)
switchMap((query) => api.search(query)),
// BUG: tapResponse() tutaj NIE jest "wewnątrz switchMap" - operuje na strumieniu
// OUTER, dokładnie jak błędny catchError w anty-przykładzie #1.
tapResponse({
  next: (products: Product[]) => patchState(store, { products, loading: false }),
  error: () => patchState(store, { loading: false, error: 'Nie udało się pobrać produktów', products: [] }),
}),
```

...dostaję TEN SAM bug. Test jest kopią testu z sekcji 1, z inną nazwą store'a — i
przechodzi (czyli: bug faktycznie się powtarza):

```typescript
// search-broken-outer-tap-response.store.spec.ts
store.search('boom');
vi.advanceTimersByTime(300);
http.expectOne('/api/products?q=boom').flush('x', { status: 500, statusText: 'Server Error' });

store.search('mysz');
vi.advanceTimersByTime(300);
http.expectNone('/api/products?q=mysz'); // DOWÓD: tapResponse() źle umieszczony = ten sam bug
```

**Wniosek:** `tapResponse()` to narzędzie DO UŻYCIA WEWNĄTRZ `switchMap`/`exhaustMap`/
`concatMap` — tam, gdzie i tak powinien być `catchError` (wiedza z wydania #4) — nie
zamiennik myślenia o miejscu w pipe'ie. Dokumentacja NgRx w swoim przykładzie (`@usageNotes`
w `.d.ts`) też go tak umieszcza: wewnątrz `exhaustMap`. To nie jest przypadek.

---

## 3️⃣ Gdzie `tapResponse()` NAPRAWDĘ pomaga: typy + `finalize` na anulowaniu

### 🎣 Dlaczego to ważne

Skoro poprawnie umieszczony ręczny `tap`+`catchError` (wydanie #4) i poprawnie umieszczony
`tapResponse()` dają TEN SAM efekt "strumień żyje po błędzie" — to po co w ogóle
`tapResponse()`? Dwie realne różnice, obie widoczne w typach i w zachowaniu, nie w
marketingu:

**(a) `error` jest WYMAGANY przez typy.** `TapResponseObserver<T, E>` z `.d.ts`:

```typescript
type TapResponseObserver<T, E> = {
  next: (value: T) => void;
  error: (error: E) => void;      // BRAK znaku '?' - wymagany, nie opcjonalny
  complete?: () => void;
  finalize?: () => void;
};
```

Przy gołym `tap({ next: ... })` kompilator NIE zmusi cię do dopisania `catchError` gdzieś
dalej — można o nim zwyczajnie zapomnieć, i błąd ucieknie w górę (czyli: dokładnie bug z
sekcji 1, tylko bez `catchError` wcale, nie ze złym miejscem). `tapResponse({ next })` bez
`error` **nie skompiluje się**. To przenosi "czy obsłużyłem błąd?" z code review na
kompilator — coś, czego .NET developer rozpozna jako różnicę między `Try`/`catch`
opcjonalnym a wymuszonym przez sygnaturę.

**(b) `finalize` odpala się TAKŻE przy anulowaniu przez `switchMap`.** To jest rzecz, której
żaden ręczny `tap(next)`/`catchError(error)` nie zrobi strukturalnie: gdy `switchMap`
anuluje żądanie (bo przyszło nowsze), anulowane żądanie NIE dostaje `next`, NIE dostaje
`error` — po prostu zostaje odpięte. `finalize` z RxJS to teardown-callback (jak `finally`
w .NET) — odpala się przy complete, error LUB unsubscribe. W moim `search.store.ts`
używam tego do licznika `pendingCount`, który musi wrócić do zera niezależnie od tego, czy
żądanie się powiodło, zepsuło, czy zostało anulowane:

```typescript
// search.store.ts (wycinek - WERSJA IDIOMATYCZNA)
switchMap((query) =>
  api.search(query).pipe(
    tapResponse({
      next: (products) => patchState(store, { products }),
      error: () => patchState(store, { error: 'Nie udało się pobrać produktów', products: [] }),
      // Odpala się ZAWSZE - sukces, błąd, ANULOWANIE przez nowsze szukanie.
      finalize: () => patchState(store, (s) => ({ loading: false, pendingCount: s.pendingCount - 1 })),
    }),
  ),
),
```

Dowód testem — dwa szybkie wyszukiwania, pierwsze anulowane przez drugie:

```typescript
// search.store.spec.ts
store.search('a');
vi.advanceTimersByTime(300);
const first = http.expectOne('/api/products?q=a');
expect(store.pendingCount()).toBe(1);

store.search('ab'); // nowe zapytanie ANULUJE poprzednie (switchMap)
vi.advanceTimersByTime(300);
const second = http.expectOne('/api/products?q=ab');
expect(first.cancelled).toBe(true);           // 'a' anulowane - BEZ next, BEZ error
expect(store.pendingCount()).toBe(1);          // ale finalize dla 'a' JUŻ zdjął licznik (1, nie 2)

second.flush([KEYBOARD]);
expect(store.pendingCount()).toBe(0);          // finalize dla 'ab' też odpalił
```

Gdybym tę samą logikę próbował napisać ręcznym `tap`/`catchError` bez `finalize`, licznik
`pendingCount` dla anulowanego żądania 'a' NIGDY by nie spadł — bo ani `tap(next)`, ani
`catchError`/`error` nie dostają szansy wystrzelić dla strumienia, który został odpięty, a
nie zakończony błędem czy sukcesem. To jest różnica, której nie da się obejść "więcej
kodu w `tap`" — to własność samego `finalize` jako operatora teardown, nieobsługiwalna
przez `next`/`error`.

---

## 4️⃣ Weryfikacja — prawdziwy output

Node w tej sesji: **v22.14.0** (sprawdzone na starcie, `node --version`) — ta sama
sytuacja co w wydaniu #9 (02.10): `@angular/cli` 22.2.1 wymaga `>=22.22.3`, pierwsza próba
`ng build` kończy się błędem:

```text
$ npx ng build
Node.js version v22.14.0 detected.
The Angular CLI requires a minimum Node.js version of v22.22.3 or v24.15.0 or v26.0.0.
```

Zastosowany WYŁĄCZNIE lokalnie workaround (identyczny jak w wydaniu #9, nieobecny w repo —
plik w `node_modules/`, w `.gitignore`): zmiana progu w
`node_modules/@angular/cli/src/utilities/node-version.js`
(`^22.22.3 || ...` → `^22.14.0 || ...`). Po tej zmianie realny `npm ci`/`ng build`/`ng test`
przeszły od zera, bez żadnego innego problemu:

```text
$ npm ci --no-audit --no-fund
added 283 packages in 11s

$ npx ng build
Initial chunk files | Names    |  Raw size | Estimated transfer size
main-675XAML6.js     | main     | 148.75 kB |  43.94 kB
styles-5INURTSO.css  | styles   |   0 bytes |   0 bytes
Application bundle generation complete. [5.764 seconds]

$ npx ng test --no-watch
 Test Files  4 passed (4)
      Tests  9 passed (9)
   Duration  3.05s
```

9 testów w 4 plikach: `search-broken-outer-catch.store.spec.ts` (2 — anty-przykład #1),
`search-broken-outer-tap-response.store.spec.ts` (2 — anty-przykład #2), `search.store.spec.ts`
(4 — debounce/sukces, błąd-strumień-żyje, `finalize` na anulowaniu, `isEmpty`), `app.spec.ts`
(1). Zero poprawek po drodze.

Sprawdziłem też ponownie pułapkę "goły `vitest run` bez `ng test`" (znaną z wydań #7/#9) —
dziś wyszedł INNY komunikat błędu niż poprzednio (co samo jest ciekawe — pokazuje, że to nie
jeden konkretny błąd, a cała kategoria "Angular poza `ng test`/`TestBed` nie jest
skonfigurowany"):

```text
$ npx vitest run
Error: The service 'BrowserXhr' needs to be compiled using the JIT compiler, but
'@angular/compiler' is not available.
 Test Files  4 failed (4)
      Tests  no tests
```

### ⚠️ Co jest niezweryfikowane (wprost)

- **`ng serve`/przeglądarka** — jak w każdym poprzednim wydaniu, cała weryfikacja to
  `ng build` + testy w jsdom (Vitest/`HttpTestingController`), nie realny HTTP w
  przeglądarce.
- **`mapResponse()`** (siostrzany operator z tego samego `@ngrx/operators`, do użycia w
  `@ngrx/effects`, nie w `rxMethod`) — widziany w źródle przy tej okazji, nieużyty w
  kodzie dzisiejszego wydania (ta rubryka nie dotykała jeszcze `createEffect`/Actions).
- **`validateHttp`, SSR/hydration, reszta opcjonalnego `FormUiControl`** — wciąż
  nieruszone (lista z wydania #9).

---

## 🧭 Do zapamiętania

| Potrzeba | Narzędzie |
|---|---|
| Błąd jednego żądania w `switchMap`/`exhaustMap`/`concatMap` nie ma zabić całego `rxMethod` | `catchError`/`tapResponse` MUSZĄ być wewnątrz `.pipe()` zwracanego przez projection function, nigdy na zewnętrznym, płaskim `pipe()` |
| Sprawdzenie, czy "miejsce w pipe" naprawdę ma znaczenie, a nie tylko wybór operatora | `tapResponse()` to tylko `tap`+`catchError`+opcjonalny `finalize` (patrz `ngrx-operators.mjs`) — źle umieszczony psuje się identycznie jak gołe `catchError` |
| Wymuszenie (przez kompilator, nie code review), że błąd z `rxMethod` jest obsłużony | `tapResponse({ next, error })` — `error` jest WYMAGANY w `TapResponseObserver<T, E>`, w przeciwieństwie do osobnego `catchError`, o którym można zapomnieć |
| Czyszczenie stanu (licznik, flaga `loading`) niezależnie od tego, czy żądanie się powiodło, zepsuło, czy zostało anulowane przez `switchMap` | `finalize` w `tapResponse(...)` — jedyny z trzech callbacków, który odpala się TAKŻE na `unsubscribe` (anulowanie), nie tylko `next`/`error` |

**Następnym razem (propozycja):** `validateHttp` (async walidacja wprost na `httpResource`),
`ng serve` w przeglądarce (jeśli środowisko na to pozwoli), `mapResponse()` w kontekście
`@ngrx/effects`/Actions (dziś poza zakresem — ta rubryka nie dotykała jeszcze efektów na
akcjach, tylko `rxMethod` w signal store).

---

## 📎 Jak uruchomić

Zobacz [`code/README.md`](code/README.md).

---

<div align="center">

[← wróć do wydania (wszystkie rubryki)](../README.md) · [spis wydań](../../../README.md)

</div>
