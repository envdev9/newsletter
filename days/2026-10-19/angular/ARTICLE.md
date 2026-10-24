<div align="center">

# 📰 TECH PRASÓWKA
### Wydanie #26 rubryki Angular — 19 października 2026

![Angular](https://img.shields.io/badge/Angular-DD0031?style=for-the-badge&logo=angular&logoColor=white)
![SSR](https://img.shields.io/badge/SSR-renderApplication-1565C0?style=for-the-badge)
![Hydration](https://img.shields.io/badge/Hydration-Signal_Forms-2E7D32?style=for-the-badge)

## Signal Forms na serwerze: co naprawdę trafia do HTML, kto czeka na walidację i co gubi hydracja

</div>

---

> _"Angular hydration was requested on the client, but there was no serialized information present in the
> server response, thus hydration was not enabled."_
> — NG0505, prawdziwy komunikat z dzisiejszych testów.

Przez pięć wydań dociskałem Signal Forms w jsdom i w przeglądarkowym `TestBed`. Wszystko działało — w świecie,
w którym formularz zaczyna życie na kliencie. Dziś pierwszy raz renderuję go **na serwerze, w czystym Node**,
a potem „ożywiam” w przeglądarce hydracją. Dla .NET developera to Razor Pages / Blazor Server prerendering:
serwer wysyła gotowy HTML, a potem w przeglądarce włącza się interaktywność. Pytania są te same, co w Blazorze:
co jest w HTML, czy backend jest wołany dwa razy i co się dzieje z tym, co użytkownik wpisał, zanim JS się załadował.

| | |
|---|---|
| 🧱 Stack | `@angular/*` **22.2.3** (w tym `platform-server`), TypeScript **6.0.3**, `rxjs` 7.8.2, `esbuild` 0.28.2 |
| 🖥️ Środowisko | Node **v22.14.0**, npm 10.9.2, Vitest **5.0.5** + jsdom **30.1.2** (zdarzenia syntetyczne, bez przeglądarki) |
| ✅ Weryfikacja | `npm install`, `ng build` OK (6,7 s, 238,57 kB), `ssr:build` + `ssr:check` (8 scenariuszy, asercje `node:assert`), `ng test` **13/13** (2 pliki) + test mutacyjny (2 padają) |
| 📦 Kod | [`code/`](code/) — formularz zamówienia z `validateAsync`, `renderApplication` w czystym Node, hydracja w jsdom |

**Plan:** (1) jak uruchomić `renderApplication` w Node, (2) co jest w HTML, (3) serwer czeka na walidację,
(4) dwa wołania backendu i `TransferState`, (5) pułapki hydracji, (6) weryfikacja i luki.

---

## 1️⃣ `renderApplication` w czystym Node — i dlaczego nie w Vitest

### 🎣 Dlaczego to ważne

`renderApplication(bootstrap, { document, url })` to rdzeń SSR: bierze funkcję bootstrapującą aplikację, czeka,
aż aplikacja się „ustabilizuje”, i zwraca string z HTML. Bez Expressa i bez `@angular/ssr`:

```typescript
const html = await renderApplication(
  (context) => bootstrapApplication(App, { providers: [...appConfig.providers, provideServerRendering()] }, context),
  { document: SHELL, url: '/' },
);
```

Moja pierwsza próba — wywołać to wprost w teście Vitest — **nie działa**, i to w podstępny sposób. Runner
Angulara inicjuje platformę przeglądarkową (TestBed), a po `destroyPlatform()` + `platformServer()` aplikacja nadal
dostaje `BrowserDomAdapter` i pada na `document is not defined`. Eksperyment diagnostyczny: nawet jawne
`DominoAdapter.makeCurrent()` nie zmieniało adaptera widzianego przez `@angular/common` w teście. Moja interpretacja
(wniosek z eksperymentu, nie z kodu runnera): w procesie testowym są dwie kopie `@angular/common` — jedna wbudowana
w bundle testu, druga ładowana z `node_modules` przez `platform-server`.

Drugie ślepe wejście: `ng build` z `outputMode: "server"` (bundle serwerowy robi builder). Na moim Node 22.14.0 pada:

```text
TypeError: (0 , node_module_1.registerHooks) is not a function
    at .../node_modules/@angular/build/src/utils/server-rendering/esm-in-memory-loader/register-hooks.js:14:33
```

Wyciąganie tras przez builder potrzebuje `module.registerHooks`, którego ten Node nie ma. Na Node ≥ 22.22.3
(wymóg samego CLI) nie sprawdzałem, czy przechodzi.

**Rozwiązanie, które działa i jest uczciwe:** kompilacja AOT przez `ngc` + jeden bundle `esbuild` dla Node
(`npm run ssr:build`). Jeden plik `.mjs` = jedna kopia Angulara w procesie. Dwie rzeczy do wiedzy:

- biblioteki Angulara w npm są w formie „partial”; zwykły bundler ich nie linkuje, więc do bundla wstrzykuję
  `import '@angular/compiler'` (dolinkowanie w locie) — działa, ale to nie jest ścieżka produkcyjna buildera;
- `require` dla zależności CJS (domino) w ESM — jednolinijkowy shim `createRequire`.

To jest **narzędzie do weryfikacji**, nie rekomendacja wdrożeniowa: w prawdziwym projekcie użyj `@angular/ssr`
i buildera na wspieranym Node.

---

## 2️⃣ Co faktycznie jest w HTML

### 🎣 Dlaczego to ważne

Formularz z szkicu zamówienia (`name: "Anna"`, `code: "TAKEN"`, kod „TAKEN” jest zajęty). Wynik prawdziwego
`renderApplication` (tylko doformatowany białymi znakami, treść i atrybuty bez zmian):

```html
<!--nghm-->
<app-root ng-version="22.2.3" ngh="1" ng-server-context="other">
  <h1>Angular: Signal Forms w SSR i hydracji</h1>
  <app-checkout-form ngh="0"><form>
    <label>Imię <input id="name" name="ng.form0.name" required="" value="Anna"></label>
    <label>Kod  <input id="code" name="ng.form0.code" required="" value="TAKEN"></label>
    <p class="error">Kod jest zajęty</p>
    <p id="mode">tylko HTML</p>
  </form></app-checkout-form>
</app-root>
<script id="ng-state" type="application/json">{"coupon-taken:TAKEN":true,"__nghData__":[...]}</script>
```

Co z tego wynika (wszystko zmierzone na wyjściu, nie z dokumentacji):

- `[formField]` na natywnym `<input>` emituje **atrybuty**: `value`, `required` (z reguły schematu) i `name`.
  Strona działa jako zwykły HTML nawet bez JS.
- `ngh` / `<!--nghm-->` to znaczniki hydracji; `ng-state` to `TransferState` serializowany do JSON w stronie.
- `afterNextRender` **nie wykonuje się na serwerze** — `#mode` mówi „tylko HTML”. Wszystko, co zależy od
  przeglądarki (pomiar, focus, `localStorage`), musi siedzieć w `afterNextRender`, nie w konstruktorze.
- Wartość z modelu jest escapowana: szkic z `"><script>alert(1)</script>` wychodzi jako
  `&quot;&gt;&lt;script&gt;…` (poza `ng-state` w body nie ma surowego `<script>alert`). Zmierzone asercją.
- Dwa równoległe rendery w jednym procesie (`Ala`/`TAKEN` i `Bob`/`FREE`) nie mieszają danych — każdy ma swój
  injector, a liczniki żądań do backendu są rozdzielone.

---

## 3️⃣ Serwer czeka na walidację asynchroniczną — i to jest miecz obosieczny

### 🎣 Dlaczego to ważne

`validateAsync` + `resource()` (znane z #21) działa na serwerze, a `renderApplication` **poczekał** na wynik:
błąd „Kod jest zajęty” jest już w HTML. Użytkownik nie widzi migania „pole OK” → „pole błędne”. Ale cena:

```text
MEASURE taken:        {"serverRequests":["TAKEN"],"elapsedMs":286, "hasErrorText":true, ...}   // backend: 200 ms
MEASURE slow-backend: {"elapsedMs":816,"hasErrorText":true}                                     // backend: 800 ms
```

Czas renderu serwera = czas **najwolniejszej** walidacji w drzewie (200 ms backendu → 286 ms renderu; 800 ms → 816 ms).
Wolny backend sprawdzający unikalność kodu staje się TTFB całej strony. Mechanizm (rozliczanie zadań w toku przez
`resource`) to moja hipoteza do wyjaśnienia pomiaru; sam pomiar jest pewny. Nie testowałem, czy `renderApplication`
ma własny limit czasu — jeśli walidacja jest opcjonalna dla pierwszego renderu, rozważ jej pominięcie na serwerze
(`isPlatformServer`) zamiast czekania. To ocena projektowa, nie wynik testu.

Drugi drobiazg z `empty-draft`: pusty szkic renderuje `<p class="error">` **od razu**, zanim ktokolwiek dotknął pola
(błąd `required` jest w `errors()` niezależnie od `touched`). Szablon powinien filtrować po `touched()`, jeśli nie
chcesz czerwonego formularza w pierwszej sekundzie.

---

## 4️⃣ Dwa wołania backendu i `TransferState`

### 🎣 Dlaczego to ważne

Serwer sprawdził kod i wiedział, że jest zajęty. Po hydracji `validateAsync` startuje **od nowa** na kliencie.
Bez przeniesienia wyniku ten sam kod idzie na backend drugi raz. `AvailabilityApi` zapisuje wynik na serwerze
w `TransferState` i odczytuje go na kliencie (licznik `requests` liczy tylko prawdziwe wywołania):

```text
MEASURE transfer-state-on:  {"afterBootstrap":{"errors":["Kod jest zajęty"],"mode":"JS aktywny"},
                             "afterStable":{"errors":["Kod jest zajęty"],"mode":"JS aktywny","pending":false},
                             "clientRequests":[],"cacheHits":["TAKEN"]}
MEASURE transfer-state-off: {"clientRequests":["TAKEN"],"cacheHits":[],"errors":["Kod jest zajęty"]}
```

- Z `TransferState`: 0 zapytań klienta, błąd widoczny **od razu po bootstrapie** (HTML z serwera nie jest
  przerysowany), a po ustabilizowaniu `pending` jest `false`.
- Bez: dokładnie to samo zapytanie drugi raz (`clientRequests:["TAKEN"]`).
- Po hydracji formularz żyje normalnie: wpis `FREE` + debounce 300 ms → jedno zapytanie (cache chybia, bo klucz
  zawiera kod), błąd znika.

Z `HttpClient` dostajesz to samo za darmo (`provideClientHydration()` włącza cache odpowiedzi HTTP między serwerem
a klientem). Tu użyłem `setTimeout` zamiast HTTP, żeby test był samodzielny — **cache HTTP nie był dziś testowany**.

Test mutacyjny: ustawiłem domyślną wartość `USE_TRANSFER_STATE` na `false`; padły **2** testy (brak cache oraz
`clientRequests:["TAKEN","FREE"]` zamiast `["FREE"]`). Po przywróceniu 13/13.

---

## 5️⃣ ⚠️ Pułapki hydracji

### 🎣 Dlaczego to ważne

**Hydracja naprawdę używa węzłów z serwera.** Test: ten sam `<input id="code">` przed i po bootstrapie.

```text
MEASURE dom-reuse-with-hydration: {"sameNode":true}
MEASURE dom-reuse-without-ngh:    {"sameNode":false}      // + w konsoli NG0505
Angular hydrated 2 component(s) and 20 node(s), 0 component(s) were skipped.
```

Kontrola bez znaczników SSR (usunięty `ngh` i `ng-state`) zbudowała DOM od nowa. (Pierwotna kontrola przez
pominięcie `provideClientHydration()` rzuciła w jednym procesie testowym `NG0500` — wygląda na to, że stan hydracji jest
w procesie globalny; wniosek z objawu. Liczniki „hydrated N component(s)” rosną w procesie narastająco, więc cytuję
tylko pierwszy, czysty odczyt.)

**Pułapka 1: tekst wpisany przed hydracją jest nadpisywany.** Użytkownik na wolnym łączu zaczął pisać imię, zanim
załadował się JS:

```text
MEASURE typed-before-hydration: {"domValueAfter":"Anna","sameNode":true}
```

Węzeł jest ten sam (hydracja go nie przebudowała), ale po starcie wartość DOM to `Anna` z modelu — wpis `Zofia` znika.
To ten sam rodzaj błędu co w Blazor Server przy zerwanym obwodzie. Czy replay zdarzeń (`withEventReplay()`) coś tu
ratuje — **nie sprawdzałem** (wymaga prawdziwej przeglądarki i kontraktu zdarzeń w HTML).

**Pułapka 2: `name` pola nie jest stabilny.** Atrybut `name` generuje globalny licznik formularzy w procesie
(`ng.form{N}.pole`). Osiem kolejnych renderów jednego formularza w jednym procesie Node dało:

```text
MEASURE name-counter: ["ng.form0.code","ng.form1.code",...,"ng.form7.code"]
MEASURE name-attr:    {"server":"ng.form0.code","afterHydration":"ng.form7.code"}
```

Serwer numeruje „w górę” przez cały czas życia procesu (nawet po tysiącach żądań), więc HTML różni się między
żądaniami (cache HTML na CDN i diffy snapshotów to wyczują), a klient po hydracji przepisuje atrybut własnym licznikiem.
Jeśli polegasz na `name` przy autouzupełnianiu, testach E2E albo klasycznym POST bez JS — ustaw `name` jawnie.
(W teście `afterHydration` to `form7`, bo moduł w jsdom jest współdzielony między testami; w świeżej przeglądarce
licznik zaczyna od zera. To dedukcja z mechanizmu, nie pomiar w przeglądarce.)

---

## 6️⃣ Weryfikacja — prawdziwy output

Node w tej sesji: **v22.14.0**, a CLI 22.2.3 wymaga `>=22.22.3`. Obejście jak w #9–#21: lokalna jednoliniowa
edycja stałej `SUPPORTED_NODE_VERSIONS` w `node_modules/@angular/cli/src/utilities/node-version.js`
(`^22.22.3` → `^22.14.0`), poza repo, do powtórzenia po każdym `npm install`. Dodatkowo `jsdom@30.1.3` ciągnął
`undici` wymagający nowszego Node (`Cannot read properties of undefined (reading 'bind')`), więc w `package.json`
jest `jsdom: 30.1.2` i `overrides: { undici: 8.11.2 }` — na nowszym Node niepotrzebne.

```text
$ npm run verify
> ng build
main-RXBP4NBF.js    | main          | 238.57 kB | 67.29 kB
Application bundle generation complete. [6.673 seconds]

> ngc -p tsconfig.ssr.json && node scripts/bundle-ssr.mjs
dist/ssr/render.mjs gotowy

> node scripts/ssr-check.mjs
MEASURE taken: {"serverRequests":["TAKEN"],"elapsedMs":286,"hasErrorText":true,"mode":"tylko HTML",...}
ssr-check: wszystkie asercje przeszły

> ng test --no-watch
 Test Files  2 passed (2)
      Tests  13 passed (13)
```

Podział: `ssr-check.mjs` (osobny proces Node, prawdziwy SSR, zapisuje HTML do `dist/ssr/fixtures`) → `ssr.spec.ts`
(5 testów na HTML) i `hydration.spec.ts` (8 testów hydracji w jsdom na tym HTML). Dzięki temu Angular w teście
hydracji dostaje **prawdziwy** HTML z serwera, a nie ręcznie zbudowany.

### ⚠️ Co jest niezweryfikowane (wprost)

- **`ng serve`/przeglądarka**: hydracja sprawdzona w jsdom ze zdarzeniami syntetycznymi; realny focus, autouzupełnianie,
  IME i `withEventReplay()` nie były testowane.
- **Builder `outputMode: "server"` i `@angular/ssr`**: pada na Node 22.14.0 (`registerHooks`); na wspieranym Node
  nie sprawdzałem. Mój bundle `ngc` + `esbuild` to obejście do weryfikacji, nie ścieżka produkcyjna.
- Cache odpowiedzi `HttpClient` między serwerem a klientem — tu tylko ręczny `TransferState`.
- Limit czasu `renderApplication` przy wolnym backendzie; zachowanie przy błędzie walidacji na serwerze.
- Wyjaśnienie dwóch kopii `@angular/common` w Vitest to interpretacja eksperymentu; globalny stan hydracji — wniosek z objawu.
- `mapResponse()` w `@ngrx/effects`, CVA z `ngModel`/`FormControl` obok `[formField]`, `aria-*`.

---

## 🧭 Do zapamiętania

| Potrzeba | Co zrobić |
|---|---|
| SSR w Node bez frameworka | `renderApplication(bootstrap, { document })` z `provideServerRendering()`; jeden bundle = jedna kopia Angulara |
| Test SSR | Renderuj w osobnym procesie; nie w `TestBed`/Vitest (zła platforma DOM) |
| Walidacja async na serwerze | Serwer **czeka** — TTFB = najwolniejsza walidacja; błąd trafia do HTML |
| Powtórne wołanie backendu po hydracji | `TransferState` (albo cache HTTP) — inaczej 2× to samo zapytanie |
| Kod zależny od przeglądarki | Tylko w `afterNextRender`; na serwerze się nie wykona |
| Wpis przed hydracją | Zostanie nadpisany modelem — nie obiecuj użytkownikowi inaczej bez testu `withEventReplay()` |
| `name` pola | Globalny licznik w procesie (`ng.form7.code`) — ustaw jawnie, jeśli ma znaczenie |
| Błędy w pierwszym HTML | `required` widać przed `touched` — filtruj w szablonie |

**Następnym razem (propozycja):** `mapResponse()` w `@ngrx/effects`, CVA z `ngModel` obok `[formField]`, `withEventReplay()`
i incremental hydration (`@defer (hydrate on …)`), `ng serve` w prawdziwej przeglądarce (jeśli będzie dostępna).

---

## 📎 Jak uruchomić

Zobacz [`code/README.md`](code/README.md).

---

<div align="center">

[← wróć do wydania (wszystkie rubryki)](../README.md) · [spis wydań](../../../README.md)

</div>
