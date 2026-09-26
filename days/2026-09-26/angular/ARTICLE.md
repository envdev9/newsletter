<div align="center">

# 📰 TECH PRASÓWKA
### Wydanie #4 rubryki Angular — 26 września 2026

![Angular](https://img.shields.io/badge/Angular-DD0031?style=for-the-badge&logo=angular&logoColor=white)

## Stan z HTTP: `linkedSignal`, `httpResource`, `rxMethod` i wybór między `switchMap` a `exhaustMap`

</div>

---

> _"Najdroższe błędy we frontendzie nie wynikają z braku wiedzy o Angularze. Wynikają ze
> stanu, który przeżył kontekst, w którym miał sens: zaznaczenie produktu, którego już nie ma
> na liście, odpowiedź na zapytanie, które użytkownik dawno porzucił."_

Ciąg dalszy po wydaniu #1 (signals, `@ngrx/signals`, kilka komponentów). Wydania #2 i #3
tej rubryki wypadły (na maszynie nie było Node) - dziś Node jest, więc **wszystko poniżej
zostało realnie zbudowane i przetestowane**. Zakładam, że znasz C#/.NET, ale nie Angulara.

| | |
|---|---|
| 🧱 Stack | `@angular/core` **22.2.0**, `@ngrx/signals` **22.0.1**, `rxjs` **7.8.2**, TypeScript **6.0.3** |
| 🖥️ Środowisko | Node **v22.23.3**, testy: Vitest **4.1.11** + jsdom (bez przeglądarki) |
| ✅ Weryfikacja | `npm ci` OK, `ng build` OK, `ng test` **8/8** (output w sekcji 6) |
| 📦 Kod | [`code/`](code/) - aplikacja "katalog produktów" z mock-backendem w pamięci |

**Plan wydania:** (1) `linkedSignal` w wersji, która ma pamięć, (2) `httpResource` /
`resource` - dane z HTTP jako sygnał, (3) signal store + `rxMethod`, (4) `switchMap` vs
`exhaustMap`, (5) testy, (6) czego nie sprawdziłem.

---

## 1️⃣ `linkedSignal` z pamięcią: nie gub zaznaczenia użytkownika

### 🎣 Dlaczego to ważne

W wydaniu #1 `linkedSignal(() => options()[0])` resetował wybór przy każdej zmianie źródła.
To dobre dla "kraj → opcje wysyłki". Ale wyobraź sobie listę wyników wyszukiwania:
użytkownik zaznaczył produkt nr 2, dopisał literę do frazy, lista się odświeżyła i nadal
zawiera produkt nr 2. Reset do pierwszego elementu byłby złym UX-em. W .NET (WPF/Blazor)
ląduje to w `OnItemsSourceChanged` z ręcznym `if (!items.Contains(selected))`.

### Co się zmieniło

Rozszerzona forma `linkedSignal` przyjmuje `source` i `computation`, a ta druga dostaje
**poprzednią wartość**. Reguła jest wtedy jedna, deklaratywna i w jednym miejscu:

```typescript
protected readonly selectedId = linkedSignal<{ id: number }[], number | undefined>({
  source: this.store.products,
  computation: (products, previous) =>
    products.find((p) => p.id === previous?.value)?.id ?? products[0]?.id,
});
```

Czytaj: "gdy zmieni się lista - zostaw poprzedni wybór, jeśli nadal istnieje, inaczej
weź pierwszy". Użytkownik nadal może zrobić `selectedId.set(id)`. Analogia: `computed`
to właściwość tylko-do-odczytu, `signal` to pole, a `linkedSignal` to **właściwość z
setterem, która sama się przelicza, gdy zmieni się to, na czym jest oparta**.

Test ([`product-browser.spec.ts`](code/src/app/products/product-browser.spec.ts))
sprawdza trzy zachowania: zaznaczenie zostaje, gdy produkt jest na nowej liście; resetuje
się na pierwszy, gdy zniknął; ręczny wybór działa.

---

## 2️⃣ `httpResource` i `resource()`: dane z HTTP jako sygnał

### 🎣 Dlaczego to ważne

Klasyczny wzorzec: `HttpClient.get()` → `subscribe` → ręczne flagi `loading`/`error` →
ręczne anulowanie poprzedniego żądania przy zmianie parametru. Każdy ekran ze szczegółami
ma ten sam boilerplate i te same błędy (wyścig: odpowiedź na stare `id` nadpisuje nowe).
`httpResource` daje to gotowe: **URL jest funkcją sygnałów, a wynikiem są sygnały**.

### Co sprawdziłem w zainstalowanej wersji

W `@angular/core` 22.2.0 i `@angular/common` 22.2.0 `resource()`, `httpResource` oraz
`ResourceRef` mają w plikach `.d.ts` adnotację `@publicApi 22.0` (czyli w tej wersji nie są
już oznaczone jako eksperymentalne; z pamięci, niesprawdzone tu: w wersjach 19/20 były w
podglądzie deweloperskim, więc sprawdź adnotację w swojej wersji). Uwaga na nazewnictwo: opcja
`request` z wczesnych wersji nazywa się dziś **`params`**, a w `resource()` loader dostaje
`{ params, abortSignal }`.

```typescript
protected readonly details = httpResource<ProductDetails>(() => {
  const id = this.selectedId();                       // czytamy signal => zależność
  return id === undefined ? undefined : `/api/products/${id}`;   // undefined = nie ładuj
});
```

W szablonie (nowa składnia `@switch`):

```html
@switch (details.status()) {
  @case ('idle')    { <p>Nic nie wybrano.</p> }
  @case ('loading') { <p>Pobieram szczegóły...</p> }
  @case ('error')   { <p class="error">Błąd szczegółów</p> }
  @default {
    @if (details.hasValue()) { <strong>{{ details.value().name }}</strong> }
  }
}
```

Powierzchnia API, którą warto znać: `value()`, `status()` (`idle` / `loading` /
`reloading` / `resolved` / `error` / `local`), `isLoading()`, `error()`, `hasValue()`,
`reload()`, `set()` (lokalne nadpisanie), `destroy()`. Zmiana `selectedId` powoduje
anulowanie poprzedniego żądania i wysłanie nowego - sam framework robi to, co w RxJS
robiłbyś `switchMap`-em.

Porównanie z .NET: to `Lazy<Task<T>>`, które samo się unieważnia, gdy zmieni się
parametr, i ma wbudowane `IsLoading`/`Error`.

**`resource()` vs `httpResource` vs `rxResource`:**

| API | Loader | Kiedy |
|---|---|---|
| `httpResource` | URL/`HttpResourceRequest` → `HttpClient` (interceptory działają!) | zwykłe GET-y - domyślny wybór |
| `resource` | `loader: ({ params, abortSignal }) => Promise<T>` | `fetch`, IndexedDB, dowolny Promise |
| `rxResource` (`@angular/core/rxjs-interop`) | `stream` zwracający Observable | gdy masz już Observable |

### ⚠️ Pułapki

- **Tylko do odczytu.** Dokumentacja typów wprost: `resource` jest przeznaczony do
  *pobierania*; przy zmianie parametru anuluje trwające ładowanie, co dla `POST` mogłoby
  przerwać mutację. Mutacje - przez `HttpClient`/`rxMethod` (sekcja 3).
- **`fixture.whenStable()` w testach.** Resource rejestruje "pending task", więc
  `whenStable()` czeka na odpowiedź HTTP. W teście z `HttpTestingController` grozi to
  timeoutem (trafiłem na to - pierwsza wersja testu wisiała 5 s). Rozwiązanie: nie czekać
  na stabilność, gdy żądanie jest w locie; najpierw `flush`.
- Interceptory (`withInterceptors`) obowiązują `httpResource`, bo pod spodem to `HttpClient`
  - dlatego mock backendu w projekcie działa tak samo dla wszystkiego.

---

## 3️⃣ Signal store + HTTP: `rxMethod`, `withMethods`, `withComputed`

### 🎣 Dlaczego to ważne

`httpResource` świetnie pasuje do "pobierz dane dla tego parametru". Ale wyszukiwarka z
debounce'em, licznik wyników, komunikat błędu i stan "składam zamówienie" to **stan
współdzielony z logiką**, więc mieszka w store, nie w komponencie. `rxMethod` to brakujące
ogniwo: metoda store'a, która pod spodem jest **potokiem RxJS**, ale z zewnątrz jest zwykłą
funkcją (`store.search('kl')`).

```typescript
export const ProductsStore = signalStore(
  { providedIn: 'root' },
  withState(initialState),                       // query, products, loading, error, ordering...
  withComputed(({ products, error, loading }) => ({
    count: computed(() => products().length),
    isEmpty: computed(() => !loading() && !error() && products().length === 0),
  })),
  withMethods((store, api = inject(ProductsApi)) => ({
    search: rxMethod<string>(
      pipe(
        map((q) => q.trim()),
        debounceTime(300),
        distinctUntilChanged(),
        tap((query) => patchState(store, { query, loading: true, error: null })),
        switchMap((query) =>
          api.search(query).pipe(
            tap((products) => patchState(store, { products, loading: false })),
            catchError(() => {
              patchState(store, { products: [], loading: false, error: 'Nie udało się pobrać produktów' });
              return of(null);
            }),
          ),
        ),
      ),
    ),
    // placeOrder - w sekcji 4
  })),
);
```

Jak to czytać (analogia do .NET): `withState` to pola, `withComputed` to właściwości
wyliczane, `withMethods` to metody, `patchState` to niemutujące `with` na rekordzie.
`rxMethod<T>(pipe(...))` przypomina `Subject<T>` + `Rx.NET`-owy pipeline schowany w
metodzie. Argumentem może być wartość, **signal** (metoda odpali się przy każdej jego
zmianie) albo Observable. Subskrypcja sprząta się razem ze store'em - bez ręcznego
`unsubscribe`.

### Operatory - po co każdy z nich (kolejność ma znaczenie)

| Operator | Po co | Co się stanie bez niego |
|---|---|---|
| `map(trim)` | normalizacja przed porównaniem | `"mysz "` i `"mysz"` to dwa żądania |
| `debounceTime(300)` | czekaj na ciszę | żądanie na każdy klawisz |
| `distinctUntilChanged()` | pomiń identyczną frazę | powtórne żądanie po wklejeniu tego samego |
| `switchMap` | anuluj poprzednie | wyścig: stara odpowiedź nadpisuje nową |
| `catchError` **wewnątrz** `switchMap` | błąd zabija to żądanie, nie strumień | jeden 500 i wyszukiwarka martwa do odświeżenia strony |

Najczęstszy błąd: `catchError` na zewnątrz `switchMap`. RxJS kończy strumień po błędzie,
więc wyszukiwarka przestaje reagować. W teście sprawdzam to wprost: po błędzie 500 kolejne
`search('ok')` nadal działa.

Uwaga: w `@ngrx/signals` istnieje też `tapResponse` (pakiet `@ngrx/operators`) skracający
`tap` + `catchError`. Nie użyłem go i nie sprawdzałem, żeby nie dokładać zależności -
wspominam z pamięci.

---

## 4️⃣ `switchMap` czy `exhaustMap`? (i `concatMap` jako trzeci)

### 🎣 Dlaczego to ważne

Wszystkie trzy operatory robią "dla każdej wartości uruchom wewnętrzne Observable". Różnią
się odpowiedzią na pytanie: **co, gdy nowa wartość przyjdzie, zanim poprzednie skończyło?**

| Operator | Zachowanie | Analogia w C# | Typowy przypadek |
|---|---|---|---|
| `switchMap` | anuluje poprzednie, liczy się najnowsze | `CancellationTokenSource.Cancel()` + nowe wywołanie | wyszukiwanie, szczegóły dla wybranego id (odczyty!) |
| `exhaustMap` | ignoruje nowe, dopóki poprzednie trwa | `if (_inFlight) return;` / `SemaphoreSlim(1)` z `Wait(0)` | submit formularza, "Zamów", odświeżanie tokenu |
| `concatMap` | kolejkuje, wykonuje po kolei | `Channel<T>` z jednym konsumentem | zapisy, które muszą zachować kolejność |

Reguła kciuka: **odczyt → `switchMap`, mutacja → `exhaustMap` lub `concatMap`**. Dlaczego
nie `switchMap` na mutacji? Bo anulowanie po stronie klienta nie cofa tego, co serwer już
zaczął: przerwany `POST` mógł się wykonać, a UI myśli, że nie. Dlatego dwuklik na "Zamów"
z `switchMap` może stworzyć dwa zamówienia albo zgubić informację o pierwszym.

```typescript
placeOrder: rxMethod<number>(
  pipe(
    exhaustMap((productId) => {
      patchState(store, { ordering: true, error: null });
      return api.placeOrder(productId).pipe(
        tap(({ orderId }) => patchState(store, { ordering: false, lastOrderId: orderId })),
        catchError(() => {
          patchState(store, { ordering: false, error: 'Zamówienie nie powiodło się' });
          return of(null);
        }),
      );
    }),
  ),
),
```

Test: trzy szybkie `placeOrder(1)` → `expectOne('/api/orders')` przechodzi (rzuciłby wyjątek,
gdyby żądań było więcej); po `flush` czwarte wywołanie tworzy nowe żądanie.

> To ograniczenie działa po stronie klienta. Prawdziwą ochronę przed duplikatami daje
> idempotentny endpoint (klucz idempotencji) - `exhaustMap` tylko oszczędza użytkownikowi
> podwójnego kliknięcia.

---

## 5️⃣ Mock backendu bez sieci

Żadnego zewnętrznego API. Aplikacja używa **funkcyjnego interceptora**
([`mock-api.interceptor.ts`](code/src/app/products/mock-api.interceptor.ts)) - to
odpowiednik `DelegatingHandler`/`HttpMessageHandler`, którego w .NET używasz w testach
integracyjnych. Zwraca dane w pamięci z opóźnieniem 200-800 ms; fraza `boom` daje 500, żeby
zobaczyć stan błędu. Podpięcie: `provideHttpClient(withInterceptors([mockApiInterceptor]))`
w `app.config.ts`. W testach jednostkowych używam `HttpTestingController`
(odpowiednik `MockHttpMessageHandler`) - tam interceptora nie ma.

---

## 6️⃣ Weryfikacja - prawdziwy output

Środowisko: Node **v22.23.3**, `@angular/core` **22.2.0**, `@ngrx/signals` **22.0.1**,
`rxjs` **7.8.2**, `vitest` **4.1.11**, `jsdom` **27.4.0**.

```text
$ npm ci --no-audit --no-fund
added 290 packages in 13s

$ npm run build          # = ng build
Initial chunk files | Names         |  Raw size | Estimated transfer size
main-P7V4R2DZ.js    | main          | 167.70 kB |                49.48 kB
styles-YDSRV2IW.css | styles        | 186 bytes |               186 bytes

                    | Initial total | 167.89 kB |                49.67 kB

Application bundle generation complete. [5.903 seconds]

$ npm test               # = ng test --no-watch (Vitest + jsdom, bez przeglądarki)
 Test Files  2 passed (2)
      Tests  8 passed (8)
   Duration  2.44s
```

Pokrycie testów (8 przypadków): debounce (299 ms - brak żądania, 300 ms - jedno),
`distinctUntilChanged` (po `trim`), `switchMap` (`req.cancelled === true` dla starego
żądania), przeżycie strumienia po błędzie 500, `exhaustMap` (3 kliknięcia = 1 żądanie),
`httpResource` w stanie `idle`, wybór przez `linkedSignal` + pobranie szczegółów, zachowanie
i reset zaznaczenia.

### ⚠️ Co jest niezweryfikowane (wprost)

- **Nie uruchamiałem aplikacji w przeglądarce** (`ng serve` + klikanie). Build i testy w
  jsdom przechodzą, ale wygląd i realny czas odpowiedzi interceptora nie były oglądane.
- `npm install` **bez lockfile'a** wywalił się tu błędem npm
  `Cannot read properties of null (reading 'edgesOut')` (wersja npm 10.x); dopiero
  `npm install --legacy-peer-deps` zadziałał i wygenerował `package-lock.json`. Z gotowym
  lockfile'em zwykłe `npm ci` działa (wynik wyżej). Przyczyny błędu npm nie zbadałem
  (dziennik npm był dla mnie nieczytelny).
- Zachowanie `resource()` (Promise) i `rxResource` opisałem na podstawie definicji typów w
  `node_modules`; **nie ma dla nich osobnego kodu ani testu** - kod projektu używa tylko
  `httpResource`.
- Projekt nie ma polyfilla `zone.js` ani `provideZonelessChangeDetection()`, a build i testy
  przechodzą - z tego wnioskuję, że zoneless jest domyślne w 22.x; nie potwierdziłem tego w
  dokumentacji.

---

## 🧭 Do zapamiętania

| Potrzeba | Narzędzie |
|---|---|
| Wybór zależny od listy, ale zmienialny ręcznie, z pamięcią | `linkedSignal({ source, computation })` |
| GET zależny od sygnałów, ze statusem | `httpResource` |
| Współdzielony stan + wyszukiwanie/mutacje | `signalStore` + `rxMethod` |
| Odczyt, liczy się ostatni | `switchMap` |
| Mutacja, ignoruj dubel | `exhaustMap` (lub `concatMap` przy kolejce) |

**Następnym razem (propozycja):** `resource()` z własnym loaderem i `AbortSignal`,
`withEntities`, `signalState`, własne feature'y store (`signalStoreFeature`), formularze
sygnałowe, jeśli dostępne w tej wersji.

---

## 📎 Jak uruchomić

Zobacz [`code/README.md`](code/README.md).

---

<div align="center">

[← wróć do wydania (wszystkie rubryki)](../README.md) · [spis wydań](../../README.md)

</div>
