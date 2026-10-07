<div align="center">

# 📰 TECH PRASÓWKA
### Wydanie #14 rubryki Angular — 7 października 2026

![Angular](https://img.shields.io/badge/Angular-DD0031?style=for-the-badge&logo=angular&logoColor=white)
![NgRx SignalStore Events](https://img.shields.io/badge/NgRx_Signals-Events-6A1B9A?style=for-the-badge)

## SignalStore Events: zdarzenia, reduktory i efekty bez Redux-owego boilerplate'u — i pięć rzeczy, które zmierzyłem

</div>

---

> _"Receives events before the `Events` service and is primarily used for handling state transitions."_
> — komentarz nad `ReducerEvents` w `@ngrx/signals/events` 22.0.1. Jedno zdanie, które
> tłumaczy, dlaczego efekt zawsze widzi już zaktualizowany stan. Resztę mechaniki
> przeczytałem w skompilowanym źródle i sprawdziłem testami.

Do tej pory w tej rubryce store był zbiorem **metod**: komponent woła `store.addItem()`,
a metoda robi `patchState` albo odpala `rxMethod` (wydania #1, #3, #12). To działa, dopóki
jeden store nie musi zareagować na to, co zrobił inny — wtedy zaczynają się wstrzykiwania
store'a do store'a. Dziś poziom wyżej: **plugin zdarzeń** `@ngrx/signals/events` — komponent
mówi „co się stało" (`opened`, `added`), a store'y same decydują, co z tym zrobić. Dla .NET
developera: różnica między bezpośrednim wywołaniem serwisu a `IMediator.Publish` z
`INotificationHandler<T>` — wielu odbiorców jednego zdarzenia, żaden nie zna nadawcy.

| | |
|---|---|
| 🧱 Stack | `@angular/*` **22.2.1**, `@ngrx/signals` **22.0.1** (`/events`), TypeScript **6.0.3**, `rxjs` 7.8.x |
| 🖥️ Środowisko | Node **v22.14.0**, npm 10.9.2, Vitest **5.0.3** + jsdom, fake timery |
| ✅ Weryfikacja | `npm ci` (282 pakiety, 10 s), `ng build` OK (5,6 s, 128,12 kB), `ng test` **15/15** (4 pliki) + test mutacyjny |
| 📦 Kod | [`code/`](code/) — lista zadań: `TasksStore` + niezależny `ActivityLogStore` na tych samych zdarzeniach, plus 8 pomiarów mechaniki na gołych store'ach |

**Plan:** (1) cztery klocki API, (2) działający przykład dwóch store'ów na jednym
strumieniu, (3) pięć haczyków zmierzonych, (4) weryfikacja i czego NIE sprawdziłem.

---

## 1️⃣ Cztery klocki

### 🎣 Dlaczego to ważne

W dużej aplikacji najtrudniejsze nie jest „jak zapisać stan", tylko „kto ma zareagować, gdy
użytkownik kliknął X". Gdy odpowiedź brzmi „koszyk, licznik w nagłówku i analityka", metody
wołające się nawzajem robią z store'ów graf zależności. Zdarzenia odwracają kierunek: jest
jeden strumień, a każdy store zapisuje się na to, co go dotyczy.

```typescript
// 1. Zdarzenia - nazwy w czasie przeszłym, "co się stało"
export const tasksPageEvents = eventGroup({
  source: 'Tasks Page',
  events: { opened: type<void>(), added: type<string>(), toggled: type<number>() },
});

// 2. Reduktory: (zdarzenie, stan) -> patch. Czyste, bez I/O.
withReducer(
  on(tasksPageEvents.opened, () => ({ loading: true, error: null })),
  on(tasksApiEvents.loadedSuccess, ({ payload }) => ({ tasks: payload, loading: false })),
  on(tasksPageEvents.added, ({ payload }, state) => ({
    tasks: [...state.tasks, { id: state.tasks.length + 1, title: payload, done: false }],
  })),
),

// 3. Efekty: strumień zdarzeń -> I/O -> NOWE zdarzenia (zwrócone = zdispatchowane)
withEventHandlers((_, events = inject(Events), api = inject(TasksApi)) => ({
  load$: events.on(tasksPageEvents.opened).pipe(
    switchMap(() => api.getAll().pipe(
      map((tasks) => tasksApiEvents.loadedSuccess(tasks)),
      catchError((e: Error) => of(tasksApiEvents.loadedFailure(e.message))),
    )),
  ),
})),
```

4. **Wysyłanie** w komponencie: `readonly dispatch = injectDispatch(tasksPageEvents);` i
   `dispatch.added('Kupić chleb')` — typowane, bez ręcznego tworzenia obiektu zdarzenia.

`eventGroup` buduje typ zdarzenia z szablonu `[Źródło] nazwa`, np. `[Tasks Page] opened`
(widać to w dzienniku w teście DOM). Zwróć uwagę na podział: **reduktor** zmienia stan,
**efekt** robi I/O i odpowiada nowym zdarzeniem — `loadedSuccess` wraca do reduktora, nie
ustawia stanu bezpośrednio.

Drugi store, `ActivityLogStore`, nie importuje `TasksStore` — słucha `events.on()` bez
argumentów (= wszystko) i zapisuje typy zdarzeń. Test: `opened` + 200 ms → dziennik
`['[Tasks Page] opened', '[Tasks API] loadedSuccess']`, a `TasksStore` ma 2 zadania, 1
zrobione. Nikt nikogo nie wywołał.

---

## 2️⃣ Pięć rzeczy, które zmierzyłem

Wszystkie w `events.mechanics.spec.ts` i `tasks.store.spec.ts`; źródło:
`node_modules/@ngrx/signals/fesm2022/ngrx-signals-events.mjs`.

### a) Kolejność: reduktor przed efektem, wszystko synchronicznie

`Dispatcher.dispatch` robi (źródło):

```javascript
this.reducerEvents[EVENTS].next(event);                       // reduktory - od razu
queueScheduler.schedule(() => this.events[EVENTS].next(event)); // efekty i słuchacze
```

Efekt, który czyta `store.count()`, widzi **już zwiększony** stan (test: `seen == [1]`).
`queueScheduler` nie jest asynchroniczny — poza zagnieżdżeniem odpala się od razu, więc stan
zmienia się synchronicznie w `dispatch()` (test: `tasks()` zawiera pozycję w linii po
`dispatch`).

### b) Zdarzenie zwrócone z efektu czeka na resztę handlerów bieżącego

Trzy handlery: h1 na `ping` zwraca `pong`, h2 też słucha `ping`, h3 słucha `pong`.
Zmierzona kolejność:

```text
h1 widzi ping -> h2 widzi ping -> h3 widzi pong
```

Zagnieżdżony `dispatch(pong)` z h1 trafia do kolejki `queueScheduler` i czeka, aż h2
dostanie `ping`. Czyli „dispatch z efektu" **nie jest** wywołaniem w głąb — to ważne, gdy
liczysz na kolejność skutków ubocznych. (Reduktor `pong` wykonałby się natychmiast — idzie
bezpośrednim kanałem; tego osobno nie mierzyłem, wynika ze źródła powyżej.)

### c) Strażnik pętli

Efekt `events.on(ping).pipe(tap(...))` emituje `ping` dalej, ale nie jest on ponownie
dispatchowany: `events.on()` oznacza zdarzenia ukrytym znacznikiem `SOURCE_TYPE`, a
`withEventHandlers` pomija zdarzenia z tym znacznikiem. Test: 1 wywołanie, zero pętli.
Tworzenie nowego zdarzenia (`map(() => pong())`) przechodzi normalnie.

### d) ⚠️ Haczyk: błąd w efekcie zabija go na zawsze

### 🎣 Dlaczego to ważne

To ten sam błąd co `rxMethod` z #4 i #12, tylko tym razem nie ma operatora, który by Cię
przed nim chronił. `withEventHandlers` robi `merge(...handlers).pipe(takeUntilDestroyed()).subscribe()`
— **bez obsługi błędu**. Pierwszy błąd, który wypłynie z któregokolwiek handlera tego
`withEventHandlers`, kończy cały merge.

Test: efekt `events.on(boom).pipe(switchMap(() => throwError(...)))` bez `catchError`,
trzy `dispatch(boom())`:

```text
started: 1                    // reszta boom() zignorowana
onUnhandledError: ['padło']   // błąd poleciał do rxjs config.onUnhandledError
```

Reguła jak wcześniej: `catchError` **wewnątrz** `switchMap`/`exhaustMap`, po wewnętrznym
observable. Test mutacyjny na `TasksStore`: przeniosłem `catchError` na zewnątrz
`switchMap` — padł test „kolejne `opened` znów działa" (`expected +0 to be 2`: po pierwszym
błędzie API drugie ładowanie nie wystartowało). Zmiana wycofana.

### e) ⚠️ Haczyk: wyjątek w reduktorze zabija reduktory, nie efekty

`withReducer` jest zbudowany na `withEventHandlers`, ale **osobnym** wywołaniu — własna
subskrypcja. Reduktor rzucający wyjątek na `boom`:

```text
po ping:                   n = 1
po boom (rzuca) i drugim ping:  n = 1   // reduktor martwy
handlerCalls:              3            // efekt na ping+boom żyje
```

Efekt: store przestaje zmieniać stan **bez żadnego błędu w UI** (błąd idzie tylko do
`onUnhandledError`/konsoli). Reduktory powinny być czyste i niezdolne do rzucania — żadnego
`JSON.parse`, żadnego dostępu do `undefined.x` na payloadzie z zewnątrz.

---

## 3️⃣ Trzy rzeczy z architektury, które mogą zaskoczyć

**Store jest leniwy, a strumień nie ma replay.** `ActivityLogStore` i `TasksStore` to
`providedIn: 'root'` — instancja powstaje przy pierwszym `inject`. Zdarzenia wysłane
wcześniej **przepadają**. Test: `dispatch(added('przed utworzeniem store'))`, potem
`inject(TasksStore)` → `tasks() == []`, `log() == []`; dopiero następne zdarzenie trafia.
W aplikacji pokrywa to fakt, że komponent wstrzykuje store przed pierwszym klikiem, ale dla
store'a „tylko nasłuchującego" (analityka, log) musisz go gdzieś jawnie utworzyć.

**`Dispatcher` i `Events` są `providedIn: 'platform'`** (źródło: `Injectable({ providedIn: 'platform' })`),
nie `'root'`. Jeden strumień na platformę. Zasięg lokalny dostajesz przez
`providers: [provideDispatcher()]` w komponencie. Zmierzone:

```text
local.dispatch(ping())                       -> widzi tylko lokalny słuchacz
local.dispatch(pong(), { scope: 'parent' })  -> widzi globalny
global.dispatch(ping())                      -> widzą OBA (lokalne Events łączą się z rodzicem)
```

Domyślny scope `dispatch` to lokalny („self"); w górę idzie tylko jawnie.

**Dokumentacja w komentarzach jest nieaktualna.** JSDoc nad `toScope`/`mapToScope` w
paczce 22.0.1 pokazuje `withEffects(...)`, ale takiego eksportu nie ma — jest
`withEventHandlers` (`grep` po `.mjs`: `withEffects` występuje wyłącznie w komentarzach).
Kopiując przykład z podpowiedzi IDE, dostaniesz błąd kompilacji. Tak samo przykłady
używają `mapResponse` z `@ngrx/operators` — dziś go nie instalowałem (dwa operatory
RxJS wystarczyły), więc to nadal niesprawdzone.

---

## 4️⃣ Weryfikacja — prawdziwy output

Node w tej sesji: **v22.14.0**, a Angular CLI 22.2.1 wymaga `>=22.22.3`. Bez obejścia:

```text
Node.js version v22.14.0 detected.
The Angular CLI requires a minimum Node.js version of v22.22.3 or v24.15.0 or v26.0.0.
```

Obejście jak w #9/#12/#13: lokalna edycja progu w
`node_modules/@angular/cli/src/utilities/node-version.js` (poza repo, `node_modules/` w
`.gitignore`); **trzeba je powtarzać po każdym `npm ci`** — dziś `npm ci` je skasował i
przywrócił komunikat powyżej. Nie omijałem tego inaczej niż przez ten jeden plik.

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

15 testów: 5 na `TasksStore`/`ActivityLogStore` (synchroniczny reduktor, dwa store'y na
jednym zdarzeniu, błąd API i odzyskanie, `switchMap` anuluje, leniwość), 8 mechanika na
gołych store'ach (kolejność, zagnieżdżenie, strażnik pętli, martwy efekt, martwy reduktor,
zniszczenie store'a, zasięgi, `patchState` w efekcie), 1 DOM, 1 smoke. Wszystkie przeszły
za pierwszym razem — dlatego zrobiłem test mutacyjny (wyżej), żeby upewnić się, że testy
naprawdę łapią regresję.

Dodatkowo test „`patchState` w efekcie": ręczne `patchState` w handlerze działa, ale
omija reduktory — stan zmienia się bez śladu w dzienniku zdarzeń. Technicznie możliwe,
stylistycznie to przeciwieństwo celu pluginu.

### ⚠️ Co jest niezweryfikowane (wprost)

- **`ng serve`/przeglądarka** — brak przeglądarki; `npm start` nie był uruchomiony.
- `mapResponse()` z `@ngrx/operators` w efektach (tylko z JSDoc), `mapToScope`/`toScope`
  w działaniu, `withEventHandlers` zwracające tablicę observable zamiast obiektu.
- Reduktor `pong` natychmiast przy zagnieżdżonym `dispatch` (wynika ze źródła, bez testu).
- Stabilność API: w kodzie 22.0.1 nie znalazłem znaczników `@experimental` (grep po
  `.mjs` i `.d.ts`), ale to nie jest gwarancja stabilności — sprawdź dokumentację NgRx.
- SSR/hydration (`Dispatcher` na poziomie platformy przy wielu requestach), Redux DevTools.
- Zakładam, że obejście progu wersji Node nie wpływa na wyniki; testy przeszły.

---

## 🧭 Do zapamiętania

| Potrzeba | Narzędzie |
|---|---|
| Opisać „co się stało" | `eventGroup({ source, events })` → `[Źródło] nazwa` |
| Wysłać z komponentu | `injectDispatch(grupa)` → `dispatch.added('x')` |
| Zmienić stan | `withReducer(on(zdarzenie, (e, state) => patch))` — czysto, bez wyjątków |
| Zrobić I/O | `withEventHandlers(... events.on(x).pipe(switchMap(... catchError ...)))` |
| Odpowiedzieć na I/O | zwróć nowe zdarzenie (`map(() => loadedSuccess(...))`) |
| Błąd w efekcie | `catchError` wewnątrz `switchMap`, inaczej efekt martwy na zawsze |
| Zasięg lokalny | `provideDispatcher()` + `{ scope: 'parent' \| 'global' }` |
| Store tylko nasłuchujący | wstrzyknij go jawnie — zdarzenia sprzed `inject` przepadają |

**Następnym razem (propozycja):** `@ngrx/operators` `mapResponse()` w efektach zdarzeń,
`debounce` jako funkcja i `'blur'` w `validateHttp` (z #13), `request` → `undefined`,
pozostałe pola `FormUiControl`, SSR/hydration.

---

## 📎 Jak uruchomić

Zobacz [`code/README.md`](code/README.md).

---

<div align="center">

[← wróć do wydania (wszystkie rubryki)](../README.md) · [spis wydań](../../../README.md)

</div>
