# Kod do wydania Angular z 08.10.2026 — dwa różne „debounce" w Signal Forms

Pełny artykuł: [`../ARTICLE.md`](../ARTICLE.md).

Wymagania: **Node.js** (zweryfikowane na v22.14.0 — zob. "Uwaga o wersji Node") i **npm**
(10.9.2). Wersje: `@angular/*` **22.2.1** (CLI/build 22.2.2), TypeScript **6.0.3**, `vitest`
**5.0.3** (jsdom), `rxjs` 7.8.2.

## Fragment prasówki, którego dotyczy ten kod

> W Signal Forms są dwa różne „debounce". Reguła `debounce(p.pole, 300 | 'blur' | Debouncer)` opóźnia
> **zapis z UI do modelu** (model i walidatory sync widzą stary stan do blura/końca timera;
> `dirty()` jest już `true`), a opcja `debounce` w `validateHttp` opóźnia tylko **request** (model
> zmienia się na bieżąco). Zmierzone na prawdziwych `<input>`: zapis programowy (`value.set`) omija
> debounce pola i kasuje oczekujący wpis z UI; reguła na korzeniu obejmuje pola potomne; w własnym
> `Debouncer` `ctx.value()` to wartość z modelu (o jeden wpis opóźniona), `void` = zapis od razu.
> Pułapka: `submit()` w trakcie debounce waliduje stary model i nie odpala akcji (blur przed submitem
> działa). `validateHttp`: `request → undefined` zdejmuje `pending`, ale NIE anuluje lecącego
> requestu (późna odpowiedź jest ignorowana); `debounce` jako funkcja dostaje `(request, snapshot)`,
> a snapshot startuje jako `'resolved'` (nie `'idle'`), `'loading'` = otwarte okno debounce.

## Struktura

```
src/app/
  app.ts, app.config.ts, app.spec.ts       -> host + 1 test
  projects/
    project.schema.ts        -> blurSchema, uiDebounceSchema, requestDebounceSchema,
                                customDebouncerSchema, httpDebounceFnSchema
    project-form.ts          -> komponent z blurSchema (model wyświetlany pod polem)
    mock-api.interceptor.ts  -> backend w pamięci dla `ng serve` (nazwa "boom" = błąd 500)
    debounce.spec.ts         -> 13 pomiarów (prawdziwe <input>, fake timery, HttpTestingController)
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

Sesja miała Node **v22.14.0**, a Angular CLI 22.2.2 wymaga `>=22.22.3`. Obejście (tylko lokalne,
plik w `node_modules/`, nie trafia do repo): w
`node_modules/@angular/cli/src/utilities/node-version.js` zmiana `'^22.22.3 || ...'` na
`'^22.14.0 || ...'`; trzeba je powtórzyć po każdym `npm ci`. Przy Node >= 22.22.3 niepotrzebne.

## Realna weryfikacja (ta sesja)

```text
$ npm ci --no-audit --no-fund
added 283 packages in 11s

$ npm run build
main-J64AWHFI.js    | main   | 233.03 kB | 65.01 kB
Application bundle generation complete. [5.829 seconds]

$ npm test
 Test Files  2 passed (2)
      Tests  14 passed (14)
```

Test mutacyjny: usunięcie `debounce(p.name, 'blur')` z `blurSchema` → padły 2 testy
(`expected 'prasow' to be ''`, `expected 'abc' to be ''`). Zmiana wycofana, 14/14.

Niezweryfikowane: `ng serve`/przeglądarka (w tym Enter w polu z `'blur'`), `debounce('blur')` na
własnej kontrolce `FormValueControl`, dostęp do wpisanego tekstu w `Debouncer`, SSR/hydration.
