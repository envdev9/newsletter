# Kod do wydania Angular z 13.10.2026 — `FormCheckboxControl` i stary `ControlValueAccessor` pod `[formField]`

Pełny artykuł: [`../ARTICLE.md`](../ARTICLE.md).

Wymagania: **Node.js** (zweryfikowane na v22.14.0 — zob. "Uwaga o wersji Node") i **npm**
(10.9.2). Wersje: `@angular/*` **22.2.2**, TypeScript **6.0.3**, `vitest` **5.0.4** (jsdom),
`rxjs` 7.8.2.

## Fragment prasówki, którego dotyczy ten kod

> `FormCheckboxControl` wymaga `checked = model(false)` (nie `value`); `debounce(ms)` działa na nim
> jak na tekście, ale `dirty()` zostaje `true` po dwóch klikach, mimo że model się nie zmienił.
> Stary `ControlValueAccessor` działa pod `[formField]` bez zmian: kolejność wywołań to
> `registerOnChange`, `registerOnTouched`, `writeValue`, `setDisabledState(false)`; `onTouched()`
> jest odpowiednikiem `touch` dla `debounce('blur')`. `readonly` nie ma metody CVA (tylko `input()`),
> stare `NG_VALIDATORS` łączą się z regułami schematu. Komponent implementujący CVA i
> `FormValueControl` naraz: wygrywa CVA, `value`/`touch` są martwe. Pułapka: `FormField.reset()`
> w trakcie debounce cofa UI, ale nie anuluje wpisu — blur zapisuje go do modelu.

## Struktura

```
src/app/
  app.ts, app.config.ts, app.spec.ts   -> host + 1 test
  settings/
    settings.schema.ts   -> debounce(newsletter, 300), debounce(rating, 'blur'), min, disabled, readonly
    consent-toggle.ts    -> ConsentToggle: FormCheckboxControl
    star-rating.ts       -> StarRating (stary CVA), MinStarsValidator (NG_VALIDATORS), DualRating (CVA + FormValueControl)
    settings-form.ts     -> formularz z obiema kontrolkami
    settings.spec.ts     -> 17 testów / pomiarów (jsdom, fake timery, zdarzenia syntetyczne)
```

## Jak uruchomić od zera

```bash
cd code
npm ci                                # lockfile w repo
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
z `'^22.22.3 || ...'` na `'^22.14.0 || ...'`; trzeba je powtórzyć po każdym `npm ci`. Przy
Node >= 22.22.3 niepotrzebne.

## Realna weryfikacja (ta sesja)

```text
$ npm install --no-audit --no-fund
added 279 packages in 39s

$ npm run build
main-RO43RADI.js    | main   | 203.01 kB | 56.40 kB
Application bundle generation complete. [6.775 seconds]

$ npm test
 Test Files  2 passed (2)
      Tests  18 passed (18)
```

Wybrane linie `MEASURE` z trybu verbose:

```text
checkbox-click:    {"t0":{"control":true,"model":false,"dirty":true},"t299":{"model":false},"t300":{"model":true}}
checkbox-even-clicks: {"control":false,"model":false,"dirty":true}
native-checkbox:   {"immediately":{"domChecked":true,"model":false,"touched":false,"dirty":true},"after300":true}
cva-mount:         ["registerOnChange","registerOnTouched","writeValue(0)","setDisabledState(false)"]
cva-validators:    {"r0":["minStars","min"],"r2":["minStars"],"r4":[],"valid":true}
cva-vs-value:      {"calls":[...,"writeValue(3)"],"valueModel":0}
cva-reset:         {"afterReset":{"current":0,"model":0,"last":"writeValue(0)"},"afterBlur":{"current":5,"model":5}}
cva-destroy:       {"before":0,"after":3}
```

Test mutacyjny: usunięcie `debounce(p.newsletter, 300)` + wyłączenie `onTouched()` w `StarRating` →
padło 5 testów. Po przywróceniu 18/18.

Uwaga: `package-lock.json` został wygenerowany na nowo (kopiowanie lockfile'a z poprzedniego wydania
było zablokowane w środowisku).

Niezweryfikowane: `ng serve`/przeglądarka (zdarzenia w testach są syntetyczne), obejście pułapki
`reset()`, CVA razem z `ngModel`/`FormControl`, `NG_ASYNC_VALIDATORS`, SSR/hydration, `mapResponse()`.
