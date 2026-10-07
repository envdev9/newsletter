# Kod do wydania Angular z 07.10.2026 — SignalStore Events: zdarzenia, reduktory, efekty

Pełny artykuł: [`../ARTICLE.md`](../ARTICLE.md).

Wymagania: **Node.js** (zweryfikowane na v22.14.0 — zob. "Uwaga o wersji Node") i **npm**
(10.9.2). Wersje: `@angular/*` **22.2.1**, `@ngrx/signals` **22.0.1** (`/events`),
TypeScript **6.0.3**, `vitest` **5.0.3** (jsdom), `rxjs` 7.8.x.

## Fragment prasówki, którego dotyczy ten kod

> Plugin `@ngrx/signals/events` odwraca kierunek zależności: komponent mówi „co się stało"
> (`injectDispatch(tasksPageEvents).added('x')`), a store'y zapisują się na zdarzenia —
> `withReducer(on(...))` zmienia stan (czysto, synchronicznie, przed efektami),
> `withEventHandlers` robi I/O i zwraca nowe zdarzenia. Zmierzone: dwa store'y reagują na to
> samo zdarzenie bez wzajemnych importów; zdarzenie zwrócone z efektu czeka na resztę
> handlerów (queueScheduler); efekt bez `catchError` wewnątrz `switchMap` umiera po pierwszym
> błędzie, a reduktor rzucający wyjątek przestaje zmieniać stan bez błędu w UI (efekty żyją);
> store jest leniwy, a strumień bez replay, więc zdarzenia sprzed pierwszego `inject()`
> przepadają; `Dispatcher`/`Events` są `providedIn: 'platform'`, zasięg lokalny daje
> `provideDispatcher()`. JSDoc w paczce wciąż pokazuje nieistniejące `withEffects`.

## Struktura

```
src/app/
  app.ts, app.config.ts          -> host
  tasks/
    tasks.events.ts              -> eventGroup: tasksPageEvents, tasksApiEvents
    tasks.api.ts                 -> fałszywe API w pamięci (200 ms, failNext)
    tasks.store.ts               -> TasksStore: withReducer + withEventHandlers (switchMap + catchError)
    activity-log.store.ts        -> store słuchający wszystkich zdarzeń, bez importu TasksStore
    tasks-page.ts                -> komponent z injectDispatch()
    tasks.store.spec.ts          -> 5 testów obu store'ów
    events.mechanics.spec.ts     -> 8 pomiarów mechaniki na gołych store'ach
    tasks-page.spec.ts           -> 1 test DOM
  app.spec.ts                    -> 1 test
```

## Jak uruchomić od zera

```bash
cd code
npm ci               # lockfile w repo
npm run build        # = ng build
npm test             # = ng test --no-watch (Vitest + jsdom) - NIE gołe `npx vitest run`
npm start            # = ng serve, http://localhost:4200/ (niezweryfikowane - brak przeglądarki)
```

`node_modules/`, `dist/`, `.angular/` są w `.gitignore`.

### Uwaga o wersji Node

Sesja miała Node **v22.14.0**, a Angular CLI 22.2.1 wymaga `>=22.22.3`. Obejście (tylko lokalne,
plik w `node_modules/`, nie trafia do repo): w
`node_modules/@angular/cli/src/utilities/node-version.js` zmiana `'^22.22.3 || ...'` na
`'^22.14.0 || ...'`; trzeba je powtórzyć po każdym `npm ci`. Przy Node >= 22.22.3 niepotrzebne.

## Realna weryfikacja (ta sesja)

```text
$ npm ci --no-audit --no-fund
added 282 packages in 10s

$ npm run build
main-6JU3GB4T.js    | main   | 128.12 kB | 38.51 kB
Application bundle generation complete. [5.583 seconds]

$ npm test
 Test Files  4 passed (4)
      Tests  15 passed (15)
```

Test mutacyjny: przeniesienie `catchError` na zewnątrz `switchMap` w `TasksStore` → padł test
„kolejne opened znów działa" (`expected +0 to be 2`). Zmiana wycofana.

Niezweryfikowane: `ng serve`/przeglądarka, `mapResponse()` z `@ngrx/operators`, `toScope`/
`mapToScope`, SSR/hydration, Redux DevTools.
