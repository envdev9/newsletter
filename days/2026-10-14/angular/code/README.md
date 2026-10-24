# Kod do wydania Angular z 14.10.2026 — `reset()` w trakcie `debounce` i `NG_ASYNC_VALIDATORS` pod `[formField]`

Pełny artykuł: [`../ARTICLE.md`](../ARTICLE.md).

Wymagania: **Node.js** (zweryfikowane na v22.14.0 — zob. "Uwaga o wersji Node") i **npm**
(10.9.2). Wersje: `@angular/*` **22.2.2**, TypeScript **6.0.3**, `vitest` **5.0.4** (jsdom),
`rxjs` 7.8.2.

## Fragment prasówki, którego dotyczy ten kod

> `FormField.reset()` tylko przepisuje wartość modelu do kontrolki — nie czyści i nie anuluje
> oczekującego wpisu `debounce`. Z `debounce(300)` model dostaje wpis po 300 ms, a UI nadal pokazuje
> stary tekst (do pierwszego blura). Obejście: `f.pole().reset(wartość)` (kasuje oczekujący wpis,
> zeruje `dirty`/`touched`), opcjonalnie + `FormField.reset()`. Stary `NG_ASYNC_VALIDATORS` pod
> `[formField]` nie jest wołany ani razu (pole `valid`, bez ostrzeżenia); zamiennik: `validateAsync`
> + `resource()` w schemacie.

## Struktura

```
src/app/
  app.ts, app.config.ts, app.spec.ts   -> host + 1 test
  signup/
    availability.api.ts   -> udawany serwer ("TAKEN" = zajęty), zapisuje zapytania
    code-input.ts         -> CodeInput (CVA), CodeAvailableValidator (NG_ASYNC_VALIDATORS)
    signup.schema.ts      -> required, debounce(300), validateAsync + resource
    signup-form.ts        -> formularz + naiveReset() / safeReset()
    signup.spec.ts        -> 13 testów / pomiarów (jsdom, fake timery, zdarzenia syntetyczne)
```

## Jak uruchomić od zera

```bash
cd code
npm ci                                # lub: npm install
npm run build                         # = ng build
npm test                              # = ng test --no-watch (Vitest + jsdom)
npm exec -- ng test --no-watch --reporters verbose   # pokazuje linie "MEASURE ..."
npm start                             # = ng serve (niezweryfikowane - brak przeglądarki)
```

NIE używaj gołego `npx vitest run` (brak `TestBed.initTestEnvironment()`).
`node_modules/`, `dist/`, `.angular/` są w `.gitignore`.

### Uwaga o wersji Node

Sesja miała Node **v22.14.0**, a Angular CLI 22.2.2 wymaga `>=22.22.3`. Obejście (tylko lokalne,
plik w `node_modules/`, nie trafia do repo): w
`node_modules/@angular/cli/src/utilities/node-version.js` zmiana stałej `SUPPORTED_NODE_VERSIONS`
z `'^22.22.3 || ...'` na `'^22.14.0 || ...'`; trzeba je powtórzyć po każdym `npm ci`/`npm install`.
Przy Node >= 22.22.3 niepotrzebne.

## Realna weryfikacja (ta sesja)

```text
$ npm install --no-audit --no-fund
added 279 packages in 56s

$ npm run build
main-7L7H5UNI.js    | main   | 208.59 kB | 57.51 kB
Application bundle generation complete. [6.896 seconds]

$ npm test
 Test Files  2 passed (2)
      Tests  14 passed (14)
```

Wybrane linie `MEASURE` z trybu verbose:

```text
reactive-forms-control:  {"validateCalls":["TAKEN"],"requests":["TAKEN"],"errors":{"taken":true},"status":"INVALID"}
formfield-legacy-async:  {"validateCalls":[],"requests":[],"model":"TAKEN2","errors":[],"valid":true,"pending":false}
validate-async-timeline: {"t0":{"model":"","pending":false,"requests":[]},"t299":{...},"t300":{"model":"TAKEN","pending":true,...},"t500":{"errors":["taken"],"valid":false,...}}
reset-naive-300:         {"afterReset":{"ui":"START","model":"START"},"later":{"ui":"START","model":"TYPED"},"afterBlur":{"ui":"TYPED","model":"TYPED"}}
reset-workaround-300:    {"afterReset":{"ui":"","model":"","dirty":false},"later":{"ui":"","model":""},"afterBlur":{"ui":"","model":""}}
reset-set-only:          {"ui":"","model":"","dirty":true,"touched":false}
signup-safe-in-flight:   {"inFlight":{"pending":true,...},"after":{"model":"","pending":false,"errors":["required"],"input":""}}
```

Test mutacyjny: usunięcie `FieldState.reset('')` z `safeReset()` + usunięcie `debounce(p.code, 300)`
ze schematu → padły 4 testy. Po przywróceniu 14/14.

Niezweryfikowane: `ng serve`/przeglądarka (zdarzenia syntetyczne), wyjaśnienie rozjazdu UI/model
(wniosek z kodu `signals.mjs`, nie z debuggera), `NG_ASYNC_VALIDATORS` na natywnym `<input>`,
CVA z `ngModel`/`FormControl` obok `[formField]`, sygnał `abort` przy resecie, SSR/hydration,
`mapResponse()`.
