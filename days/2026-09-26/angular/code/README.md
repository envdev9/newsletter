# Kod do wydania Angular z 26.09.2026 — `linkedSignal`, `httpResource`, signal store + `rxMethod`, `switchMap` vs `exhaustMap`

Pełny artykuł: [`../ARTICLE.md`](../ARTICLE.md). Poniżej ten sam kod + jak go odpalić.

Wymagania: **Node.js 20+** (weryfikowane na v22.23.3) i **npm**. Wersje: `@angular/core`
**22.2.0**, `@ngrx/signals` **22.0.1**, `rxjs` **7.8.2**, `vitest` **4.1.11** (jsdom, bez przeglądarki).

## Fragment prasówki, którego dotyczy ten kod

> **`linkedSignal` z pamięcią.** Forma `linkedSignal({ source, computation })` daje
> `computation` dostęp do poprzedniej wartości: przy zmianie listy zostaw zaznaczenie,
> jeśli element nadal istnieje, inaczej wybierz pierwszy. Użytkownik nadal może
> nadpisać wartość przez `set()`.
>
> **`httpResource`** (`@publicApi 22.0` w zainstalowanej wersji) to reaktywne żądanie GET:
> URL jest funkcją sygnałów, a wynik to sygnały `value()`, `status()`, `error()`,
> `hasValue()`. Zmiana parametru anuluje poprzednie żądanie i wysyła nowe; zwrócenie
> `undefined` oznacza "nie ładuj". Tylko do odczytów - mutacje przez `HttpClient`/`rxMethod`.
>
> **Signal store + HTTP.** `rxMethod<T>(pipe(...))` w `withMethods` to metoda store'a
> zbudowana na potoku RxJS: `debounceTime` → `distinctUntilChanged` → `switchMap`, a
> `catchError` musi być **wewnątrz** `switchMap`, żeby błąd nie ubił całego strumienia.
>
> **`switchMap` vs `exhaustMap`.** Odczyt → `switchMap` (nowe anuluje stare).
> Mutacja → `exhaustMap` (nowe jest ignorowane, dopóki poprzednie trwa) albo
> `concatMap` (kolejka). Prawdziwą ochronę przed duplikatami daje idempotentny endpoint.

## Struktura projektu

```
src/app/
  app.config.ts                      -> provideHttpClient(withInterceptors([mockApiInterceptor]))
  app.ts                             -> root
  products/
    product.model.ts                 -> typy
    mock-api.interceptor.ts          -> backend w pamięci (interceptor HttpClient; q=boom -> 500)
    products.api.ts                  -> cienki klient HTTP
    products.store.ts                -> signalStore + rxMethod (search: switchMap, placeOrder: exhaustMap)
    product-browser.ts/.html         -> linkedSignal (zaznaczenie) + httpResource (szczegóły)
    products.store.spec.ts           -> 5 testów store'a (HttpTestingController, fake timers)
    product-browser.spec.ts          -> 3 testy komponentu (linkedSignal + httpResource)
```

## Jak uruchomić od zera

```bash
cd code
npm ci               # lockfile jest w repo (zalecane)
npm run build        # = ng build, wynik w dist/code/
npm test             # = ng test --no-watch (Vitest + jsdom)
npm start            # = ng serve, http://localhost:4200/ (opcjonalnie)
```

Uwaga: `npm install` **bez** lockfile'a wywalił się w środowisku autora błędem
`Cannot read properties of null (reading 'edgesOut')`; lockfile powstał przez
`npm install --legacy-peer-deps`. Zwykłe `npm ci` z tym lockfile'em działa.
`node_modules/`, `dist/` i `.angular/` są w `.gitignore`.

## Realna weryfikacja

```text
$ npm ci --no-audit --no-fund
added 290 packages in 13s

$ npm run build
Initial chunk files | Names         |  Raw size | Estimated transfer size
main-P7V4R2DZ.js    | main          | 167.70 kB |                49.48 kB
styles-YDSRV2IW.css | styles        | 186 bytes |               186 bytes

                    | Initial total | 167.89 kB |                49.67 kB

Application bundle generation complete. [5.903 seconds]

$ npm test
 Test Files  2 passed (2)
      Tests  8 passed (8)
   Duration  2.44s
```

Niezweryfikowane: uruchomienie w przeglądarce (`ng serve`), `resource()` z własnym
loaderem i `rxResource` (opisane tylko na podstawie typów), `tapResponse` z `@ngrx/operators`.
