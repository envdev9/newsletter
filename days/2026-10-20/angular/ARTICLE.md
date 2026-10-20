<div align="center">

# 📰 TECH PRASÓWKA
### Wydanie #27 rubryki Angular — 20 października 2026

![Angular](https://img.shields.io/badge/Angular-DD0031?style=for-the-badge&logo=angular&logoColor=white)
![NgRx Effects](https://img.shields.io/badge/NgRx-mapResponse-7B1FA2?style=for-the-badge)
![Interop](https://img.shields.io/badge/Signal_Forms-CVA_%2B_compat-2E7D32?style=for-the-badge)

## Dwa mosty między starym a nowym: `mapResponse()` w efektach NgRx i stare kontrolki obok Signal Forms

</div>

---

> _"Efekt, który po pierwszym błędzie przestaje reagować — i nikt tego nie loguje."_
> — wniosek z dzisiejszego testu, nie cytat z dokumentacji.

Dotąd w tej rubryce nowoczesny Angular żył w odosobnieniu. Prawdziwe aplikacje tak nie wyglądają: mają **NgRx Effects**
(odpowiednik handlera komunikatów z MediatR/MassTransit: akcja wchodzi, efekt uboczny się wykonuje, akcja wychodzi)
oraz **stare kontrolki formularzy** pisane przez lata pod `ngModel` i `FormControl`. Dziś dwa mosty: operator
`mapResponse()` i współpraca starego `ControlValueAccessor` (CVA) z Signal Forms.

| | |
|---|---|
| 🧱 Stack | `@angular/*` **22.2.3**, `@ngrx/store`/`effects`/`operators` **22.0.1**, TypeScript **6.0.3**, `rxjs` 7.8.2 |
| 🖥️ Środowisko | Node **v22.14.0**, npm 10.9.2, Vitest **5.0.5** + jsdom **30.1.2** (zdarzenia syntetyczne, bez przeglądarki) |
| ✅ Weryfikacja | `ng build` OK (7,3 s, 251,49 kB), `ng test` **13/13** (2 pliki) + test mutacyjny (2 padają) |
| 📦 Kod | [`code/`](code/) — efekt wyszukiwania zamówień, formularz profilu z `compatForm`, grupa z `SignalFormControl` |

---

## 1️⃣ `mapResponse()` — "tapResponse, który zwraca akcję"

### 🎣 Dlaczego to ważne

Efekt NgRx **musi zwrócić akcję** (to ona trafia do reducera). Klasyczny wzorzec to `map` + `catchError` wewnątrz
`switchMap`. `mapResponse` z `@ngrx/operators` pakuje go w jeden operator. Z skompilowanego źródła (`ngrx-operators.mjs`):

```javascript
function mapResponse(observer) {
  return (source$) => source$.pipe(map((value) => observer.next(value)),
                                   catchError((error) => of(observer.error(error))));
}
```

Czyli dosłownie `map` + `catchError(of(...))`. Różnica względem `tapResponse` z #12: ten **zwraca wartość** (akcję), nie
`void`, a w typie `MapResponseObserver` nie ma `complete`/`finalize`. Użycie:

```typescript
export const searchOrders = createEffect(
  (actions$ = inject(Actions), api = inject(OrdersApi)) =>
    actions$.pipe(
      ofType(OrdersActions.search),
      switchMap(({ query }) =>
        api.search(query).pipe(
          mapResponse({
            next: (orders) => OrdersActions.searchSuccess({ orders }),
            error: (e: HttpErrorResponse) => OrdersActions.searchFailure({ message: `HTTP ${e.status}` }),
          }),
        ),
      ),
    ),
  { functional: true },
);
```

Zmierzone (`HttpTestingController`, prawdziwy `Store` + reducer):

```text
MEASURE error-then-ok: {"actions":["[Orders] search","[Orders] search failure","[Orders] search","[Orders] search success"],
                        "state":{"loading":false,"orders":[{"id":2,...}],"error":null},"errorHandler":[]}
MEASURE switchMap-cancel: {"firstCancelled":true,"secondCancelled":false}
MEASURE manual-equals-mapResponse: {"same":true}
```

Błąd 500 → akcja porażki, efekt żyje, `ErrorHandler` nietknięty; `switchMap` anuluje poprzednie żądanie; ręczny
`map`+`catchError` daje **identyczny** przebieg. Czyli `mapResponse` to skrót, nie magia.

---

## 2️⃣ ⚠️ Gdzie postawić `mapResponse` — trzy sposoby na zepsucie efektu

### 🎣 Dlaczego to ważne

W #12 pokazałem, że źle ustawiony `tapResponse` zabija `rxMethod` na zawsze. W efektach NgRx jest **ciekawiej**, bo
framework ma własną siatkę bezpieczeństwa — i to ona zmienia objawy. Z kodu `ngrx-effects.mjs`: błąd wypływający z
efektu trafia do `ErrorHandler`, a efekt jest **subskrybowany ponownie, maksymalnie 10 razy** (`MAX_NUMBER_OF_RETRY_ATTEMPTS`).

**(a) `mapResponse` na zewnątrz `switchMap`.** Błąd zostaje złapany, ale `catchError` zastępuje cały strumień akcji
jednym `of(...)`, który się **kończy**:

```text
MEASURE outside: {"afterFirst":{"loading":false,"orders":[],"error":"HTTP 500"},
  "actions":["[Orders] search","[Orders] search failure","[Orders] search"],"secondRequests":0,"errorHandler":[]}
```

Pierwszy błąd obsłużony ładnie, ale kolejne wyszukiwanie **nie wysyła żadnego żądania**, a `ErrorHandler` milczy (strumień
się zakończył, nie wybuchł — siatka NgRx nie reaguje). Najgorszy wariant: cicha śmierć.

**(b) Brak obsługi błędu.** Błąd leci do NgRx: `ErrorHandler` dostaje wpis, efekt się wznawia — ale **reducer nigdy nie
dostaje akcji porażki**:

```text
MEASURE no-handling: {"stuck":{"loading":true,"orders":[],"error":null},"handled":1,"secondRequests":1,...}
MEASURE retry-limit: {"lastQueryThatSentRequest":11,"handledAfter":[1,2,3,4,5,6,7,8,9,10,10]}
```

UI zostaje z wiecznym `loading: true`. A po limicie: żądania 1–11 jeszcze wychodzą, 11. błąd nie trafia już do
`ErrorHandler`, a 12. wyszukiwanie nie wysyła nic — efekt umarł na dobre.

**(c) Wyjątek w samych callbackach.** Dwie zmierzone niespodzianki:

```text
MEASURE next-throws:  {"state":{"loading":false,"orders":[],"error":"JS: mapper wybuchł"},"errorHandler":[]}
MEASURE error-throws: {"handled":["callback error wybuchł"],"secondRequests":1,"state":{"loading":true,...}}
```

Wyjątek w `next` **trafia do callbacku `error`** (bo `catchError` stoi za `map`) — dostaje zwykły `Error`, nie
`HttpErrorResponse`, więc `e.status` byłoby `undefined`. Pisz `error` defensywnie. Wyjątek w samym `error` ucieka na
zewnątrz: `ErrorHandler` + wznowienie, reducer zawieszony w `loading`.

Test mutacyjny: przeniosłem `mapResponse` na zewnątrz `switchMap` w prawdziwym efekcie — padły **2** testy; po
przywróceniu 13/13.

**Dla .NET developera:** to jak `try/catch` wewnątrz pętli konsumenta wiadomości vs na zewnątrz. Na zewnątrz — po
pierwszym wyjątku pętla się kończy.

---

## 3️⃣ Stary `ControlValueAccessor` pod `ngModel`, `[formControl]` i `[formField]`

### 🎣 Dlaczego to ważne

Masz firmową bibliotekę kontrolek pisanych pod Reactive Forms. CVA to stary kontrakt (interfejs z czterema metodami:
`writeValue`, `registerOnChange`, `registerOnTouched`, `setDisabledState`). Ta sama kontrolka działa pod trzema
mechanizmami, ale **kolejność wywołań jest inna** — zmierzone na jednym komponencie `StarRating`:

```text
ngModel:     writeValue(null), setDisabledState(false), registerOnChange, registerOnTouched, writeValue(2)
formControl: writeValue(2), setDisabledState(false), registerOnChange, registerOnTouched
formField:   registerOnChange, registerOnTouched, writeValue(2), setDisabledState(false)
```

`ngModel` najpierw wpisuje `null` (prawdziwa wartość dociera mikrozadaniem później), `[formField]` rejestruje callbacki
przed wartością. Wniosek: CVA musi znosić `null` i dowolną kolejność.
### ⚠️ Pułapka: `ngModel` + `[formField]` na jednym elemencie

Brak błędu kompilacji, brak ostrzeżenia w konsoli (`console.warn`/`console.error`: 0 wywołań). Kto wygrywa?

```text
MEASURE both: {"results":{"ngModel-first":{"modelAfterClick":{"rating":2},"legacyAfterClick":5,"shownStars":5},
                          "formField-first":{"modelAfterClick":{"rating":2},"legacyAfterClick":5,"shownStars":5}},
               "warns":0,"errors":0}
```

**`ngModel` wygrywa po cichu**, w obu kolejnościach atrybutów: klik zmienia zmienną z `ngModel` (5), a model Signal
Forms zostaje nietknięty (2). Formularz wygląda poprawnie, a dane nie płyną. Pierwsza wartość wyświetlana to `writeValue(1)`
z `ngModel`, nie `2` z modelu. Zasada: jeden element — jeden mechanizm. (To ten sam rodzaj cichej porażki co stary
`NG_ASYNC_VALIDATORS` z #21.)

---

## 4️⃣ `compatForm` i `SignalFormControl` — mosty oficjalne

### 🎣 Dlaczego to ważne

Angular 22.2 ma osobny punkt wejścia `@angular/forms/signals/compat` (w `.d.ts`: `@publicApi 22.0`). Pozwala migrować
**po jednym polu**, zamiast przepisywać cały formularz.

**`compatForm`** — model Signal Forms, w którym jedno pole to stary `FormControl`:

```typescript
readonly ratingControl = new FormControl(0, { nonNullable: true, validators: [Validators.min(3)] });
readonly model = signal({ name: '', rating: this.ratingControl });
readonly f = compatForm(this.model, (p) => { required(p.name); });
// <input [formField]="f.name" />   <app-star-rating [formField]="f.rating" />
```

```text
MEASURE compat-init:        {"calls":["registerOnChange","registerOnTouched","writeValue(0)","setDisabledState(false)"],
                             "value":0,"errors":["min"],"valid":false,"nameErrors":["required"]}
MEASURE compat-after-click: {"control":4,"fieldValue":4,"errors":0,"dirty":true,"touched":false,"controlDirty":true}
MEASURE compat-after-blur:  {"fieldTouched":true,"controlTouched":true}
MEASURE compat-after-setValue: {"lastCall":"writeValue(5)","fieldValue":5}
MEASURE compat-after-disable:  {"lastCall":"setDisabledState(true)","fieldDisabled":true}
MEASURE compat-extract: {"extracted":{"name":"","rating":5},"modelStillHoldsControl":true}
```

- `f.rating().value()` zwraca **wartość**, nie obiekt `FormControl`; sygnał modelu nadal trzyma kontrolkę.
- Stary walidator `Validators.min(3)` pojawia się w `errors()` pola jako błąd o `kind: "min"` — **ta sama nazwa**, której
  używa nowy walidator `min` Signal Forms. Rozróżniaj po typie błędu, nie po samym `kind`.
- Dwukierunkowo: klik → `FormControl` i pole; `setValue(5)` z kodu → `writeValue(5)` w CVA i pole; `disable()` →
  `setDisabledState(true)` i `disabled()`. `touched` pojawia się dopiero po blurze, jak w poprzednich wydaniach.
- `extractValue(f)` zwraca surowe wartości `{name, rating}` — gotowe do wysłania na backend.

**`SignalFormControl`** — odwrotny kierunek: nowoczesne pole wewnątrz starego `FormGroup`:

```text
MEASURE group-init: {"valid":false,"status":"INVALID","nameErrors":{"required":{"kind":"required"}},
                     "ratingErrors":{"min":{"min":3,"actual":0}}}
MEASURE group-after-input: {"valid":true,"value":{"name":"Ola","rating":4},"dirty":true,"nameTouched":false}
MEASURE group-after-blur:  {"nameTouched":true,"groupTouched":true}
```

Pole `<input [formField]="name.fieldTree">` i `<app-star-rating formControlName="rating">` żyją w jednym `FormGroup`:
ważność, wartość, `dirty` i `touched` propagują się do grupy. Błędy Signal Forms pojawiają się w `errors` kontrolki jako
słownik `kind → obiekt błędu`.

---

## 5️⃣ Weryfikacja — prawdziwy output

Obejście środowiskowe jak w #9–#26: Node v22.14.0, a CLI 22.2.3 wymaga `>=22.22.3`. Lokalna jednolinijkowa edycja stałej
`SUPPORTED_NODE_VERSIONS` w `node_modules/@angular/cli/src/utilities/node-version.js` (poza repo; do powtórzenia po
`npm install`), oraz `jsdom` 30.1.2 + `overrides.undici` 8.11.2 w `package.json`.

```text
$ npm run verify
> ng build
main-6T6GTRKT.js    | main          | 251.49 kB | 68.50 kB
Application bundle generation complete. [7.304 seconds]
> ng test --no-watch
 Test Files  2 passed (2)
      Tests  13 passed (13)
```

### ⚠️ Co jest niezweryfikowane (wprost)

- **`ng serve` w przeglądarce**: w tym środowisku nie ma przeglądarki. Próbowałem uruchomić `ng serve` w tle i sprawdzić
  odpowiedź HTTP przez `curl` — **polecenie `curl` zostało odrzucone przez system uprawnień**, więc nie obchodziłem
  tego; w logu serwera widać tylko `Building...`. Efekt: aplikacja zbudowana i przetestowana w jsdom, ale nie
  obejrzana w żywej przeglądarce.
- `withEventReplay()` — nie ruszane (wymaga przeglądarki).
- `mapResponse()` testowany tylko z `HttpClient` + `HttpTestingController` (jedna emisja); zachowanie przy wielu emisjach
  strumienia wynika z kodu operatora (`map` na każdej), nie z testu.
- Limit 10 wznowień pochodzi z kodu i testu na jednym efekcie; nie sprawdzałem własnego `EFFECTS_ERROR_HANDLER`
  ani `useEffectsErrorHandler: false`.
- CVA: bez `NG_VALIDATORS` pod `compatForm`, bez `NG_ASYNC_VALIDATORS`, bez `debounce` na polu compat.
- Zdarzenia syntetyczne w jsdom, `aria-*`, SSR z efektami.

---

## 🧭 Do zapamiętania

| Potrzeba | Co zrobić |
|---|---|
| Efekt zwraca akcję sukcesu/porażki | `mapResponse({ next, error })` **wewnątrz** `switchMap`, przy wywołaniu HTTP |
| `mapResponse` na zewnątrz `switchMap` | Efekt kończy się po 1. błędzie, bez śladu w `ErrorHandler` |
| Brak obsługi błędu w efekcie | `ErrorHandler` + 10 wznowień, ale reducer zostaje w `loading`; po limicie efekt umiera |
| Wyjątek w `next` | Trafia do `error` jako zwykły `Error` — nie zakładaj `HttpErrorResponse` |
| Stary CVA pod nowym formularzem | Znoś `null` i dowolną kolejność wywołań |
| `ngModel` + `[formField]` na jednym elemencie | Nigdy: `ngModel` po cichu wygrywa, model Signal Forms stoi |
| Migracja po jednym polu | `compatForm` (stary `FormControl` w modelu) lub `SignalFormControl` (nowe pole w `FormGroup`) |

**Następnym razem (propozycja):** `withEventReplay()` i incremental hydration, `NG_VALIDATORS`/`NG_ASYNC_VALIDATORS` na
polach `compatForm`, `ng serve` w przeglądarce (jeśli będzie dostępna).

---

## 📎 Jak uruchomić

Zobacz [`code/README.md`](code/README.md).

---

<div align="center">

[← wróć do wydania (wszystkie rubryki)](../README.md) · [spis wydań](../../../README.md)

</div>
