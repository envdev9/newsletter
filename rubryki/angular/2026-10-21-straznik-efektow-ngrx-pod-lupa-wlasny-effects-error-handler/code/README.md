# Kod do wydania Angular z 21.10.2026 — własny `EFFECTS_ERROR_HANDLER` w NgRx Effects

Pełny artykuł: [`../ARTICLE.md`](../ARTICLE.md).

Wymagania: **Node.js** (zweryfikowane na v22.14.0 — zob. "Uwaga o wersji Node") i **npm** (10.9.2).
Wersje: `@angular/*` **22.2.3**, `@ngrx/store`/`effects`/`operators` **22.0.1**, TypeScript **6.0.3**, `vitest` **5.0.5**
(jsdom 30.1.2), `rxjs` 7.8.2.

## Fragment prasówki, którego dotyczy ten kod

> Wznawianiem efektów NgRx rządzi funkcja w tokenie `EFFECTS_ERROR_HANDLER`. Domyślna zgłasza do `ErrorHandler` 10 błędów,
> a 11. znika po cichu (efekt umiera bez śladu). Własna polityka (`createErrorPolicy`) zgłasza każdy błąd, daje sygnał
> `onDied` i opcjonalny backoff — ale wznowienie to nowa subskrypcja (stan w `scan` zerowany), a w oknie backoffu akcje
> przepadają. `useEffectsErrorHandler: false` zabija pojedynczy efekt po pierwszym błędzie; dla efektu `dispatch: false`
> błąd nie jest materializowany i zabija także efekty-sąsiadów, trafiając do globalnego "unhandled" RxJS, a nie do `ErrorHandler`.

## Struktura

```
src/app/
  app.ts, app.config.ts                    -> host, provideStore + provideEffects + własny EFFECTS_ERROR_HANDLER
  orders/orders.store.ts                   -> akcje, reducer, efekty: safeSearch, leakySearch, leakyNoGuard, pinger
  orders/effects-error-policy.ts           -> createErrorPolicy (retry, backoff, onDied)
  orders/effects-error-policy.spec.ts      -> 13 testów (HttpTestingController, fake timery)
```

## Jak uruchomić od zera

```bash
cd code
npm install                  # lub npm ci (jest package-lock.json)
npm run verify               # = ng build + ng test --no-watch
npm exec -- ng test --no-watch --reporters verbose   # pokazuje linie "MEASURE ..."
```

NIE używaj gołego `npx vitest run` (brak `TestBed.initTestEnvironment()`). `node_modules/`, `dist/`, `.angular/` są w
`.gitignore`. `npm start` (`ng serve`) — niezweryfikowane (brak przeglądarki).

### Uwaga o wersji Node

Sesja miała Node **v22.14.0**, a Angular CLI 22.2.3 wymaga `>=22.22.3`. Obejście (tylko lokalne, w `node_modules/`, nie
trafia do repo): w `node_modules/@angular/cli/src/utilities/node-version.js` zmiana stałej `SUPPORTED_NODE_VERSIONS`
z `'^22.22.3 || ...'` na `'^22.14.0 || ...'`; powtórz po każdym `npm install`. `package.json` przypina `jsdom` 30.1.2 i
`overrides.undici` 8.11.2. Przy Node >= 22.22.3 oba obejścia są zbędne.

## Realna weryfikacja (ta sesja)

```text
$ npm run verify
main-M7JRNQN6.js    | main          | 152.73 kB | 44.65 kB
Application bundle generation complete. [6.263 seconds]
 Test Files  1 passed (1)
      Tests  13 passed (13)
```

Wybrane linie `MEASURE`:

```text
default-limit:         {"lastWithRequest":11,"handledAfter":[1,2,3,4,5,6,7,8,9,10,10]}
custom-limit:          {"lastWithRequest":4,"handledAfter":[1,2,3,4],"died":1}
state-reset:           {"first":"x#1","afterError":"y#1","next":"z#2","handled":1}
backoff-window:        {"requestsInWindow":0,"justBefore":0,"afterWindow":1,"qAfter":"po-oknie#1","handled":1}
no-guard:              {"handled":0,"secondRequests":0}
neighbour-dispatching: {"pongsBefore":1,"pongsAfter":1,"handled":0}
neighbour-dispatch-false: {"pongsBefore":1,"pongsAfter":0,"errorHandler":0,"unhandledByRxjs":["skutek uboczny padl"]}
neighbour-separate-provide: {"pongsBefore":1,"pongsAfter":0,"unhandled":1}
```

Test mutacyjny: wyciszenie zgłoszenia ostatniego błędu w `createErrorPolicy` → padły 2 testy; po przywróceniu 13/13.

Niezweryfikowane: `ng serve`/przeglądarka, zachowanie `window.onerror` w realnej przeglądarce, feature effects w lazy module,
`ngrxOnRunEffects`, backoff z jitterem.
