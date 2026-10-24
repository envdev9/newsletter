<div align="center">

# 📰 TECH PRASÓWKA
### Wydanie #28 rubryki Angular — 21 października 2026

![Angular](https://img.shields.io/badge/Angular-DD0031?style=for-the-badge&logo=angular&logoColor=white)
![NgRx Effects](https://img.shields.io/badge/NgRx-EFFECTS__ERROR__HANDLER-7B1FA2?style=for-the-badge)
![Odporność](https://img.shields.io/badge/Resilience-retry_%2B_backoff-2E7D32?style=for-the-badge)

## Strażnik efektów NgRx pod lupą: własny `EFFECTS_ERROR_HANDLER`, backoff i pułapka `useEffectsErrorHandler: false`

</div>

---

> _"Dziesięć błędów zgłoszonych, jedenasty zniknął bez śladu."_
> — wniosek z dzisiejszego testu, nie cytat z dokumentacji.

W #27 zmierzyłem, że efekt NgRx bez własnej obsługi błędu jest wznawiany maksymalnie 10 razy. Zostały trzy pytania: **kto
to robi**, **czy można to zmienić** i **co się stanie, gdy strażnika wyłączę**. Dla .NET developera: to jak polityka
ponowień (Polly / `UseMessageRetry` w MassTransit) wpięta globalnie w pętlę konsumenta wiadomości — tyle że tu masz
do dyspozycji jedną funkcję i dwie pułapki.

| | |
|---|---|
| 🧱 Stack | `@angular/*` **22.2.3**, `@ngrx/store`/`effects`/`operators` **22.0.1**, TypeScript **6.0.3**, `rxjs` 7.8.2 |
| 🖥️ Środowisko | Node **v22.14.0**, npm 10.9.2, Vitest **5.0.5** + jsdom **30.1.2** (bez przeglądarki) |
| ✅ Weryfikacja | `ng build` OK (6,3 s, 152,73 kB), `ng test` **13/13** (1 plik) + test mutacyjny (2 padają) |
| 📦 Kod | [`code/`](code/) — własna polityka błędów, 5 efektów testowych, `HttpTestingController` + fake timery |

---

## 1️⃣ Kto wznawia efekt: token `EFFECTS_ERROR_HANDLER`

### 🎣 Dlaczego to ważne

Wznawianie efektów to nie magia frameworka, tylko **zwykła funkcja w tokenie DI**, którą możesz podmienić. Z
kompilowanego źródła (`ngrx-effects.mjs`) i typów:

```typescript
type EffectsErrorHandler = <T extends Action>(observable$: Observable<T>, errorHandler: ErrorHandler) => Observable<T>;
// domyślna implementacja (skrót):
catchError((error) => {
  errorHandler.handleError(error);
  if (retryAttemptLeft <= 1) return observable$;          // ostatnia próba: BEZ catchError
  return defaultEffectsErrorHandler(observable$, errorHandler, retryAttemptLeft - 1);
})
```

Zwróć uwagę na ostatnią próbę: ponowna subskrypcja jest **bez** `catchError`, więc 11. błąd wypływa dalej — a
`EffectSources` odfiltrowuje powiadomienia inne niż `next` (`filter(notification.kind === 'N')`). Efekt: zmierzone na
efekcie bez obsługi błędu w `switchMap`:

```text
MEASURE default-limit: {"lastWithRequest":11,"handledAfter":[1,2,3,4,5,6,7,8,9,10,10]}
```

Żądania 1–11 wychodzą, ale `ErrorHandler` dostaje **10** wpisów: 11. błąd, po którym efekt umiera na stałe, nie zostawia
żadnego śladu. W produkcji to dokładnie ten rodzaj awarii, który odkrywa się po tygodniu ("dlaczego wyszukiwarka
przestała działać?").

### Własna polityka — 30 linii

```typescript
export function createErrorPolicy(options: { maxRetries: number; baseDelayMs: number; onDied: (e: unknown) => void }): EffectsErrorHandler {
  return function handler<T extends Action>(source$: Observable<T>, errorHandler: ErrorHandler, attempt = 0): Observable<T> {
    return source$.pipe(
      catchError((error) => {
        errorHandler.handleError(error);                       // KAŻDY błąd zgłoszony
        if (attempt >= options.maxRetries) { options.onDied(error); return EMPTY; }  // jawny sygnał śmierci
        if (options.baseDelayMs === 0) return handler(source$, errorHandler, attempt + 1);
        return timer(options.baseDelayMs * 2 ** attempt).pipe(switchMap(() => handler(source$, errorHandler, attempt + 1)));
      }),
    );
  };
}
// rejestracja:
{ provide: EFFECTS_ERROR_HANDLER, useValue: createErrorPolicy({ maxRetries: 3, baseDelayMs: 0, onDied: reportToMonitoring }) }
```

```text
MEASURE custom-limit: {"lastWithRequest":4,"handledAfter":[1,2,3,4],"died":1}
MEASURE pure-policy:  {"subs":3,"handledErrors":["blad 1","blad 2","blad 3"],"died":1,"completed":true}
```

`maxRetries: 3` = oryginał + 3 ponowienia (4 żądania), **wszystkie 4 błędy zgłoszone**, `onDied` wywołane raz. Test
mutacyjny: wyciszyłem zgłoszenie ostatniego błędu (powrót do zachowania domyślnego) — padły **2** testy; po przywróceniu 13/13.

---

## 2️⃣ Resubskrypcja zeruje stan i ma "okno głuchoty"

### 🎣 Dlaczego to ważne

Wznowienie to **nowa subskrypcja całego łańcucha** `actions$.pipe(...)`. Dwie konsekwencje, obie zmierzone.

**(a) Stan wewnątrz efektu (`scan`, `bufferCount`, …) jest zerowany.** Efekt numeruje wywołania przez `scan`; numer
widać w parametrze `q` żądania:

```text
MEASURE state-reset: {"first":"x#1","afterError":"y#1","next":"z#2","handled":1}
```

Po błędzie licznik wraca do 1 (gdyby efekt trwał dalej, byłoby `y#2`). Jeśli w efekcie trzymasz "ostatni znany cursor" w
`scan`, po awarii zaczynasz od zera.

**(b) Backoff = okno, w którym efekt nikogo nie słucha.** `Actions` to gorący strumień (jak `Subject`) — bez
`replay`. Przy `baseDelayMs: 1000`:

```text
MEASURE backoff-window:      {"requestsInWindow":0,"justBefore":0,"afterWindow":1,"qAfter":"po-oknie#1","handled":1}
MEASURE backoff-exponential: {"early":0,"ok":1}
```

Akcje `search` wysłane w trakcie oczekiwania (także 1 ms przed końcem) **przepadają** — nie wychodzi żadne żądanie i nikt
o tym nie wie. Po upływie okna efekt działa ponownie; drugie okno trwa 2000 ms (1 s × 2¹). Czyli backoff w tym miejscu
kupuje oddech dla backendu kosztem utraconych akcji; dla "wyszukiwania na bieżąco" to zwykle OK, dla "zapisz zamówienie"
— nie. Do tego drugiego użyj ponowień **wewnątrz** `switchMap`/`concatMap` przy samym wywołaniu HTTP (tam akcja jest już
przechwycona).

**Dla .NET developera:** to różnica między retry w middleware konsumenta (wiadomość czeka w kolejce) a restartem całego
hosta konsumenta (wiadomości z okna restartu giną, bo nie ma brokera).

---

## 3️⃣ ⚠️ `useEffectsErrorHandler: false` — kiedy wyłączenie strażnika jest groźniejsze, niż wygląda

### 🎣 Dlaczego to ważne

`createEffect(..., { useEffectsErrorHandler: false })` (typ `EffectConfig`: "czy efekt jest wznawiany po błędzie")
wyłącza strażnika dla jednego efektu. Zmierzone:

```text
MEASURE no-guard: {"handled":0,"secondRequests":0}
```

Po pierwszym błędzie: zero wpisów w `ErrorHandler`, zero kolejnych żądań. Efekt zniknął **po cichu** — ten sam wzorzec,
co w całej serii. Dalej robi się ciekawie, bo zasięg szkody zależy od jednej opcji, `dispatch`. Z kodu `mergeEffects`:
efekt z `dispatch: true` jest przepuszczany przez `materialize()` (błąd staje się powiadomieniem, które potem ktoś
odfiltrowuje), a z `dispatch: false` — tylko `ignoreElements()`. Skutek:

```text
MEASURE neighbour-guarded:         {"pongsAfterNeighbourFailure":1,"handled":1}
MEASURE neighbour-dispatching:     {"pongsBefore":1,"pongsAfter":1,"handled":0}
MEASURE neighbour-dispatch-false:  {"pongsBefore":1,"pongsAfter":0,"errorHandler":0,"unhandledByRxjs":["skutek uboczny padl"]}
MEASURE neighbour-separate-provide:{"pongsBefore":1,"pongsAfter":0,"unhandled":1}
```

- Efekt z włączonym strażnikiem: awaria sąsiada nie ma znaczenia.
- Efekt `dispatch: true` **bez** strażnika: sam umiera, sąsiad w tym samym `provideEffects()` żyje.
- Efekt `dispatch: false` **bez** strażnika (np. czysto logujący/analityczny): błąd **zabija sąsiadów** w tym samym
  `provideEffects()` — i, co zmierzyłem w ostatnim teście, także efekt zarejestrowany w **osobnym** `provideEffects()`.
  Błąd nie trafia do `ErrorHandler` Angulara, tylko do globalnego "unhandled error" RxJS (domyślnie: rzut w
  `setTimeout`, czyli do `window.onerror` / `provideBrowserGlobalErrorListeners()`).

To wniosek z testu na jednym układzie (jeden `Store`, jeden `EffectsRunner`); **nie sprawdzałem**, czy każda inna
konfiguracja (np. feature effects w lazy-loadowanym module) zachowa się tak samo — z kodu `toActions()` wynika, że
wszystkie źródła idą przez jeden strumień subskrybowany przez `Store`, więc zasięg jest szeroki.

Dodatkowo: efekt `dispatch: false` **z włączonym** strażnikiem działa poprawnie (`MEASURE dispatch-false:
{"subscriptions":2,"handled":["logger padl"]}`) — strażnik jest nakładany przed `ignoreElements()`.

**Reguła:** `useEffectsErrorHandler: false` stosuj tylko razem z własnym `catchError` w efekcie. Każdy efekt, który
łapie błąd wewnątrz (jak `safeSearch` z `mapResponse` z #27), w ogóle nie dotyka strażnika:

```text
MEASURE safe: {"actions":["[Orders] search","[Orders] search failure","[Orders] search","[Orders] search success"],"handled":0}
```

---

## 4️⃣ Weryfikacja — prawdziwy output

Obejście środowiskowe jak w #9–#27: Node v22.14.0, a CLI 22.2.3 wymaga `>=22.22.3`. Lokalna edycja stałej
`SUPPORTED_NODE_VERSIONS` w `node_modules/@angular/cli/src/utilities/node-version.js` (poza repo; do powtórzenia po
`npm install`), oraz `jsdom` 30.1.2 + `overrides.undici` 8.11.2 w `package.json`.

```text
$ npm run verify
> ng build
main-M7JRNQN6.js    | main          | 152.73 kB | 44.65 kB
Application bundle generation complete. [6.263 seconds]
> ng test --no-watch
 Test Files  1 passed (1)
      Tests  13 passed (13)
```

### Droga do wyniku — co się nie zgadzało

Dwie moje hipotezy obaliły się w trakcie: (1) że efekt bez strażnika zawsze zabija sąsiadów — nie, tylko `dispatch: false`;
(2) że `dispatch: false` błąd trafi do `ErrorHandler` — nie, trafia do globalnego handlera RxJS (przechwytywałem go przez
`rxjs.config.onUnhandledError`, i musiałem poczekać na kolejne makrozadanie, bo RxJS raportuje przez `setTimeout(0)`).

### ⚠️ Co jest niezweryfikowane (wprost)

- **`ng serve` w przeglądarce**: brak przeglądarki, nie uruchamiałem. Aplikacja zbudowana i przetestowana w jsdom.
- Zachowanie w realnej przeglądarce przy błędzie unhandled RxJS (`window.onerror`) — wniosek z kodu RxJS, nie z testu.
- Feature effects w lazy-loadowanym module / `provideEffects()` w trasie; kolejność wielu `EFFECTS_ERROR_HANDLER`.
- `ngrxOnRunEffects` jako alternatywna warstwa obsługi błędów (klasy efektów).
- `withEventReplay()`, `@defer (hydrate on …)`, `NG_VALIDATORS` pod `compatForm` — z "Następnego poziomu" #27, nie ruszane.
- Backoff z jitterem i anulowaniem przy `ngOnDestroy` aplikacji; test z `vi.useFakeTimers` pokrywa tylko czas, nie rzeczywiste opóźnienia sieci.

---

## 🧭 Do zapamiętania

| Potrzeba | Co zrobić |
|---|---|
| Zmienić politykę wznowień | Podmień token `EFFECTS_ERROR_HANDLER` (`createErrorPolicy`) |
| Domyślny strażnik | 10 błędów zgłoszonych, 11. znika po cichu, efekt martwy |
| Wznowienie efektu | Nowa subskrypcja: `scan`/stan w efekcie zerowany |
| Backoff w strażniku | Akcje w oknie oczekiwania przepadają — nie dla zapisów |
| `useEffectsErrorHandler: false` | Tylko z własnym `catchError`; `dispatch: false` + `false` zabija sąsiadów |
| Krytyczna operacja (zapis) | Obsłuż błąd wewnątrz `switchMap`/`concatMap`, strażnik traktuj jak siatkę bezpieczeństwa |

**Następnym razem (propozycja):** `withEventReplay()` i incremental hydration (`@defer (hydrate on …)`),
`NG_VALIDATORS`/`NG_ASYNC_VALIDATORS` pod `compatForm`, `ngrxOnRunEffects`, `ng serve` w przeglądarce (jeśli będzie
dostępna).

---

## 📎 Jak uruchomić

Zobacz [`code/README.md`](code/README.md).

---

<div align="center">

[← wszystkie artykuły: 🅰️ Angular](../README.md) · [spis rubryk](../../../README.md)

</div>
