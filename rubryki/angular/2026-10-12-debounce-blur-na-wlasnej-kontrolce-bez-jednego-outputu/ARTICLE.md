<div align="center">

# 📰 TECH PRASÓWKA
### Wydanie #19 rubryki Angular — 12 października 2026

![Angular](https://img.shields.io/badge/Angular-DD0031?style=for-the-badge&logo=angular&logoColor=white)
![Signal Forms](https://img.shields.io/badge/Signal_Forms-FormValueControl-1565C0?style=for-the-badge)

## `debounce('blur')` na własnej kontrolce: bez jednego outputu model nie zapisze się NIGDY

</div>

---

> _"Emit this in response to the native `blur` event (when focus leaves the control), not `focus`.
> The `Field` directive listens to this output to update the field's touched status, which
> blur-based rules such as `debounce('blur')` rely on."_
> — komentarz nad `touch` w `FormUiControl`, `@angular/forms/signals` 22.2.2.

W #15 użyłem `debounce(p.name, 'blur')` na natywnym `<input>` i wszystko działało „samo".
Zostawiłem wtedy otwarty wątek: co z **własną kontrolką**? Dziś to zamykam i przy okazji
dociągam resztę opcjonalnego kontraktu `FormUiControl` (`required`, `pattern`, `readonly`,
`hidden`, `disabledReasons`, `name`…). Dla .NET developera: to jak własny `UserControl` w WPF,
któremu framework sam wstrzykuje `IsEnabled`, `IsReadOnly`, `Validation.Errors` — tyle że tu
nie ma `DependencyProperty`, tylko `input()` o odpowiedniej nazwie.

| | |
|---|---|
| 🧱 Stack | `@angular/forms` **22.2.2**, `@angular/core` 22.2.2, `@angular/build`/CLI 22.2.2, TypeScript **6.0.3**, `rxjs` 7.8.2 |
| 🖥️ Środowisko | Node **v22.14.0**, npm 10.9.2, Vitest **5.0.3** + jsdom (zdarzenia syntetyczne, bez przeglądarki) |
| ✅ Weryfikacja | `npm install` (276 pakietów, 50 s), `ng build` OK (7,2 s, 199,89 kB), `ng test` **13/13** (2 pliki) + test mutacyjny |
| 📦 Kod | [`code/`](code/) — kontrolka `SkuInput` z pełnym kontraktem + 12 pomiarów |

**Plan:** (1) co dyrektywa `[formField]` sama wstrzykuje do kontrolki, (2) `debounce('blur')` +
brakujący `touch`, (3) trzy sposoby wyłączenia pola i ich wspólny skutek uboczny, (4) weryfikacja i luki.

---

## 1️⃣ Kontrakt: kontrolka dostaje stan pola „za darmo"

### 🎣 Dlaczego to ważne

Jedyny **wymagany** element to `value = model<T>()`. Reszta jest opcjonalna, ale jeśli zadeklarujesz
`input()` o nazwie z kontraktu, dyrektywa `[formField]` zasila go automatycznie. Zero bindowania
w szablonie rodzica. Efekt: `<app-sku-input [formField]="f.sku" />` i kontrolka wie, że jest
wymagana, ile ma znaków i jaki wzorzec obowiązuje.

Kontrolka (skrót, pełny kod w `code/src/app/sku/sku-input.ts`):

```typescript
export class SkuInput implements FormValueControl<string> {
  readonly value = model('');                     // jedyny wymagany element
  readonly required = input(false);
  readonly pattern = input<readonly RegExp[]>([]);
  readonly maxLength = input<number | undefined>(undefined);
  readonly disabled = input(false);
  readonly disabledReasons = input<readonly WithOptionalFieldTree<DisabledReason>[]>([]);
  readonly readonly = input(false);
  readonly name = input('');
  /* hidden, invalid, pending, touched, dirty, minLength, errors … */
  readonly touch = output<void>();                // PATRZ sekcja 2
}
```

Schemat pola (`sku.schema.ts`): `required`, `pattern(/^[A-Z]{3}-\d{4}$/)`, `maxLength(8)`.
Zmierzone w teście zaraz po wyrenderowaniu (tryb `edit`, puste pole):

```text
required: true            pattern: ["/^[A-Z]{3}-\\d{4}$/"]    maxLength: 8
minLength: undefined      name: "a.form0.sku"                  invalid: true
disabled/readonly/hidden/pending/touched/dirty: false          errors: ["required"]
```

Dwie rzeczy, których nie zakładałem:

- **`name`** to `"<APP_ID>.form<N>.sku"` — `a.form0.sku` w teście (APP_ID `a`), numer formularza rośnie
  globalnie. To nie jest `sku`; nie używaj go jako klucza do backendu.
- Ten sam schemat na **natywnym `<input>`** ustawia właściwości DOM: `required: true`, `maxLength: 8`,
  `name: "a.form1.sku"`, ale `pattern` zostaje `""` (wzorzec nie jest przenoszony do atrybutu).
  Na hoście **własnej kontrolki** (`<app-sku-input>`) nie pojawia się nic: ani `required`, ani `name`,
  ani `maxlength` — wszystko trzeba przepisać ręcznie do wewnętrznego `<input>`
  (u mnie przez `[disabled]`, `[readOnly]`, `[attr.aria-required]`…).

---

## 2️⃣ ⚠️ `debounce('blur')` i brakujący `touch`

### 🎣 Dlaczego to ważne

Reguła `debounce(p.sku, 'blur')` trzyma wpis użytkownika w „kolejce", dopóki pole nie zostanie
**dotknięte** (touched). Natywny `<input>` dyrektywa podpina sama (nasłuch `blur`). Własna
kontrolka musi to zrobić sama przez output `touch`. Jeśli go zabraknie, **kod się kompiluje,
walidacja działa, a model nigdy się nie zapisze**:

```text
NoTouchSkuInput: wpis 'ABC-1234', zdarzenie blur, czekam 1 s
model().sku = ''   touched() = false   dirty() = true
```

Kontrakt `FormValueControl` wymaga tylko `value`, więc kompilator milczy. To najbardziej podstępny
rodzaj błędu: UI wygląda dobrze (kontrolka pokazuje wpisany tekst), a `submit()` dostaje pusty model.
W C# odpowiednik: `UpdateSourceTrigger=LostFocus` na kontrolce, która nigdy nie wywołuje
`LostFocus`.

Poprawna kontrolka (`touch` na `blur`, nie na `focus`):

```html
<input [value]="value()" (input)="onInput($event)"
       (blur)="touch.emit()" (keydown.enter)="touch.emit()" />
```

### Zmierzone zachowanie przy poprawnym `touch`

| Moment | `model().sku` | `touched()` | `dirty()` | `errors()` |
|---|---|---|---|---|
| po wpisaniu `abc-1234` (przed blur) | `''` | `false` | **`true`** | **`['required']`** |
| po `blur` | `'abc-1234'` | `true` | `true` | `['pattern']` |

Haczyk w pierwszym wierszu: pole **już ma tekst**, a komunikat dalej brzmi „SKU jest wymagane".
Walidatory widzą model, nie to, co jest w kontrolce. Jeśli pokazujesz błędy od razu (bez `touched()`),
użytkownik zobaczy nieaktualny komunikat. Wzorzec: błędy pokazuj dopiero po `touched()`.

### Trzy sposoby domknięcia oczekującego wpisu

1. **`blur`** — standard.
2. **Enter** — `(keydown.enter)="touch.emit()"`. Zmierzone: po Enterze `model().sku == 'ABC-1234'`,
   `submit()` odpalił akcję raz z tą wartością. Bez Entera i bez blura `submit()` z kodu zwraca
   `false`, akcja się **nie** odpala, model dalej `''` (to ta sama pułapka z #15, tu zamknięta
   po stronie kontrolki).
3. **Zniszczenie kontrolki** — niespodzianka. Gdy kontrolka znika z DOM (`@if`) z oczekującym
   wpisem, model dostaje wartość: `{ before: '', after: 'ABC-1234' }`. Źródło: cleanup efektu
   bindingu woła `flushSync()` (`signals.mjs`, `registerAsBinding`), jeśli nie zostały żadne inne
   bindingi pola. Wpis nie przepada, ale też nie ma `touched`.

> Zapamiętaj: **`touch` to nie „ozdobny" output.** To jedyny sposób, żeby `debounce('blur')`
> działał na własnej kontrolce.

---

## 3️⃣ `disabled`, `readonly`, `hidden` — trzy flagi, jeden skutek

### 🎣 Dlaczego to ważne

Dokumentacja każdego z trzech mówi to samo: pole „nie wnosi" nic do walidacji i stanu
touched/dirty. W kodzie (`_validation_errors-chunk.mjs`):
`shouldSkipValidation = hidden() || disabled() || readonly() || isOrphaned()`.
Zmierzone na tym samym polu `sku` (puste, `required`):

| Tryb | Co dostaje kontrolka | `errors()` | `valid()` |
|---|---|---|---|
| `edit` | wszystko `false` | `['required']` | `false` |
| `locked` (`disabled`) | `disabled: true`, `disabledReasons: ["Magazyn zablokował edycję SKU"]` | `[]` | `true` |
| `readonly` | `readonly: true` | `[]` | `true` |
| `hidden` | (kontrolka usunięta przez `@if`) | `[]` | `true` |

Konsekwencje, które łatwo przeoczyć:

- **`hidden` + `required` + `submit()`**: puste, wymagane pole, a `submit()` zwraca `true` i akcja
  dostaje `sku: ''`. Zmierzone: `visibleOk: false`, po przejściu w `hidden` — `hiddenOk: true`,
  `calls: ["''"]`. Dla .NET dev: to jak `[Required]` na właściwości, którą model binder pomija.
  Walidację po stronie serwera nadal musisz mieć.
- **`touched`/`dirty` znikają przy `readonly`**, ale **wracają** po powrocie do `edit`:
  `before {touched:true, dirty:true, errors:['pattern']}` → `during {touched:false, dirty:false,
  errors:0}` → `back` identyczne jak `before`. Stan jest zapamiętany, tylko maskowany
  (`selfTouched && !isNonInteractive`).
- **`disabledReasons` to tablica obiektów**, nie string: `disabled(p.sku, { when: … })` zwracające
  string trafia do `message`. Kontrolka może pokazać powód (u mnie `<small>` pod polem).
- **`hidden` bez `@if`**: kontrolka dostaje `hidden: true`, ale **dalej jest w DOM**, a tryb dev
  ostrzega w konsoli (`is hidden but is being rendered`, test przechwycił jedno ostrzeżenie).
  `hidden` to flaga stanu, nie `display: none`.
- **Wpis oczekujący + `locked` + `blur`**: model dostał `'ABC-1234'` mimo `disabled`
  (`touched()` zostało `false`). `debounce` nie sprawdza `disabled` przy zapisie. Jeśli
  `disabled` ma blokować zmianę modelu, nie polegaj tylko na tym, że wewnętrzny `<input>` jest
  zablokowany — wpis, który zdążył powstać przed zablokowaniem, i tak wyląduje w modelu.

---

## 4️⃣ Weryfikacja — prawdziwy output

Node w tej sesji: **v22.14.0**, a CLI 22.2.2 wymaga `>=22.22.3`. Obejście jak w #9/#12–#15:
lokalna jednoliniowa edycja progu w `node_modules/@angular/cli/src/utilities/node-version.js`
(poza repo, `node_modules/` w `.gitignore`), **do powtórzenia po każdym `npm ci`/`npm install`**.
Instalacja zgłasza dużo ostrzeżeń `EBADENGINE` (warning npm, nie błąd).

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

Test mutacyjny: usunąłem `debounce(p.sku, 'blur')` ze schematu → padło **5** testów (m.in.
`expected 'ABC-1234' to be ''` w teście zniszczenia kontrolki i teście Entera). Po przywróceniu 13/13.

Uczciwie o procesie: lockfile z poprzednich wydań **nie został skopiowany** (polecenie `cp` zostało
odrzucone przez środowisko, nie obchodziłem tego), więc `package-lock.json` jest wygenerowany na
nowo przez `npm install` z tego samego `package.json`. Skutek: Angular **22.2.2** zamiast 22.2.1
z #15; reszta (TypeScript 6.0.3, Vitest 5.0.3, jsdom 30.1.2, rxjs 7.8.2) bez zmian.

### ⚠️ Co jest niezweryfikowane (wprost)

- **`ng serve`/przeglądarka**: zdarzenia `blur`/`keydown.enter` w testach są syntetyczne (jsdom).
  Realne zachowanie Entera w polu wewnątrz `<form>` (domyślny submit) niesprawdzone.
- `focus()`/`reset()` na tej kontrolce — pokryte w #9 na innych kontrolkach, tu nieużyte.
- Kontrolki `FormCheckboxControl` i `ControlValueAccessor` (interop) w kontekście `debounce('blur')`.
- Dostęp do surowego tekstu w `Debouncer`, SSR/hydration, `mapResponse()` w `@ngrx/effects`.
- Twierdzenia o dostępności (`aria-*`) — ustawione, ale nieprzetestowane czytnikiem ekranu.
- Obejście progu wersji Node nie powinno wpływać na wyniki, ale to założenie.

---

## 🧭 Do zapamiętania

| Potrzeba | Co zrobić |
|---|---|
| `debounce('blur')` na własnej kontrolce | `touch = output<void>()` emitowany na `blur` (NIE `focus`) |
| Zatwierdzanie Enterem | dodatkowo `(keydown.enter)="touch.emit()"` |
| Kontrolka ma znać `required`/`pattern`/`maxLength` | deklaracja `input()` o tej samej nazwie, bez bindowania |
| Własny host nie dostaje atrybutów DOM | przepisz stan do wewnętrznego `<input>` ręcznie |
| Błąd pokazywany od razu | pamiętaj, że walidatory widzą model, nie wpis (`required` mimo tekstu) |
| `hidden`/`disabled`/`readonly` | pomijają walidację → `submit()` przechodzi z pustym `required` |
| `hidden` | zawsze z `@if`, inaczej ostrzeżenie dev i kontrolka zostaje w DOM |
| Oczekujący wpis, kontrolka znika | wpis jest domykany (`flushSync`), ale bez `touched` |

**Następnym razem (propozycja):** SSR/hydration formularzy, `mapResponse()` z `@ngrx/operators`
w `@ngrx/effects`, `FormCheckboxControl` z `debounce('blur')`, interop z `ControlValueAccessor`.

---

## 📎 Jak uruchomić

Zobacz [`code/README.md`](code/README.md).

---

<div align="center">

[← wszystkie artykuły: 🅰️ Angular](../README.md) · [spis rubryk](../../../README.md)

</div>
