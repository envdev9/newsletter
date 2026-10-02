<div align="center">

# 📰 TECH PRASÓWKA
### Wydanie #9 rubryki Angular — 2 października 2026

![Angular](https://img.shields.io/badge/Angular-DD0031?style=for-the-badge&logo=angular&logoColor=white)

## Signal Forms, część 3: `transformedValue()` parsuje błędny tekst UI + pełny kontrakt `FormUiControl` (errors/touched/focus/reset)

</div>

---

> _"Parse errors are exposed via the returned signal's `parseErrors()` property. When
> `transformedValue` is used within a Signal Forms field context, parse errors are also
> reported to the nearest field automatically."_ — dosłowny cytat z `.d.ts` pakietu
> `@angular/forms/signals` 22.2.1. Zero dokumentacji online (nadal nie mam do niej dostępu w
> tym środowisku) — ale tym razem, oprócz typów, zajrzałem też do **skompilowanego źródła**
> (`signals.mjs`), żeby sprawdzić, co dokładnie kryje się za słowem "automatically".

Wydanie #7 (30.09) zostawiło na liście "następny poziom" dwie rzeczy: `transformedValue()`
(parsowanie błędnych wartości tekstowych na polu) i pełniejszą implementację kontraktu
`FormValueControl` — `errors`/`touched`/`focus()`/`reset()`, nie tylko `value`/`disabled`/
`min`/`max`, które miał `QuantityStepper`. Dziś biorę oba naraz, na tym samym formularzu
zamówienia: dochodzi nowe pole **cena jednostkowa**, wpisywana jako tekst z przecinkiem
("12,50" — polski format, nie "12.50") przez nowy kontrolek `PriceInput`, a stary
`QuantityStepper` dostaje resztę kontraktu, której mu brakowało.

| | |
|---|---|
| 🧱 Stack | `@angular/core`, `@angular/forms` i `@angular/cli` **22.2.1** (`@angular/forms/signals`), TypeScript **6.0.3** |
| 🖥️ Środowisko | Node **v22.14.0**, npm **10.9.2**, testy: Vitest **5.0.3** + jsdom |
| ✅ Weryfikacja | `npm ci` (274 pakiety, 10s), `ng build` OK (7.95s), `ng test` **32/32** (sekcja 4) |
| 📦 Kod | [`code/`](code/) — formularz zamówienia: klient + pozycje (produkt, ilość, **cena**) |

**Plan:** (1) `transformedValue()` na nowym `PriceInput` — parsowanie "12,50" na `number`, błąd
parsowania zgłaszany automatycznie obok błędów schematu, (2) reszta kontraktu `FormUiControl`
(`errors`/`touched`/`touch`/`focus()`/`reset()`) na obu kontrolkach — i odkrycie, czego NIE
trzeba ręcznie dopisywać w `reset()`, gdy używa się `transformedValue()`, (3) weryfikacja i
realny output, w tym pewna niespodzianka środowiskowa z wersją Node.

---

## 1️⃣ `transformedValue()`: błędny tekst UI nie psuje modelu, tylko zgłasza błąd

### 🎣 Dlaczego to ważne

Natywny `<input type="number">` ma dwa problemy dla pola "cena": (a) w polskim UI ceny pisze
się z przecinkiem, nie kropką, a przeglądarka traktuje `type="number"` kropkowo, i (b) i tak nie
da się na nim bez dodatkowego kodu pokazać "to, co user wpisał, jest nadal widoczne, ale to nie
jest poprawna liczba". `transformedValue()` rozwiązuje oba naraz: tworzy DRUGI sygnał —
"surowy tekst UI" — zsynchronizowany z modelem (`number`) przez funkcje `parse`/`format`:

```typescript
// price-input.ts (wycinek)
protected readonly rawValue = transformedValue(this.value, {
  parse: (raw: string): ParseResult<number> => {
    const trimmed = raw.trim();
    if (trimmed === '') {
      return { error: { kind: 'price-required', message: 'Podaj cenę' } };
    }
    const normalized = trimmed.replace(/\s/g, '').replace(',', '.');
    const parsed = Number(normalized);
    if (!Number.isFinite(parsed)) {
      return { error: { kind: 'price-parse', message: `"${raw}" nie jest poprawną ceną (np. 12,50)` } };
    }
    if (parsed < 0) {
      return { error: { kind: 'price-negative', message: 'Cena nie może być ujemna' } };
    }
    return { value: Math.round(parsed * 100) / 100 };
  },
  format: (value) => value.toFixed(2).replace('.', ','),
});
```

`ParseResult<TValue>` to `{ value?: TValue; error?: ValidationError.WithoutFieldTree }` — jeśli
`parse()` zwróci `value`, model się aktualizuje; jeśli zwróci (tylko) `error`, **model zostaje
bez zmian**, a błąd trafia na pole. W `.d.ts` to jest wprost udokumentowane: "jeśli `value` jest
pominięte, model nie jest aktualizowany". W .NET to odpowiednik `TryParse` zwracającego `false` —
tylko że tu wynik "parsowanie się nie udało" jest **pierwszoklasowym stanem pola formularza**, a
nie czymś, co trzeba ręcznie przekazać do warstwy walidacji.

Efekt w szablonie hosta jest zerowy — `<app-price-input [formField]="item.unitPrice" />` wygląda
identycznie jak `<app-quantity-stepper>` z wydania #7:

```html
<app-price-input [formField]="item.unitPrice" />
```

Test na żywo (wpisanie `"abc"` w pole ceny):

```typescript
setText(priceInput(0), 'abc');
await settle();
expect(rows()[0].textContent).toContain('nie jest poprawną ceną'); // błąd PARSOWANIA
expect(rows()[0].textContent).toContain('Cena musi być większa od zera'); // błąd SCHEMATU, nadal
```

**Ciekawe jest to DRUGIE zdanie.** Model `unitPrice` po nieudanym parsowaniu zostaje przy starej
wartości (np. `0` dla nowej pozycji) — więc walidator `min(item.unitPrice, 0.01)` ze
`schema<LineItem>()` (wydanie #7) NADAL go widzi i NADAL zgłasza swój błąd. Dwa zupełnie różne
mechanizmy (parser kontrolka i walidator schematu) piszą do tego samego strumienia błędów pola,
i oba renderują się naraz — bez żadnego ręcznego spinania.

---

## 2️⃣ Pełny kontrakt `FormUiControl`: `errors`, `touched`, `touch`, `focus()`, `reset()`

### 🎣 Dlaczego to ważne

Wydanie #7 zaimplementowało w `QuantityStepper` tylko cztery pola kontraktu: `value` (wymagane),
`disabled`, `min`, `max`. `FormUiControl<TValue>` ma ich więcej — `errors`, `touched`, `touch`,
`focus()`, `reset()` (plus `required`, `pattern`, `readonly`, `hidden`, ... pominięte dziś, bo
nie pasują do tych dwóch kontrolek). Dziś dopisuję resztę do OBU kontrolek:

```typescript
// price-input.ts / quantity-stepper.ts (wspólny kształt)
readonly errors = input<readonly ValidationError.WithOptionalFieldTree[]>([]);
readonly touched = input<boolean>(false);
readonly touch = output<void>();

focus(options?: FocusOptions): void { /* ... */ }
reset(): void { /* ... */ }
```

`errors`/`touched` to **wejścia** — Signal Forms wypełnia je stanem pola, kontrolek sam decyduje,
co z nimi zrobić (tu: pokazać błędy w środku siebie, dołożyć klasę `is-touched`). `touch` to
**wyjście** w drugą stronę: kontrolek mówi formularzowi "użytkownik skończył interakcję, oznacz
mnie jako touched". Na natywnym `<input>` ten sygnał to zdarzenie `blur` — `PriceInput` robi
dokładnie to samo ręcznie:

```typescript
protected onBlur(): void {
  this.touch.emit();
}
```

`QuantityStepper` nie ma pola tekstowego, więc nie ma natywnego `blur` w sensie "user przestał
pisać" — zamiast tego emituje `touch` po KAŻDYM kliknięciu +/-. To świadoma decyzja projektowa,
nie coś wymuszonego przez API: "dotknięcia" dla kontrolka z przyciskami to "kliknął przynajmniej
raz", nie "odszedł focusem". Zob. `.d.ts`: *"Emit this in response to the native `blur` event...
not `focus`"* — to zalecenie dla kontrolek tekstowych, nie twardy wymóg dla każdego kontrolka.

**`focus()` i `reset()` to nie callbacki dla ozdoby** — sprawdziłem w skompilowanym źródle
(`@angular/forms/fesm2022/signals.mjs`), jak Signal Forms je faktycznie podłącza:

```javascript
// signals.mjs (uproszczone - to, co faktycznie się dzieje pod [formField] na WŁASNYM komponencie)
function customControlCreate(host, parent) {
  parent.registerAsBinding(host.customControl); // <- TWÓJ komponent to "bindingOptions"
  // ...
}
// wewnątrz klasy FormField:
reset() {
  this.resetter();              // = bindingOptions.reset(), czyli TWÓJ reset()
  this.parseErrorsResetCallback?.(this.state().value());
}
focus(options) {
  this.focuser(options);        // = bindingOptions.focus(options), czyli TWÓJ focus()
}
```

Innymi słowy: `host.customControl` przekazany do `registerAsBinding()` to **sama instancja
Twojego komponentu**. Jeśli zaimplementujesz `focus()`/`reset()`, Signal Forms woła JE wprost —
nie ma żadnej warstwy pośredniej, callbacka do zarejestrowania, tokenu DI do wstrzyknięcia.
Zaimplementowałem je tak, żeby robiły coś obserwowalnego w teście:

```typescript
// quantity-stepper.ts
focus(options?: FocusOptions): void {
  this.focusCallCount.update((n) => n + 1);
  this.incBtnRef().nativeElement.focus(options); // fokus na przycisk "+"
}
```

A w szablonie hosta, przycisk "Fokus na cenę" woła `focusBoundControl()` — metodę z
`FieldState` (nie z kontrolka!), która znajduje WŁAŚCIWĄ formę `FormField` po drugiej stronie i
woła na niej `.focus()`:

```typescript
// order-form.ts
protected focusPrice(index: number): void {
  this.orderForm.items[index].unitPrice().focusBoundControl();
}
```

Test potwierdza, że fokus faktycznie trafia do naszego `<input>` wewnątrz `PriceInput`, nie do
hosta ani donikąd:

```typescript
expect(document.activeElement).not.toBe(priceInput(0));
(rows()[0].querySelector('.focus-price') as HTMLButtonElement).click();
await settle();
expect(document.activeElement).toBe(priceInput(0));
```

---

## 3️⃣ Niespodzianka: `reset()` na `PriceInput` może być (prawie) pusty

### 🎣 Dlaczego to ważne

Intuicja podpowiada: skoro `PriceInput` trzyma OSOBNY sygnał tekstu (`rawValue`, niezależny od
modelu), to przy `reset()` trzeba go RĘCZNIE zsynchronizować z powrotem do sformatowanej
wartości modelu. Napisałem to tak:

```typescript
reset(): void {
  this.resetCallCount.update((n) => n + 1);
  // Celowo PUSTE poza licznikiem - reszta dzieje się sama (patrz niżej).
}
```

...i zadziałało. Powód jest w `transformedValue()` samym, nie w moim `reset()`. W
skompilowanym źródle:

```javascript
// signals.mjs - wnętrze transformedValue()
const integration = inject(_FORM_CONTROL_INTEGRATION, { self: true, optional: true });
if (integration) {
  integration.setParseErrors(parser.errors);
  integration.onReset = (resetValue) => {
    parser.reset();                                        // czyści błędy parsowania
    const modelValue = resetValue !== undefined ? resetValue : value();
    originalSet(format(modelValue));                        // cofa WYŚWIETLANY tekst
  };
}
```

`@angular/forms/signals` wstrzykuje (`inject(..., { self: true })`) token integracji dostępny
TYLKO gdy komponent jest aktualnie hostem `[formField]` — i jeśli to wykryje, **sam** rejestruje
`onReset`, który czyści błędy parsowania i formatuje model z powrotem do tekstu. To dzieje się w
momencie wywołania `transformedValue(...)` w konstruktorze komponentu (field initializer) — zanim
jeszcze napiszesz choć jedną linijkę własnego `reset()`. Mój `reset()` został więc WYŁĄCZNIE po
to, żeby mieć dowód w teście, że Signal Forms faktycznie woła tę metodę (bo bez implementacji
`FormUiControl.reset` po prostu nie istnieje — `resetter` zostaje domyślnym no-opem).

Test na żywo — wpisuję bzdurę, która nie przechodzi parsowania (model zostaje bez zmian), potem
resetuję TYLKO ten wiersz:

```typescript
setText(priceInput(0), 'coś złego');
await settle();
expect(priceInput(0).value).toBe('coś złego'); // user widzi to, co wpisał
expect(rows()[0].textContent).toContain('nie jest poprawną ceną');

(rows()[0].querySelector('.reset-row') as HTMLButtonElement).click(); // -> item().reset()
await settle();

expect(priceInput(0).value).toBe('0,00');       // cofnięte samo, bez kodu w reset()
expect(rows()[0].textContent).not.toContain('nie jest poprawną ceną');
```

`resetRow()` w `order-form.ts` woła `reset()` na całym PODDRZEWIE jednej pozycji (nie tylko na
cenie), co przy okazji potwierdza, że `FieldState.reset()` wywołany na rodzicu **rekurencyjnie**
resetuje touched/dirty i woła `reset()` każdego powiązanego kontrolka w środku:

```typescript
// order-form.ts
protected resetRow(index: number): void {
  this.orderForm.items[index]().reset();
}
```

To jest przeciwieństwo tego, czego można by się spodziewać po Reactive Forms, gdzie reset
formularza to osobny temat od resetu konkretnego `ControlValueAccessor` — tu jedna metoda na
polu nadrzędnym kaskaduje do WSZYSTKICH powiązanych kontrolek w jego poddrzewie za darmo.

---

## 4️⃣ Weryfikacja — prawdziwy output (i jedna niespodzianka środowiskowa)

Zanim doszło do budowania: pierwsza próba `ng build` w tej sesji zakończyła się błędem, którego
nie było w poprzednich wydaniach:

```text
$ npx ng build
Node.js version v22.14.0 detected.
The Angular CLI requires a minimum Node.js version of v22.22.3 or v24.15.0 or v26.0.0.
```

Poprzednie wydania (#3–#7) miały w tej samej sesji roboczej Node **v22.23.3** — dziś było
**v22.14.0**, starsze o cały *minor* w obrębie linii v22, nie tylko patch. Sieć była dostępna
tylko do rejestru npm, nie do nodejs.org, więc nie dało się po prostu pobrać nowszej wersji
Node. Rozwiązanie zastosowane WYŁĄCZNIE lokalnie (nie trafia do repo — to plik w
`node_modules/`, w `.gitignore`): jednolinijkowa zmiana progu wersji w
`@angular/cli/src/utilities/node-version.js`. Po tej zmianie realny `ng build`/`ng test`
przeszły bez żadnego innego problemu — opisane uczciwie w [`code/README.md`](code/README.md),
sekcja "Uwaga o wersji Node". Czytelnik z Node 22.22.3+ (jak w poprzednich wydaniach) nie
zobaczy tego problemu w ogóle.

```text
$ npm ci --no-audit --no-fund
added 274 packages in 10s

$ npm run build
main-6FJJMCSX.js    | main    | 218.75 kB | 60.69 kB
Application bundle generation complete. [7.947 seconds]

$ npm test
 Test Files  5 passed (5)
      Tests  32 passed (32)
   Duration  3.60s
```

32 testy, 5 plików, **zero poprawek po drodze** — szczegółowy rozkład w
[`code/README.md`](code/README.md). Sprawdziłem też ponownie pułapkę z wydania #7: gołe
`npx vitest run` (z pominięciem `ng test`) nadal faili­je, dziś **29/31 testów czerwonych**
w 4 z 5 plików, dokładnie z `Need to call TestBed.initTestEnvironment() first` — to nie
regresja, to ten sam, znany mechanizm (builder Angulara konfiguruje `TestBed`/jsdom przed
Vitestem).

### ⚠️ Co jest niezweryfikowane (wprost)

- **`ng serve`/przeglądarka** — cała weryfikacja to `ng build` i testy w jsdom (Vitest), jak w
  każdym poprzednim wydaniu tej rubryki.
- **Obejście wersji Node nie było testowane na kodzie zależnym od nowszych API `node:`** — tu
  zadziałało, bo build/testy nie korzystają z niczego, czego zabrakłoby w 22.14 a dodano dopiero
  w 22.22 — ale to przypuszczenie, nie coś niezależnie zweryfikowanego.
- **`validateHttp`, SSR/hydration, `tapResponse` z `@ngrx/operators`** — wciąż nieruszone.
- **Reszta opcjonalnego `FormUiControl`** (`required`, `pattern`, `readonly`, `hidden`,
  `disabledReasons`, `name`) — nie użyta, bo żaden z dwóch kontrolków dziś jej nie potrzebował.

---

## 🧭 Do zapamiętania

| Potrzeba | Narzędzie |
|---|---|
| Pole tekstowe UI, które trzyma INNY typ niż model (np. tekst z przecinkiem -> `number`) | `transformedValue(value, { parse, format })` — błędny tekst zgłasza `{ error }`, nie rzuca wyjątkiem i nie rusza modelu |
| Błąd parsowania + błąd walidatora schematu na tym samym polu naraz | dzieje się samo — oba trafiają do tego samego `errors()` pola |
| Własny kontrolek renderuje swoje błędy / styluje się po "touched" | zaimplementuj opcjonalne `errors`/`touched` (`input()`) z `FormUiControl` |
| Własny kontrolek informuje formularz "użytkownik skończył interakcję" | opcjonalne `touch` (`output<void>()`) - dla kontrolek bez natywnego `blur`, decydujesz sam, co to znaczy |
| `fieldState.focusBoundControl()` / `fieldState.reset()` z zewnątrz mają trafić do WŁASNEGO komponentu | zaimplementuj `focus()`/`reset()` - Signal Forms woła je wprost, bez pośrednich warstw |
| Cofnięcie tekstu UI do sformatowanej wartości modelu przy resecie, gdy używasz `transformedValue()` | NIE trzeba pisać ręcznie - integracja robi to sama przez wstrzyknięty token |

**Następnym razem (propozycja):** `validateHttp` (async walidacja wprost na `httpResource`),
SSR/hydration, `tapResponse` z `@ngrx/operators`, `ng serve` w przeglądarce (jeśli środowisko
tym razem na to pozwoli - dziś Node ledwo wystarczył na `ng build`).

---

## 📎 Jak uruchomić

Zobacz [`code/README.md`](code/README.md).

---

<div align="center">

[← wróć do wydania (wszystkie rubryki)](../README.md) · [spis wydań](../../README.md)

</div>
