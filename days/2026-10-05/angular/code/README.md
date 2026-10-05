# Kod do wydania Angular z 05.10.2026 — `tapResponse()` z `@ngrx/operators`: gdzie naprawdę pomaga

Pełny artykuł: [`../ARTICLE.md`](../ARTICLE.md).

Wymagania: **Node.js** (zweryfikowane na v22.14.0 — zob. sekcja "Uwaga o wersji Node"
niżej) i **npm** (zweryfikowane na 10.9.2). Wersje: `@angular/core`/`@angular/common` i
`@angular/cli` **22.2.1**, `@ngrx/signals` **22.0.1**, `@ngrx/operators` **22.0.1**
(NOWY pakiet w tej rubryce), TypeScript **6.0.3**, `vitest` **5.0.3** (jsdom, bez
przeglądarki), `rxjs` **7.8.2**.

## Fragment prasówki, którego dotyczy ten kod

> **Mit:** `tapResponse()` "chroni" `rxMethod` przed śmiercią strumienia niezależnie od
> tego, gdzie go umieścisz w `pipe()`. NIEPRAWDA — skompilowane źródło
> (`@ngrx/operators/fesm2022/ngrx-operators.mjs`) pokazuje, że to dosłownie
> `tap({ next, complete }) + catchError(error => { observer.error(error); return EMPTY; }) +
> opcjonalny finalize`. Umieszczony PO `switchMap` (na zewnętrznym strumieniu rxMethod,
> zamiast wewnątrz projection function) psuje się TAK SAMO jak gołe `catchError` umieszczone
> w tym samym złym miejscu: po jednym błędzie `rxMethod` przestaje reagować na kolejne
> wywołania na zawsze (dowód: `search-broken-outer-catch.store.spec.ts` i
> `search-broken-outer-tap-response.store.spec.ts`).
>
> **Co `tapResponse()` NAPRAWDĘ daje**, gdy jest umieszczony poprawnie (wewnątrz
> `switchMap`, tam gdzie i tak powinien być `catchError`):
> 1. `error` jest WYMAGANY przez typ `TapResponseObserver<T, E>` — nie da się o nim
>    zapomnieć tak, jak można zapomnieć dorzucić osobny `catchError` do gołego `tap`.
> 2. `finalize` odpala się TAKŻE dla żądania ANULOWANEGO przez `switchMap` (nowsze
>    zapytanie nadpisało stare) — czego żaden ręczny `tap(next)`/`catchError(error)` nie
>    zrobi, bo anulowanie to ani `next`, ani `error`, tylko `unsubscribe` (teardown).
>    Dowód: `search.store.spec.ts`, test `finalize odpala się TAKŻE dla żądania
>    ANULOWANEGO przez switchMap`.

## Struktura

```
src/app/
  app.ts                                        -> host: <app-product-search />
  app.config.ts                                 -> provideHttpClient(withInterceptors([mockApiInterceptor]))
  products/
    product.model.ts                            -> interfejs Product
    products.api.ts                              -> ProductsApi.search() przez HttpClient
    mock-api.interceptor.ts                      -> backend w pamięci (tylko dla ng serve - testy go NIE używają)
    search-broken-outer-catch.store.ts           -> ANTY-PRZYKŁAD #1: tap/catchError PO switchMap
    search-broken-outer-tap-response.store.ts    -> ANTY-PRZYKŁAD #2: tapResponse() PO switchMap (ten sam bug)
    search.store.ts                              -> WERSJA IDIOMATYCZNA: tapResponse() WEWNĄTRZ switchMap + finalize
    product-search.ts / .html                    -> UI dla search.store.ts (wersji idiomatycznej)
    *.spec.ts                                    -> 9 testów (Vitest + jsdom + HttpTestingController)
```

Trzy warianty `search()` w jednym miejscu to CELOWE — to jest dosłownie teza artykułu:
pierwsze dwa wyglądają niewinnie podobnie, ale mają identyczny bug; trzeci różni się tylko
MIEJSCEM `tapResponse()` w pipe'ie (wewnątrz `switchMap`, nie po nim) i dodatkiem
`finalize`.

## Jak uruchomić od zera

```bash
cd code
npm ci               # lockfile w repo
npm run build        # = ng build
npm test             # = ng test --no-watch (Vitest + jsdom)
npm start            # = ng serve, http://localhost:4200/ (opcjonalnie, niezweryfikowane - zob. niżej)
```

`node_modules/`, `dist/` i `.angular/` są w `.gitignore`.

**Uwaga:** testy trzeba odpalać przez `ng test`/`npm test`, NIE przez gołe
`npx vitest run` — builder Angulara (`@angular/build:unit-test`) konfiguruje
`TestBed`/jsdom przed startem Vitest. Sprawdzone w tej sesji: gołe `npx vitest run` dało
**4 pliki testowe failed (0 testów)**, z błędem:

```text
Error: The service 'BrowserXhr' needs to be compiled using the JIT compiler, but
'@angular/compiler' is not available.
```

(Inny komunikat błędu niż w wydaniach #7/#9 tej rubryki dla tego samego pitfallu — co samo
potwierdza, że to cała kategoria błędów "środowisko Angulara nie jest zainicjalizowane",
nie jeden konkretny komunikat do zapamiętania.)

### ⚠️ Uwaga o wersji Node w TEJ sesji

Ta sesja miała zainstalowany Node **v22.14.0**. `@angular/cli`/`@angular/build` **22.2.1**
odmawiają startu poniżej `v22.22.3` (twardy check w `bin/ng.js`) — pierwsza próba
`ng build` kończyła się błędem:

```text
Node.js version v22.14.0 detected.
The Angular CLI requires a minimum Node.js version of v22.22.3 or v24.15.0 or v26.0.0.
```

Dokładnie ta sama sytuacja co w wydaniu #9 (02.10) tej rubryki. Sieć była dostępna tylko do
rejestru npm (nie do nodejs.org), więc nie dało się pobrać nowszego Node, a inne wersje
Node (np. przez `nvm`) nie były dostępne w tym środowisku. Zastosowane obejście,
WYŁĄCZNIE lokalnie: jednolinijkowa zmiana progu wersji w
`node_modules/@angular/cli/src/utilities/node-version.js`
(`'^22.22.3 || ^24.15.0 || >=26.0.0'` → `'^22.14.0 || ^24.15.0 || >=26.0.0'`) — **plik w
`node_modules/`, nigdy nie trafia do repo** (jest w `.gitignore`), nie jest częścią
dostarczanego kodu. Czytelnik z Node **v22.22.3+** nie potrzebuje tego obejścia w ogóle.
Po tej jednej zmianie realny `ng build`/`ng test` przeszły bez żadnego innego problemu
(zob. "Realna weryfikacja" niżej) — testowane DWA razy w tej sesji: raz po `npm install`,
raz po pełnym `npm ci` od zera (który resetuje `node_modules/`, więc obejście trzeba
nałożyć ponownie po każdym czystym `npm ci`).

## Fragment: trzy warianty `search()` - różnica to MIEJSCE i `finalize`

```typescript
// search-broken-outer-catch.store.ts - ANTY-PRZYKŁAD #1
switchMap((query) => api.search(query)),
tap((products) => patchState(store, { products, loading: false })),       // PO switchMap - BUG
catchError(() => { /* ... */ return of(null); }),                          // PO switchMap - BUG

// search-broken-outer-tap-response.store.ts - ANTY-PRZYKŁAD #2
switchMap((query) => api.search(query)),
tapResponse({ next: ..., error: ... }),                                    // PO switchMap - TEN SAM BUG

// search.store.ts - WERSJA IDIOMATYCZNA
switchMap((query) =>
  api.search(query).pipe(
    tapResponse({ next: ..., error: ..., finalize: () => patchState(store, (s) => ({ loading: false, pendingCount: s.pendingCount - 1 })) }),
  ),
),
```

## Realna weryfikacja (`npm ci` + `ng build` + `ng test`, czysty katalog, ta sesja)

```text
$ npm ci --no-audit --no-fund
added 283 packages in 11s

$ npm run build
main-675XAML6.js    | main    | 148.75 kB | 43.94 kB
styles-5INURTSO.css | styles  |   0 bytes |  0 bytes
Application bundle generation complete. [5.764 seconds]

$ npm test
 Test Files  4 passed (4)
      Tests  9 passed (9)
   Duration  3.05s
```

9 testów w 4 plikach: `search-broken-outer-catch.store.spec.ts` (2 — bug przy błędzie +
kontrola bez błędu), `search-broken-outer-tap-response.store.spec.ts` (2 — ten sam bug z
`tapResponse()` źle umieszczonym + kontrola), `search.store.spec.ts` (4 — debounce+sukces z
`pendingCount`, błąd WEWNĄTRZ `switchMap` nie zabija strumienia, `finalize` na żądaniu
anulowanym przez `switchMap`, `isEmpty`), `app.spec.ts` (1 — komponent się renderuje).

**Sanity-check wykonany w tej sesji** (żeby upewnić się, że testy "broken" faktycznie
wykrywają bug, a nie przechodzą przypadkiem): tymczasowo zamieniłem w
`search-broken-outer-catch.store.spec.ts` asercję `http.expectNone(...)` na
`http.expectOne(...)` i odpaliłem ponownie — test **failował** z komunikatem
`Expected one matching request for criteria "Match URL: /api/products?q=mysz", found none.`
Potwierdza to, że żądanie faktycznie nie wychodzi po błędzie — nie jest to fałszywie
zielony test. Zmiana została od razu wycofana, nie jest częścią dostarczanego kodu.

Wypróbuj ręcznie (jeśli masz `ng serve` pod ręką — ja nie miałem, zob. artykuł): wpisz
`boom` w pole szukania — zobaczysz błąd 500 (symulowany przez `mock-api.interceptor.ts`),
wpisz potem np. `klawiatura` — w wersji `search.store.ts` (tej, która jest podłączona do
UI) wyszukiwanie dalej działa, bo `tapResponse()` siedzi wewnątrz `switchMap`.

Niezweryfikowane: `ng serve`/przeglądarka, `validateHttp`, SSR/hydration, `mapResponse()`
w kontekście `@ngrx/effects`.
