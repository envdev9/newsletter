# Kod do wydania Angular z 12.10.2026 — `debounce('blur')` na własnej kontrolce `FormValueControl`

Pełny artykuł: [`../ARTICLE.md`](../ARTICLE.md).

Wymagania: **Node.js** (zweryfikowane na v22.14.0 — zob. "Uwaga o wersji Node") i **npm**
(10.9.2). Wersje: `@angular/*` **22.2.2**, TypeScript **6.0.3**, `vitest` **5.0.3** (jsdom),
`rxjs` 7.8.2.

## Fragment prasówki, którego dotyczy ten kod

> `debounce(p.pole, 'blur')` na własnej kontrolce działa tylko wtedy, gdy kontrolka ma output
> `touch` emitowany na `blur`. Bez niego kod się kompiluje, a model nie zapisze się nigdy
> (zmierzone: po 1 s `model == ''`, `touched == false`). Podczas pisania model stoi w miejscu,
> `dirty()` jest `true`, a walidatory widzą stary model (komunikat `required` mimo wpisanego tekstu).
> Oczekujący wpis domykają: `blur`, Enter z `touch.emit()` oraz zniszczenie kontrolki (`flushSync`).
> Dodatkowo: `disabled`/`readonly`/`hidden` pomijają walidację (`submit()` przechodzi z pustym
> `required`), maskują `touched`/`dirty`, a kontrolka sama dostaje `required`/`pattern`/`maxLength`/
> `name`/`disabledReasons` bez bindowania. `hidden` bez `@if` zostawia kontrolkę w DOM i ostrzega w dev.

## Struktura

```
src/app/
  app.ts, app.config.ts, app.spec.ts   -> host + 1 test
  sku/
    sku.schema.ts        -> skuSchema: debounce('blur'), required, pattern, maxLength,
                            disabled/readonly/hidden sterowane polem `mode`
    sku-input.ts         -> SkuInput (pełny kontrakt FormUiControl + touch)
                            i NoTouchSkuInput (celowo bez touch)
    sku-form.ts          -> formularz z przełącznikiem trybu i submit()
    sku-control.spec.ts  -> 12 pomiarów (jsdom, zdarzenia syntetyczne)
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
`node_modules/@angular/cli/src/utilities/node-version.js` zmiana `'^22.22.3 || ...'` na
`'^22.14.0 || ...'`; trzeba je powtórzyć po każdym `npm ci`. Przy Node >= 22.22.3 niepotrzebne.

## Realna weryfikacja (ta sesja)

```text
$ npm install --no-audit --no-fund
added 276 packages in 50s

$ npm run build
main-ETXW2OUY.js    | main   | 199.89 kB | 55.36 kB
Application bundle generation complete. [7.223 seconds]

$ npm test
 Test Files  2 passed (2)
      Tests  13 passed (13)
```

Wybrane linie `MEASURE` z trybu verbose:

```text
contract-initial: required:true, pattern:["/^[A-Z]{3}-\\d{4}$/"], maxLength:8, name:"a.form0.sku", errors:["required"]
during-typing:    model:"", controlValue:"abc-1234", dirty:true, touched:false, errors:["required"]
after-blur:       model:"abc-1234", touched:true, errors:["pattern"]
no-touch-after-1s: model:"", touched:false, dirty:true
destroy-flush:    before:"", after:"ABC-1234"
mode-hidden:      visibleOk:false, hiddenOk:true, calls:["''"]
```

Test mutacyjny: usunięcie `debounce(p.sku, 'blur')` ze schematu → padło 5 testów. Po przywróceniu 13/13.

Uwaga: `package-lock.json` został wygenerowany na nowo (kopiowanie lockfile'a z poprzedniego wydania
było zablokowane w środowisku), stąd Angular 22.2.2.

Niezweryfikowane: `ng serve`/przeglądarka (zdarzenia w testach są syntetyczne), Enter w polu wewnątrz
`<form>` w realnej przeglądarce, `FormCheckboxControl`/`ControlValueAccessor` z `debounce('blur')`,
SSR/hydration, `mapResponse()`.
