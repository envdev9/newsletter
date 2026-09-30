<div align="center">

# 📰 TECH PRASÓWKA
### Wydanie #7 rubryki Angular — 30 września 2026

![Angular](https://img.shields.io/badge/Angular-DD0031?style=for-the-badge&logo=angular&logoColor=white)

## Signal Forms, część 2: tablica pól przez `applyEach()` + własny `FormValueControl` zamiast `<input>`

</div>

---

> _"A `FormField` placed on a custom control (`FormUiControl`) automatically registers that
> custom control as a binding."_ — dosłowny cytat z `.d.ts` pakietu `@angular/forms/signals`
> (nie z dokumentacji online — do tej mam nadal zerowy dostęp w tym środowisku). Innymi słowy:
> `[formField]` nie wie i nie musi wiedzieć, czy pod spodem jest `<input>`, czy Twój własny
> komponent Angulara. Wystarczy kontrakt.

Wydanie #5 (28.09) pokazało Signal Forms na pojedynczym, płaskim formularzu: `form()`,
walidatory sync, `[formField]`/`[formRoot]`, walidacja async przez `resource()`, błąd
"z serwera" na konkretnym polu. Na liście "następny poziom" zostały m.in. `applyEach`/`schema()`
wielokrotnego użytku i własny `FormValueControl`. Dziś biorę oba naraz, bo w praktyce idą w
parze: **tablica powtarzalnych wierszy formularza to dokładnie miejsce, w którym reużywalna
schema i własny kontrolek najbardziej się opłacają.** Przykład: formularz zamówienia z
dynamiczną listą pozycji (produkt + ilość), gdzie ilość edytuje się przyciskami +/− zamiast
przez `<input type="number">`.

| | |
|---|---|
| 🧱 Stack | `@angular/core` i `@angular/forms` **22.2.0** (`@angular/forms/signals`), TypeScript **6.0.3** |
| 🖥️ Środowisko | Node **v22.23.3**, npm **10.9.9**, testy: Vitest **5.0.2** + jsdom |
| ✅ Weryfikacja | `npm ci` (274 pakiety, ok. 11 s), `ng build` OK (8.07 s), `ng test` **15/15** (sekcja 5) |
| 📦 Kod | [`code/`](code/) — formularz zamówienia: klient + tablica pozycji, własny stepper ilości |

**Plan:** (1) `schema<T>()` wydzielona do osobnego pliku + `applyEach()` na tablicy pól, bez
rejestrowania/wyrejestrowywania niczego ręcznie przy dodawaniu/usuwaniu wierszy, (2) kontrakt
`FormValueControl<TValue>` — własny komponent zamiast `<input>`, wpięty w `[formField]`
dokładnie tak samo, (3) automatyczne przekazanie `min`/`max` z walidatorów schemy do inputów
własnego kontrolka — bez ręcznego wiązania w szablonie hosta, (4) test na żywo blokady
współbieżnego `submit()` — rzecz, którą w wydaniu #5 zostawiłem jako "niezweryfikowane", dziś
potwierdzona przechodzącym testem, (5) weryfikacja i realny output.

---

## 1️⃣ Reużywalna `schema()` + `applyEach()`: jedna walidacja, dowolna liczba wierszy

### 🎣 Dlaczego to ważne

W wydaniu #5 walidatory (`required`, `minLength`, ...) były wołane bezpośrednio wewnątrz
funkcji przekazanej do `form()` — dobre dla płaskiego formularza, nie skaluje się na tablicę
o zmiennej długości. `@angular/forms/signals` ma na to dedykowaną parę funkcji: `schema<T>()`
tworzy **nazwany, wielokrotnego użytku** opis reguł dla typu `T` (nie dla konkretnego pola), a
`applyEach()` nakłada go na **każdy** element tablicy:

```typescript
// line-item-schema.ts
import { max, min, required, schema } from '@angular/forms/signals';

export interface LineItem {
  productName: string;
  quantity: number;
}

export const lineItemSchema = schema<LineItem>((item) => {
  required(item.productName, { message: 'Nazwa produktu jest wymagana' });
  min(item.quantity, 1, { message: 'Ilość musi być co najmniej 1' });
  max(item.quantity, 99, { message: 'Ilość nie może przekraczać 99' });
});
```

```typescript
// order-form.ts
const orderForm = form(this.model, (f) => {
  required(f.customerName, { message: 'Nazwa klienta jest wymagana' });
  applyEach(f.items, lineItemSchema);
});
```

To jest dokładny odpowiednik `RuleForEach()` z FluentValidation w .NET (`RuleForEach(x =>
x.Items).SetValidator(new LineItemValidator())`) — z jedną różnicą, która w praktyce dużo
zmienia: dodanie albo usunięcie elementu tablicy to **zwykły `signal.update()` na modelu**,
nic więcej.

```typescript
protected addItem(): void {
  this.model.update((m) => ({ ...m, items: [...m.items, emptyLineItem()] }));
}

protected removeItem(index: number): void {
  this.model.update((m) => ({ ...m, items: m.items.filter((_, i) => i !== index) }));
}
```

Żadnego `FormArray.push(this.fb.group(...))`, żadnego ręcznego `removeAt(i)` synchronizowanego
z osobną tablicą danych jak w Reactive Forms — `applyEach` jest zadeklarowany raz, przy
budowie `orderForm`, i obowiązuje dla każdego elementu, który w danej chwili istnieje w
modelu, bez względu na to, ile ich jest. W szablonie tablica pól iteruje się wprost przez
`@for`, bo `orderForm.items` (typ `FieldTree<LineItem[]>`) jest jednocześnie iterowalny:

```html
@for (item of orderForm.items; track $index; let i = $index) {
  <input type="text" [formField]="item.productName" />
  <!-- item.quantity niżej, sekcja 2 -->
}
```

`item` w pętli to gotowy `FieldTree<LineItem>` tego konkretnego wiersza — `item.productName`
i `item.quantity` działają identycznie jak pola formularza płaskiego z wydania #5.

---

## 2️⃣ Własny `FormValueControl`: `[formField]` na komponencie, nie na `<input>`

### 🎣 Dlaczego to ważne

Ilość w każdym wierszu edytuje się nie przez `<input type="number">`, tylko przez własny
komponent `<app-quantity-stepper>` z przyciskami +/−. W Reactive Forms taki kontrolek wymaga
zaimplementowania `ControlValueAccessor` — czterech metod (`writeValue`, `registerOnChange`,
`registerOnTouched`, opcjonalnie `setDisabledState`) i ręcznego dostawcy `NG_VALUE_ACCESSOR`.
W Signal Forms kontrakt jest jeden, strukturalny (nie DI), i w praktyce jednopolowy —
`FormValueControl<TValue>` z `@angular/forms/signals`:

```typescript
interface FormValueControl<TValue> extends FormUiControl<TValue> {
  readonly value: ModelSignal<TValue>;   // jedyne pole WYMAGANE
  readonly checked?: undefined;          // musi NIE być zdefiniowane (to kontrakt checkboxa)
}
```

`FormUiControl<TValue>` (wspólna baza) dokłada same **opcjonalne** `input()`-y: `disabled`,
`readonly`, `min`, `max`, `errors`, `touched`, `required`, `pattern`, ... — jeśli je
zaimplementujesz, `[formField]` sam je wypełni z aktualnego stanu pola. Cały mój
`QuantityStepper` (bez importu ani wzmianki o Signal Forms w środku — kontrakt jest czysto
strukturalny, "duck typing" na poziomie typów):

```typescript
// quantity-stepper.ts
import { Component, input, model } from '@angular/core';
import type { FormValueControl } from '@angular/forms/signals';

@Component({
  selector: 'app-quantity-stepper',
  template: `
    <div class="stepper" [class.is-disabled]="disabled()">
      <button type="button" class="step-btn" (click)="decrement()"
              [disabled]="disabled() || !canDecrement()">−</button>
      <span class="qty-value">{{ value() }}</span>
      <button type="button" class="step-btn" (click)="increment()"
              [disabled]="disabled() || !canIncrement()">+</button>
    </div>
  `,
})
export class QuantityStepper implements FormValueControl<number> {
  readonly value = model.required<number>();
  readonly disabled = input<boolean>(false);
  readonly min = input<number | undefined>(undefined);
  readonly max = input<number | undefined>(undefined);

  protected canDecrement(): boolean {
    return this.min() === undefined || this.value() > this.min()!;
  }
  protected canIncrement(): boolean {
    return this.max() === undefined || this.value() < this.max()!;
  }
  protected increment(): void {
    if (this.canIncrement()) this.value.update((v) => v + 1);
  }
  protected decrement(): void {
    if (this.canDecrement()) this.value.update((v) => v - 1);
  }
}
```

A w szablonie hosta różnica względem natywnego pola to wyłącznie nazwa tagu:

```html
<app-quantity-stepper [formField]="item.quantity" />
```

`[formField]` widzi, że `QuantityStepper` ma `value: ModelSignal<number>` i sam się do niego
podłącza dwukierunkowo — kliknięcie +/− zmienia `value`, `value` zmienia model formularza
(`item.quantity`), i odwrotnie: zewnętrzna zmiana `item.quantity().value.set(...)` odświeża
przyciski. Dokładnie tak samo, jak `[formField]` na `<input>` robi to przez `value`/`input`
DOM-owe, tylko że tu nośnikiem jest `model()`, standardowy mechanizm dwukierunkowego
bindowania Angulara od 17.2 wzwyż — nie coś specyficznego dla formularzy.

---

## 3️⃣ `min`/`max` trafiają do kontrolka same — z tej samej schemy, nie z szablonu

### 🎣 Dlaczego to ważne

Nigdzie w `order-form.ts` nie ma `[min]="1"` ani `[max]="99"` na `<app-quantity-stepper>`.
Te wartości pochodzą z walidatorów `min(item.quantity, 1)` / `max(item.quantity, 99)`
zadeklarowanych w `lineItemSchema` (sekcja 1) — `[formField]` czyta je z metadanych pola i
wstrzykuje we `input()`-y `min`/`max` kontrolka automatycznie, bo `QuantityStepper` je
zadeklarował jako część `FormUiControl`. Efekt widać na granicach: nowa pozycja startuje z
ilością `1`, więc przycisk "−" jest zablokowany **od razu**, zanim użytkownik cokolwiek
kliknie — sprawdzone testem (sekcja 5), nie na oko:

```typescript
// order-form.spec.ts
expect(stepperButtons(0)[0].hasAttribute('disabled')).toBe(true); // "−" na starcie
```

To ta sama różnica co w .NET między walidacją rozproszoną po widoku (atrybuty HTML wpisywane
ręcznie w każdym miejscu, gdzie pole się pojawia) a jednym źródłem prawdy (adnotacje na
modelu/DTO, np. `[Range(1, 99)]`) — tu źródłem prawdy jest `lineItemSchema`, a UI (dowolny,
także customowy) dostaje z niej ograniczenia za darmo.

---

## 4️⃣ Zweryfikowane na żywo: `submit()` faktycznie blokuje wywołania współbieżne

### 🎣 Dlaczego to ważne

Wydanie #5 zostawiło to jako "niezweryfikowane": dokumentacja API `submit()` twierdzi, że
"concurrent submissions are prohibited" — drugie wywołanie w trakcie trwającej submisji ma
zwrócić `false` natychmiast, bez odpalania `action`. Dziś to sprawdzone realnym testem: dwa
zdarzenia `submit` na `<form [formRoot]>` wystrzelone jedno po drugim, zanim pierwsze zdążyło
się rozwiązać (fake-backend ma 300 ms opóźnienia):

```typescript
submitForm(); // pierwszy submit rusza (300ms w toku)
await settle();
submitForm(); // drugi submit - musi zostać odrzucony NATYCHMIAST
await settle();

await vi.advanceTimersByTimeAsync(300);
await settle();

expect(component['submitCallCount']()).toBe(1); // action wywołane RAZ, nie dwa
```

Test przechodzi — `submitCallCount` (mój własny licznik inkrementowany na starcie `action`)
zostaje na `1` mimo dwóch zdarzeń `submit`. W ASP.NET Core odpowiednikiem byłoby ręczne
blokowanie podwójnego kliknięcia przyciskiem po stronie klienta albo idempotency key po
stronie serwera — tu ochrona jest częścią samego `submit()`, za darmo, potwierdzona nie tylko
w `.d.ts`, ale i w działającym teście.

---

## 5️⃣ Weryfikacja — prawdziwy output

```text
$ npm ci --no-audit --no-fund
added 274 packages in 11s

$ npm run build
main-Y5L3PYNB.js    | main    | 207.76 kB |  57.67 kB
styles-5INURTSO.css | styles  |   0 bytes |   0 bytes
Application bundle generation complete. [8.066 seconds]

$ npm test
 Test Files  4 passed (4)
      Tests  15 passed (15)
   Duration  3.25s
```

15 testów w 4 plikach: `order-backend.spec.ts` (2 — fake-backend zamówienia: sukces po 300 ms,
promise nierozwiązane wcześniej), `quantity-stepper.spec.ts` (4 — render wartości, granica
`max` blokuje "+", granica `min` blokuje "−", `disabled` blokuje oba niezależnie od granic),
`order-form.spec.ts` (8 — start z jedną pozycją i błędami wymaganymi, dodawanie wiersza,
usuwanie wiersza z ochroną przed zejściem do zera, niezależna walidacja per wiersz przez
`applyEach`, edycja ilości przez własny kontrolek, automatyczne `min`/`max` z schemy, pełny
submit sukcesu, blokada współbieżnego submit), `app.spec.ts` (1 — kompozycja komponentu
głównego). Zero poprawek po drodze — w odróżnieniu od wydania #5 (pułapka z fake timerami),
tym razem wszystkie testy przeszły za pierwszym uruchomieniem `ng test`.

Jedna rzecz warta odnotowania z procesu weryfikacji: `npx vitest run` uruchomiony bezpośrednio
(z pominięciem `ng test`) failuje z `Need to call TestBed.initTestEnvironment() first` —
builder Angulara (`@angular/build:unit-test`) konfiguruje środowisko testowe (Angular
`TestBed` + jsdom) przed odpaleniem Vitest, więc testy Signal Forms/komponentów trzeba
odpalać przez `ng test`/`npm test`, nie przez gołe `vitest run`. To nie błąd w kodzie, tylko
przypomnienie, że projekt Angulara ma własny, nakładany na Vitest warstwę uruchomieniową.

### ⚠️ Co jest niezweryfikowane (wprost)

- **`ng serve`/przeglądarka nie były uruchamiane** — cała weryfikacja to `ng build` i testy w
  jsdom (Vitest). Wizualne zachowanie `QuantityStepper` (np. focus po kliknięciu, płynność
  animacji) nie było oglądane w realnej przeglądarce.
- **`errors`/`touched`/`focus()` na `FormValueControl`** — `QuantityStepper` implementuje
  tylko `value`, `disabled`, `min`, `max`. Reszta kontraktu `FormUiControl` (`errors` jako
  input renderowany wewnątrz komponentu, `touch` output, `focus()`/`reset()` jako metody)
  istnieje w typach i jest opisana w `.d.ts`, ale nie została tu użyta — błędy w moim
  przykładzie nadal renderuję na zewnątrz kontrolka, w szablonie hosta, tak jak w wydaniu #5.
- **`transformedValue()`** — widziana w `.d.ts` jako pomocnik do parsowania "surowej" wartości
  UI (np. string z `<input>`) na typ modelu z raportowaniem błędów parsowania; nie użyta, bo
  `QuantityStepper` operuje na `number` natywnie (przyciski, nie tekstowy input).
- **SSR/hydration, `tapResponse`, `validateHttp`** — wciąż nieruszone (patrz "następnym razem").

---

## 🧭 Do zapamiętania

| Potrzeba | Narzędzie |
|---|---|
| Jedna reguła walidacji dla wielu elementów tablicy | `schema<T>(fn)` (reużywalna, nazwana) + `applyEach(f.tablica, schemaT)` |
| Dodanie/usunięcie elementu tablicy pól | zwykły `signal.update()` na modelu — `applyEach` obejmuje elementy automatycznie |
| Własny komponent zamiast `<input>` podpięty pod `[formField]` | zaimplementuj `FormValueControl<TValue>` — wymagane tylko `value: ModelSignal<TValue>` |
| Ograniczenia (`min`/`max`/`disabled`/...) przekazane do własnego kontrolka bez ręcznego wiązania | zadeklaruj odpowiednie opcjonalne `input()` z `FormUiControl` — `[formField]` wypełnia je z pola |
| Ochrona przed podwójnym submitem | wbudowana w `submit()`/`[formRoot]` — drugie wywołanie w trakcie trwającego zwraca `false` bez odpalania `action` |

**Następnym razem (propozycja):** `transformedValue()` z realnym parsowaniem błędnych wartości
UI, `errors`/`touch` jako pełna implementacja `FormUiControl` na własnym kontrolce,
`validateHttp` (async walidacja wprost na `httpResource`), SSR/hydration, `tapResponse`
z `@ngrx/operators`, `ng serve` w przeglądarce (jeśli środowisko na to pozwoli).

---

## 📎 Jak uruchomić

Zobacz [`code/README.md`](code/README.md).

---

<div align="center">

[← wróć do wydania (wszystkie rubryki)](../README.md) · [spis wydań](../../README.md)

</div>
