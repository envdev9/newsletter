# Kod do wydania Angular z 30.09.2026 — `applyEach()` + reużywalna `schema()` + własny `FormValueControl`

Pełny artykuł: [`../ARTICLE.md`](../ARTICLE.md).

Wymagania: **Node.js 20+** (weryfikowane na v22.23.3) i **npm** (weryfikowane na 10.9.9).
Wersje: `@angular/core` i `@angular/forms` **22.2.0** (w tym podpakiet `@angular/forms/signals`),
TypeScript **6.0.3**, `vitest` **5.0.2** (jsdom, bez przeglądarki).

## Fragment prasówki, którego dotyczy ten kod

> **`schema<T>(fn)`** tworzy nazwaną, wielokrotnego użytku definicję reguł dla typu `T`
> (np. `LineItem`), niezależną od konkretnego pola. **`applyEach(f.tablica, schemaT)`**
> nakłada tę schemę na KAŻDY element tablicy — dodanie/usunięcie elementu to zwykły
> `signal.update()` na modelu, bez rejestrowania/wyrejestrowywania walidatorów ręcznie
> (odpowiednik `RuleForEach()` z FluentValidation w .NET, ale reaktywnie).
>
> **`FormValueControl<TValue>`** to kontrakt (nie klasa bazowa, nie DI), który pozwala
> podłączyć WŁASNY komponent pod `[formField]` dokładnie tak samo jak natywny `<input>`.
> Jedyne wymagane pole: `value: ModelSignal<TValue>`. Reszta (`disabled`, `min`, `max`,
> `errors`, `touched`, ...) to opcjonalne `input()`, które `[formField]` wypełnia samo z
> aktualnego stanu pola — bez `ControlValueAccessor`/`NG_VALUE_ACCESSOR` znanych z
> Reactive Forms.
>
> **`min`/`max`** przekazane do własnego kontrolka pochodzą automatycznie z walidatorów
> `min()`/`max()` zadeklarowanych w schemie pola — nie z ręcznego `[min]="..."` w szablonie
> hosta. Jedno źródło prawdy (schema), dowolny UI korzysta z niego za darmo.
>
> **`submit()`** blokuje wywołania współbieżne — potwierdzone dziś działającym testem
> (`order-form.spec.ts`, „współbieżny submit”), nie tylko cytatem z `.d.ts`: drugie
> zdarzenie `submit` w trakcie trwającej wysyłki NIE odpala `action` ponownie.

## Struktura

```
src/app/
  app.ts                     -> host: <app-order-form />
  order-form.ts              -> formularz zamówienia: klient + tablica pozycji (applyEach)
  line-item-schema.ts        -> reużywalna schema<LineItem>() (required/min/max)
  quantity-stepper.ts        -> własny FormValueControl<number> - przyciski +/- zamiast <input>
  order-backend.ts           -> fake-backend składania zamówienia (300ms)
  *.spec.ts                  -> 15 testów (Vitest + jsdom)
```

## Jak uruchomić od zera

```bash
cd code
npm ci               # lockfile w repo
npm run build        # = ng build
npm test             # = ng test --no-watch (Vitest + jsdom)
npm start            # = ng serve, http://localhost:4200/ (opcjonalnie, niezweryfikowane)
```

`node_modules/`, `dist/` i `.angular/` są w `.gitignore`.

**Uwaga:** testy trzeba odpalać przez `ng test`/`npm test`, NIE przez gołe `npx vitest run` —
builder Angulara (`@angular/build:unit-test`) konfiguruje `TestBed`/jsdom przed startem
Vitest; bez tego testy Signal Forms/komponentów failują od razu z `Need to call
TestBed.initTestEnvironment() first`.

## Realna weryfikacja

```text
$ npm ci --no-audit --no-fund
added 274 packages in 11s

$ npm run build
main-Y5L3PYNB.js    | main    | 207.76 kB |  57.67 kB
Application bundle generation complete. [8.066 seconds]

$ npm test
 Test Files  4 passed (4)
      Tests  15 passed (15)
   Duration  3.25s
```

Wypróbuj ręcznie (jeśli akurat masz `ng serve` pod ręką, ja nie miałem — patrz artykuł,
sekcja "co niezweryfikowane"): dodaj kilka pozycji przyciskiem „+ dodaj pozycję”, zmień
ilość przyciskami stepperа, spróbuj zejść ilością do zera (przycisk „−” zablokuje się na
`1`, bo `lineItemSchema` ma `min(item.quantity, 1)`), zostaw pustą nazwę produktu w którymś
wierszu i zobacz błąd tylko przy TYM wierszu (reszta niezależna, dzięki `applyEach`).

Niezweryfikowane: `ng serve`/przeglądarka, pełna implementacja `FormUiControl` (`errors`,
`touched`, `focus()`) na `QuantityStepper`, `transformedValue()`, `validateHttp`,
SSR/hydration, `tapResponse`.
