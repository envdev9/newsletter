# Kod do wydania Angular z 06.10.2026 — `validateHttp`: asynchroniczna walidacja pola przez HTTP

Pełny artykuł: [`../ARTICLE.md`](../ARTICLE.md).

Wymagania: **Node.js** (zweryfikowane na v22.14.0 — zob. "Uwaga o wersji Node") i **npm**
(10.9.2). Wersje: `@angular/*` **22.2.1**, `@angular/forms` **22.2.1** (`/signals`,
`@publicApi 22.0`), TypeScript **6.0.3**, `vitest` **5.0.3** (jsdom), `rxjs` 7.8.x.

## Fragment prasówki, którego dotyczy ten kod

> `validateHttp(path, opts)` z `@angular/forms/signals` to — dosłownie, według skompilowanego
> źródła — `validateAsync` z `factory: request => httpResource(request, opts.options)`.
> Daje: `request` (URL albo `{url, params}`), `debounce`, `when`, `onSuccess`/`onError`
> mapujące odpowiedź/błąd HTTP na błędy pola. Zmierzone testem: 4 szybkie zmiany wartości =
> **1** request z `debounce: 300` (bez debounce: 4 requesty, 3 anulowane); `pending()` jest
> `true` już w oknie debounce; reguły sync (`required`/`minLength`) blokują HTTP całkowicie;
> `{url, params}` koduje `Ala & Ola` jako `Ala%20%26%20Ola`, a ręcznie sklejony string wysyła
> surowe `Ala & Ola`. Pułapka: pierwsza wartość NIE jest debounce'owana, jeśli pole nie było
> wcześniej czytane (leniwe metadane) — w teście trzeba je „przeczytać" przed `set()`.

## Struktura

```
src/app/
  app.ts, app.config.ts          -> host + provideHttpClient(withInterceptors([mockApiInterceptor]))
  projects/
    project.schema.ts            -> projectSchema (POPRAWNA) i naiveProjectSchema (do porównania)
    project-form.ts              -> komponent: [formField], pending()/errors()/valid() w szablonie
    mock-api.interceptor.ts      -> backend w pamięci (tylko dla ng serve; testy go nie używają)
    project.schema.spec.ts       -> 10 testów na samym drzewie pól (bez DOM) + HttpTestingController
    project-form.spec.ts         -> 2 testy w DOM
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

W `ng serve` spróbuj nazw: `prasowka`, `angular`, `Ala & Ola` (zajęte, z sugestią), `boom`
(symulowany błąd 500), dowolna inna (wolna). `node_modules/`, `dist/`, `.angular/` są w `.gitignore`.

### Uwaga o wersji Node

Sesja miała Node **v22.14.0**, a Angular CLI 22.2.1 wymaga `>=22.22.3`. Obejście (tylko lokalne,
plik w `node_modules/`, nie trafia do repo): w
`node_modules/@angular/cli/src/utilities/node-version.js` zmiana `'^22.22.3 || ...'` na
`'^22.14.0 || ...'`; trzeba je powtórzyć po każdym `npm ci`. Przy Node >= 22.22.3 niepotrzebne.

## Realna weryfikacja (ta sesja)

```text
$ npm ci --no-audit --no-fund
added 281 packages in 10s

$ npm run build
main-PS6CR6TM.js    | main   | 232.62 kB | 64.96 kB
Application bundle generation complete. [5.199 seconds]

$ npm test
 Test Files  3 passed (3)
      Tests  13 passed (13)
```

Test mutacyjny: po usunięciu `debounce: 300` z `projectSchema` padły 3 testy (2 w schemacie, 1 w DOM) —
m.in. oczekiwano 1 requestu, przyszły 4 (`name=pra`, `pras`, `prase`, `prasow`). Zmiana wycofana.

Niezweryfikowane: `ng serve`/przeglądarka, SSR/hydration, `debounce` jako funkcja/`'blur'`,
`request` zwracające `undefined`, `options` (`HttpResourceOptions`) przekazane do `validateHttp`.
