# Kod do wydania Angular z 19.10.2026 — Signal Forms w SSR i hydracji

Pełny artykuł: [`../ARTICLE.md`](../ARTICLE.md).

Wymagania: **Node.js** (zweryfikowane na v22.14.0 — zob. "Uwaga o wersji Node") i **npm** (10.9.2).
Wersje: `@angular/*` **22.2.3** (z `platform-server`), TypeScript **6.0.3**, `vitest` **5.0.5** (jsdom 30.1.2),
`esbuild` 0.28.2, `rxjs` 7.8.2.

## Fragment prasówki, którego dotyczy ten kod

> `renderApplication` w czystym Node renderuje formularz Signal Forms z szablonu: `[formField]` na natywnym
> `<input>` emituje `value`, `required` i `name`. Serwer **czeka** na `validateAsync` (render trwa tyle, ile
> najwolniejsza walidacja: backend 200 ms → 286 ms, 800 ms → 816 ms), więc błąd jest już w HTML. Po hydracji
> walidacja startuje od nowa na kliencie — bez `TransferState` ten sam kod idzie na backend drugi raz.
> Hydracja ponownie używa węzłów DOM z serwera, ale nadpisuje to, co użytkownik wpisał przed startem JS, a atrybut
> `name` (`ng.formN.pole`) pochodzi z globalnego licznika w procesie.

## Struktura

```
src/app/
  app.ts, app.config.ts          -> host + provideClientHydration()
  checkout/
    availability.api.ts          -> udawany backend ("TAKEN" = zajęty) + TransferState
    checkout.schema.ts           -> required, debounce(300), validateAsync + resource, token DRAFT
    checkout-form.ts             -> formularz z dwoma natywnymi <input [formField]>
src/ssr/
  render.ts                      -> renderApplication (bundlowany do dist/ssr/render.mjs)
  fixtures.ts                    -> odczyt HTML wyrenderowanego przez prawdziwy SSR
  ssr.spec.ts                    -> 5 testów na HTML z serwera
  hydration.spec.ts              -> 8 testów hydracji w jsdom
scripts/
  bundle-ssr.mjs, ssr-shim.mjs   -> ngc (AOT) + esbuild -> jeden plik .mjs dla Node
  ssr-check.mjs                  -> 8 scenariuszy SSR w czystym Node (asercje + linie MEASURE)
tsconfig.ssr.json                -> kompilacja AOT kodu SSR przez ngc
```

## Jak uruchomić od zera

```bash
cd code
npm install                  # lub npm ci (jest package-lock.json)
npm run verify               # = build + ssr:build + ssr:check + test
```

Albo krok po kroku:

```bash
npm run build                # ng build (przeglądarkowy bundle)
npm run ssr:build            # ngc -p tsconfig.ssr.json + esbuild -> dist/ssr/render.mjs
npm run ssr:check            # prawdziwy SSR w Node; zapisuje dist/ssr/fixtures/*.html
npm test                     # ng test --no-watch (wymaga wcześniej ssr:check)
npm exec -- ng test --no-watch --reporters verbose   # pokazuje linie "MEASURE ..."
```

`npm test` bez wcześniejszego `ssr:check` kończy się czytelnym błędem o brakującym pliku w `dist/ssr/fixtures`.
NIE używaj gołego `npx vitest run` (brak `TestBed.initTestEnvironment()`). `node_modules/`, `dist/`, `.angular/`,
`out-tsc/` są w `.gitignore`. `npm start` (`ng serve`) — niezweryfikowane (brak przeglądarki).

### Uwaga o wersji Node

Sesja miała Node **v22.14.0**, a Angular CLI 22.2.3 wymaga `>=22.22.3`. Obejście (tylko lokalne, plik w
`node_modules/`, nie trafia do repo): w `node_modules/@angular/cli/src/utilities/node-version.js` zmiana stałej
`SUPPORTED_NODE_VERSIONS` z `'^22.22.3 || ...'` na `'^22.14.0 || ...'`; powtórz po każdym `npm install`.
Dodatkowo `package.json` przypina `jsdom` 30.1.2 i `overrides.undici` 8.11.2 (nowsze `undici` nie ładowało się na
Node 22.14). Przy Node >= 22.22.3 oba obejścia są zbędne. Na tym Node `ng build` z `outputMode: "server"` pada
(`registerHooks is not a function`), dlatego SSR jest składany przez `ngc` + `esbuild`.

## Realna weryfikacja (ta sesja)

```text
$ npm run build
main-RXBP4NBF.js    | main          | 238.57 kB | 67.29 kB
Application bundle generation complete. [6.673 seconds]

$ npm run ssr:check
MEASURE taken:        {"serverRequests":["TAKEN"],"elapsedMs":286,"hasErrorText":true,"mode":"tylko HTML","transferState":true,"hydrationMarkers":true,"valueAttr":true}
MEASURE free:         {"serverRequests":["FREE"],"hasErrorText":false}
MEASURE no-transfer-state: {"stateKeys":[]}
MEASURE slow-backend: {"elapsedMs":816,"hasErrorText":true}
MEASURE empty-draft:  {"serverRequests":[],"errorParagraphs":1,...}
MEASURE xss:          {"rawScriptInBody":false,"nameAttr":"&quot;&gt;&lt;script&gt;alert(1)&lt;/script&gt;"}
MEASURE parallel:     {"a":{"hasAla":true,"hasBob":false,"requests":["TAKEN"]},"b":{"hasAla":false,"hasBob":true,"requests":["FREE"]}}
MEASURE name-counter: ["ng.form0.code","ng.form1.code",...,"ng.form7.code"]
ssr-check: wszystkie asercje przeszły

$ npm test
 Test Files  2 passed (2)
      Tests  13 passed (13)
```

Wybrane linie `MEASURE` z hydracji (tryb verbose):

```text
dom-reuse-with-hydration: {"sameNode":true}
dom-reuse-without-ngh:    {"sameNode":false}
transfer-state-on:        {"afterBootstrap":{"errors":["Kod jest zajęty"],"mode":"JS aktywny"},...,"clientRequests":[],"cacheHits":["TAKEN"]}
transfer-state-off:       {"clientRequests":["TAKEN"],"cacheHits":[],"errors":["Kod jest zajęty"]}
after-hydration-typing:   {"errors":[],"clientRequests":["FREE"],"value":"FREE"}
typed-before-hydration:   {"domValueAfter":"Anna","sameNode":true}
name-attr:                {"server":"ng.form0.code","afterHydration":"ng.form7.code"}
```

Test mutacyjny: domyślna wartość `USE_TRANSFER_STATE` zmieniona na `false` → padły 2 testy
(`clientRequests:["TAKEN"]` zamiast `[]`, oraz `["TAKEN","FREE"]` zamiast `["FREE"]`). Po przywróceniu 13/13.

Niezweryfikowane: `ng serve`/przeglądarka (hydracja tylko w jsdom, zdarzenia syntetyczne), `withEventReplay()`,
cache HTTP między serwerem a klientem, `outputMode: "server"` i `@angular/ssr` na wspieranym Node, limit czasu
`renderApplication`, `mapResponse()`, CVA z `ngModel`/`FormControl` obok `[formField]`, `aria-*`.
