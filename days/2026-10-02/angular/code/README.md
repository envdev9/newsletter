# Kod do wydania Angular z 02.10.2026 — `transformedValue()` + pełny kontrakt `FormUiControl`

Pełny artykuł: [`../ARTICLE.md`](../ARTICLE.md).

Wymagania: **Node.js** (zweryfikowane na v22.14.0 — zob. sekcja "Uwaga o wersji Node" niżej)
i **npm** (zweryfikowane na 10.9.2). Wersje: `@angular/core`, `@angular/forms` i `@angular/cli`
**22.2.1** (w tym podpakiet `@angular/forms/signals`), TypeScript **6.0.3**, `vitest` **5.0.3**
(jsdom, bez przeglądarki), `rxjs` **7.8.2**.

## Fragment prasówki, którego dotyczy ten kod

> **`transformedValue(value, { parse, format })`** tworzy osobny sygnał "surowego tekstu UI"
> zsynchronizowany z modelem (`number`) przez funkcje `parse`/`format`. Błędny tekst (np. `"abc"`
> zamiast ceny) NIE rzuca wyjątkiem i NIE psuje modelu — `parse()` zwraca `{ error }` zamiast
> `{ value }`, a Signal Forms zgłasza ten błąd na polu **automatycznie**, razem z (niezależnymi)
> błędami walidatorów schematu (np. `min()`) — oba źródła błędów renderują się naraz.
>
> **Pełny kontrakt `FormUiControl`** (nie tylko `value`/`disabled`/`min`/`max` z wydania #7):
> `errors` (błędy renderowane WEWNĄTRZ kontrolka), `touched` (styl po pierwszej interakcji),
> `touch` (wyjście — kontrolka mówi formularzowi "użytkownik skończył interakcję"), `focus()`
> (Signal Forms woła tę metodę zamiast fokusować domyślnie host), `reset()` (wołany, gdy ktoś
> zawoła `fieldState.reset()` na polu lub jego przodku).
>
> **Odkrycie, którego nie dało się przewidzieć z samego `.d.ts`:** `reset()` na własnym
> kontrolku z `transformedValue()` może być PUSTY (poza dowodem w teście) — cofnięcie
> wyświetlanego tekstu do sformatowanej wartości modelu i wyczyszczenie błędu parsowania dzieje
> się SAMO, bo `transformedValue()` wpina się pod `reset()` pola przez wstrzyknięty token
> integracji (`ɵFORM_CONTROL_INTEGRATION`), niezależnie od tego, co (jeśli cokolwiek) kontrolka
> sama robi w swojej metodzie `reset()`. Potwierdzone czytając skompilowane źródło
> `@angular/forms/fesm2022/signals.mjs`, nie tylko typy — i potwierdzone przechodzącym testem.

## Struktura

```
src/app/
  app.ts                     -> host: <app-order-form />
  order-form.ts              -> formularz zamówienia: klient + tablica pozycji
  line-item-schema.ts        -> reużywalna schema<LineItem>() (required/min/max, w tym min(unitPrice, 0.01))
  price-input.ts             -> NOWY własny FormValueControl<number> z transformedValue() (cena "12,50")
  quantity-stepper.ts        -> z wydania #7, DOPISANY pełny kontrakt (errors/touched/touch/focus/reset)
  order-backend.ts           -> fake-backend składania zamówienia (300ms)
  *.spec.ts                  -> 32 testy (Vitest + jsdom)
```

## Jak uruchomić od zera

```bash
cd code
npm ci               # lockfile w repo
npm run build        # = ng build
npm test             # = ng test --no-watch (Vitest + jsdom)
npm start            # = ng serve, http://localhost:4200/ (opcjonalnie, niezweryfikowane - zob. niżej)
```

`node_modules/`, `dist/` i `.angular/` są w `.gitignore`.

**Uwaga:** testy trzeba odpalać przez `ng test`/`npm test`, NIE przez gołe `npx vitest run` —
builder Angulara (`@angular/build:unit-test`) konfiguruje `TestBed`/jsdom przed startem Vitest;
bez tego testy failują od razu z `Need to call TestBed.initTestEnvironment() first`. Sprawdzone
dziś ponownie (ten sam pitfall co w wydaniu #7): `npx vitest run` bezpośrednio dał **29/31
failed**, 4/5 plików testowych czerwonych, dokładnie z tym komunikatem.

### ⚠️ Uwaga o wersji Node w TEJ sesji

Ta sesja miała zainstalowany Node **v22.14.0**. `@angular/cli`/`@angular/build` **22.2.1**
odmawiają startu poniżej `v22.22.3` (twardy check w `bin/ng.js`, nie tylko ostrzeżenie) —
pierwsza próba `ng build` kończyła się błędem:

```text
Node.js version v22.14.0 detected.
The Angular CLI requires a minimum Node.js version of v22.22.3 or v24.15.0 or v26.0.0.
```

W poprzednich wydaniach tej rubryki (#3–#7) środowisko miało Node **v22.23.3** — tu, w tej
konkretnej sesji, było starsze (różnica to pełny **minor** w obrębie v22: 14 vs 22, nie tylko
patch). Sieć była dostępna tylko do rejestru npm (nie do nodejs.org), więc nie dało się pobrać
nowszego Node. Zastosowane obejście, WYŁĄCZNIE lokalnie, żeby faktycznie uruchomić realny
`ng build`/`ng test` (nie zasymulować wyniku): jednolinijkowa zmiana progu wersji w
`node_modules/@angular/cli/src/utilities/node-version.js` (`^22.22.3` → `^22.14.0`) — **plik w
`node_modules/`, nigdy nie trafia do repo** (jest w `.gitignore`), nie jest częścią
dostarczanego kodu. Czytelnik z Node **v22.22.3+** (jak w poprzednich wydaniach) nie potrzebuje
tego obejścia w ogóle. Uczciwie: ten próg w CLI to konserwatywna blokada, nie dowód, że kod
faktycznie wymaga 22.22+ do działania — ale to tylko przypuszczenie, nie coś zweryfikowanego
niezależnie od samego faktu, że build/testy przeszły. Realny `ng build`/`ng test` na tym
środowisku, PO tej jednej zmianie w `node_modules/`, przeszły bez żadnego innego problemu (zob.
"Realna weryfikacja" niżej) — ale to obejście nie było testowane na kodzie, który faktycznie
korzysta z nowszych API `node:` dodanych między 22.14 a 22.22.

## Fragment: pełny kontrakt `FormUiControl` na `PriceInput`

```typescript
// price-input.ts (wycinek)
export class PriceInput implements FormValueControl<number> {
  readonly value = model.required<number>();
  readonly disabled = input<boolean>(false);
  readonly errors = input<readonly ValidationError.WithOptionalFieldTree[]>([]);
  readonly touched = input<boolean>(false);
  readonly touch = output<void>();

  protected readonly rawValue = transformedValue(this.value, {
    parse: (raw: string): ParseResult<number> => {
      const trimmed = raw.trim();
      if (trimmed === '') return { error: { kind: 'price-required', message: 'Podaj cenę' } };
      const normalized = trimmed.replace(/\s/g, '').replace(',', '.');
      const parsed = Number(normalized);
      if (!Number.isFinite(parsed)) {
        return { error: { kind: 'price-parse', message: `"${raw}" nie jest poprawną ceną (np. 12,50)` } };
      }
      if (parsed < 0) return { error: { kind: 'price-negative', message: 'Cena nie może być ujemna' } };
      return { value: Math.round(parsed * 100) / 100 };
    },
    format: (value) => formatPrice(value),
  });

  focus(options?: FocusOptions): void {
    this.nativeInputRef().nativeElement.focus(options);
  }

  reset(): void {
    // Pusto poza dowodem w teście - cofnięcie tekstu dzieje się samo (zob. wyżej).
  }
}
```

## Realna weryfikacja (`npm ci` + `ng build` + `ng test`, czysty katalog, ta sesja)

```text
$ npm ci --no-audit --no-fund
added 274 packages in 10s

$ npm run build
main-6FJJMCSX.js    | main    | 218.75 kB | 60.69 kB
styles-5INURTSO.css | styles  |   0 bytes |  0 bytes
Application bundle generation complete. [7.947 seconds]

$ npm test
 Test Files  5 passed (5)
      Tests  32 passed (32)
   Duration  3.60s
```

32 testy w 5 plikach: `order-backend.spec.ts` (2), `price-input.spec.ts` (10 — formatowanie,
parsowanie poprawnej/błędnej/ujemnej/pustej ceny, render `errors`/`touched` z zewnątrz, `touch`
na blur, `focus()`, `reset()`), `quantity-stepper.spec.ts` (9 — stare testy z wydania #7 +
`touch` na klik, `errors`/`touched`, `focus()`, `reset()`), `order-form.spec.ts` (10 — w tym:
błąd schematu i błąd parsowania naraz na jednym polu, auto-format po zmianie z zewnątrz,
`focusBoundControl()` trafia do własnego `<input>`, `resetRow()` cofa błędny tekst bez
dopisywania czegokolwiek w `reset()` kontrolka, pełny submit + blokada współbieżnego submit),
`app.spec.ts` (1). Zero poprawek po drodze — wszystkie testy przeszły za pierwszym
uruchomieniem.

Wypróbuj ręcznie (jeśli masz `ng serve` pod ręką — ja nie miałem, zob. artykuł): wpisz w pole
ceny coś bez sensu (np. `abc`) i zobacz błąd parsowania OBOK błędu "cena musi być większa od
zera" (oba na raz), popraw na `15,5` i zobacz, że oba znikają, a "Wartość" wiersza i "Razem" się
przeliczają; kliknij "Fokus na cenę" i zobacz, że fokus realnie trafia do pola ceny tego wiersza;
wpisz coś błędnego, kliknij "Resetuj wiersz" i zobacz, jak tekst sam wraca do `0,00`.

Niezweryfikowane: `ng serve`/przeglądarka, `validateHttp`, SSR/hydration, `tapResponse`
z `@ngrx/operators`.
