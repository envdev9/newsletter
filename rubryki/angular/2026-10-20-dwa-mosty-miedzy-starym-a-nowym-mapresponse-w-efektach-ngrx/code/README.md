# Kod do wydania Angular z 20.10.2026 — `mapResponse()` w efektach NgRx i CVA obok Signal Forms

Pełny artykuł: [`../ARTICLE.md`](../ARTICLE.md).

Wymagania: **Node.js** (zweryfikowane na v22.14.0 — zob. "Uwaga o wersji Node") i **npm** (10.9.2).
Wersje: `@angular/*` **22.2.3**, `@ngrx/store`/`effects`/`operators` **22.0.1**, TypeScript **6.0.3**, `vitest` **5.0.5**
(jsdom 30.1.2), `rxjs` 7.8.2.

## Fragment prasówki, którego dotyczy ten kod

> `mapResponse()` z `@ngrx/operators` to `map` + `catchError(of(...))` — w efekcie NgRx stawiasz go **wewnątrz** `switchMap`.
> Na zewnątrz efekt po 1. błędzie kończy się po cichu (0 żądań przy kolejnym wyszukiwaniu, `ErrorHandler` milczy);
> bez obsługi błędu NgRx wznawia efekt max 10 razy, a reducer zostaje w `loading: true`. Wyjątek w `next` trafia do `error`
> jako zwykły `Error`. Stary `ControlValueAccessor` działa pod `ngModel`, `[formControl]` i `[formField]`, ale z inną kolejnością
> wywołań; `ngModel` + `[formField]` na jednym elemencie to cicha porażka (wygrywa `ngModel`). Mosty: `compatForm`
> (stary `FormControl` w modelu) i `SignalFormControl` (nowe pole w `FormGroup`) z `@angular/forms/signals/compat`.

## Struktura

```
src/app/
  app.ts, app.config.ts          -> host, provideStore + provideEffects
  orders/orders.store.ts         -> akcje, reducer, OrdersApi, efekt searchOrders z mapResponse
  orders/orders.effects.spec.ts  -> 9 testów efektu (warianty zły/dobry, limit wznowień)
  profile/star-rating.ts         -> klasyczny ControlValueAccessor (rejestruje kolejność wywołań)
  profile/profile-form.ts        -> compatForm: FormControl + [formField]
  profile/interop.spec.ts        -> 4 testy interop (ngModel/formControl/formField, compatForm, SignalFormControl)
```

## Jak uruchomić od zera

```bash
cd code
npm install                  # lub npm ci (jest package-lock.json)
npm run verify               # = ng build + ng test --no-watch
npm exec -- ng test --no-watch --reporters verbose   # pokazuje linie "MEASURE ..."
```

NIE używaj gołego `npx vitest run` (brak `TestBed.initTestEnvironment()`). `node_modules/`, `dist/`, `.angular/` są w
`.gitignore`. `npm start` (`ng serve`) — niezweryfikowane (brak przeglądarki; próba sprawdzenia HTTP przez `curl` została
odrzucona przez system uprawnień).

### Uwaga o wersji Node

Sesja miała Node **v22.14.0**, a Angular CLI 22.2.3 wymaga `>=22.22.3`. Obejście (tylko lokalne, w `node_modules/`, nie
trafia do repo): w `node_modules/@angular/cli/src/utilities/node-version.js` zmiana stałej `SUPPORTED_NODE_VERSIONS`
z `'^22.22.3 || ...'` na `'^22.14.0 || ...'`; powtórz po każdym `npm install`. `package.json` przypina `jsdom` 30.1.2 i
`overrides.undici` 8.11.2. Przy Node >= 22.22.3 oba obejścia są zbędne.

## Realna weryfikacja (ta sesja)

```text
$ npm run verify
main-6T6GTRKT.js    | main          | 251.49 kB | 68.50 kB
Application bundle generation complete. [7.304 seconds]
 Test Files  2 passed (2)
      Tests  13 passed (13)
```

Wybrane linie `MEASURE`:

```text
error-then-ok:  actions ["[Orders] search","[Orders] search failure","[Orders] search","[Orders] search success"], errorHandler []
outside:        {"afterFirst":{"error":"HTTP 500",...},"secondRequests":0,"errorHandler":[]}
no-handling:    {"stuck":{"loading":true,...},"handled":1,"secondRequests":1}
retry-limit:    {"lastQueryThatSentRequest":11,"handledAfter":[1,2,3,4,5,6,7,8,9,10,10]}
next-throws:    {"state":{"error":"JS: mapper wybuchł"},...}
cva-calls:      ngModel [writeValue(null),setDisabledState(false),registerOnChange,registerOnTouched,writeValue(2)]
both:           modelAfterClick {"rating":2}, legacyAfterClick 5, warns 0, errors 0
compat-after-click: {"control":4,"fieldValue":4,"errors":0,"dirty":true,"touched":false}
group-after-input:  {"valid":true,"value":{"name":"Ola","rating":4},...}
```

Test mutacyjny: `mapResponse` przeniesiony na zewnątrz `switchMap` w `searchOrders` → padły 2 testy; po przywróceniu 13/13.

Niezweryfikowane: `ng serve`/przeglądarka, `withEventReplay()`, `mapResponse()` przy wielu emisjach (tylko z kodu),
własny `EFFECTS_ERROR_HANDLER`, `NG_VALIDATORS`/`NG_ASYNC_VALIDATORS` pod `compatForm`, `aria-*`, SSR.
