<div align="center">

# 📰 TECH PRASÓWKA
### Wydanie #20 rubryki Angular — 13 października 2026

![Angular](https://img.shields.io/badge/Angular-DD0031?style=for-the-badge&logo=angular&logoColor=white)
![Signal Forms](https://img.shields.io/badge/Signal_Forms-CVA_interop-1565C0?style=for-the-badge)

## `FormCheckboxControl` i stary `ControlValueAccessor` pod `[formField]` — i `reset()`, który nie anuluje wpisu

</div>

---

> _"A component that provides a `ControlValueAccessor`. This should only be used for backwards
> compatibility with reactive forms. Prefer options (1) and (2)."_
> — komentarz nad dyrektywą `FormField`, `@angular/forms/signals` 22.2.2.

Przez pięć wydań budowałem własne kontrolki w nowym stylu (`FormValueControl`). Zostały dwa
otwarte wątki z #19: **checkbox** (inny kontrakt: `checked`, nie `value`) i **migracja**
— w każdej większej aplikacji leżą dziesiątki komponentów napisanych pod Reactive Forms
(`ControlValueAccessor`, CVA). Dla .NET developera analogia: `ICustomTypeDescriptor`/stary
`TypeConverter` kontra nowy `INotifyPropertyChanged` — dwa światy, a framework musi je
obsłużyć jednym atrybutem. Tu atrybutem jest `[formField]`.

| | |
|---|---|
| 🧱 Stack | `@angular/forms` **22.2.2**, `@angular/core` 22.2.2, CLI/build 22.2.2, TypeScript **6.0.3**, `rxjs` 7.8.2 |
| 🖥️ Środowisko | Node **v22.14.0**, npm 10.9.2, Vitest **5.0.4** + jsdom 30.1.2 (zdarzenia syntetyczne, bez przeglądarki) |
| ✅ Weryfikacja | `npm install` (279 pakietów, 39 s), `ng build` OK (6,8 s, 203,01 kB), `ng test` **18/18** (2 pliki) + test mutacyjny (5 testów pada) |
| 📦 Kod | [`code/`](code/) — `ConsentToggle` (checkbox), `StarRating` (stary CVA), walidator `NG_VALIDATORS`, 17 pomiarów |

**Plan:** (1) `FormCheckboxControl` z `debounce`, (2) stary CVA pod `[formField]` — cykl życia,
(3) co z CVA przechodzi, a co nie, (4) pułapka: `reset()` w trakcie debounce, (5) weryfikacja i luki.

---

## 1️⃣ `FormCheckboxControl`: ten sam kontrakt, inna nazwa modelu

### 🎣 Dlaczego to ważne

Przełącznik („zgoda na newsletter”) to `boolean`. Można go zrobić jako `FormValueControl<boolean>`,
ale wtedy dyrektywa nie wie, że to checkbox. Kontrakt `FormCheckboxControl` wymaga
`checked = model(false)` i **zabrania** `value` (w typie `value?: undefined` — to samo w drugą
stronę dla `FormValueControl`: `checked?: undefined`). Reszta (`disabled`, `touched`, `touch`,
`reset()` …) jest identyczna jak w #19.

```typescript
export class ConsentToggle implements FormCheckboxControl {
  readonly checked = model(false);          // jedyny wymagany element
  readonly disabled = input(false);
  readonly touch = output<void>();          // emitowany na (blur)
  toggle(): void { this.checked.update((v) => !v); }
  reset(): void { /* wołane przez FormField.reset() */ }
}
```

Schemat: `debounce(p.newsletter, 300)`. Zmierzone (fake timery, kliknięcia syntetyczne):

| Scenariusz | Wynik |
|---|---|
| 1 klik, t=0 | kontrolka `true`, `model` **`false`**, `dirty()` `true` |
| t=299 ms / t=300 ms | model `false` / **`true`** |
| 3 kliki co 100 ms | model `false` przez cały czas, po 300 ms od ostatniego `true` — **jeden** zapis |
| 2 kliki (tam i z powrotem) | kontrolka `false`, model `false`, ale **`dirty()` = `true`** |
| natywny `<input type=checkbox>` | model po 300 ms `true`; zaraz po kliknięciu `touched()` = **`false`** |
| własny checkbox + `debounce('blur')` | po kliknięciu i 5 s model `false`; po `blur` `true`, `touched` `true` |

Dwie rzeczy do zapamiętania:

- **`dirty()` nie znaczy „model się różni”.** Dwa kliki zostawiają `dirty() == true` przy
  niezmienionym modelu. Jeśli używasz `dirty()` do ostrzeżenia „masz niezapisane zmiany”,
  pokażesz je mimo że nic się nie zmieniło (odpowiednik w C#: flaga `IsDirty` ustawiana w setterze
  bez porównania wartości).
- **Natywny checkbox nie jest „dotknięty” klikiem** — tylko blurem. Jeśli walidacja pokazuje
  błędy dopiero po `touched()`, przełącznik nie wywoła jej przez samo kliknięcie.

---

## 2️⃣ Stary `ControlValueAccessor` — działa bez zmian

### 🎣 Dlaczego to ważne

`StarRating` w repo to klasyczny CVA: `providers: [{ provide: NG_VALUE_ACCESSOR, … }]`,
`writeValue`, `registerOnChange`, `registerOnTouched`, `setDisabledState`. **Zero kodu Signal Forms.**
Wystarczy `[formField]="f.rating"`. Dzięki temu migrację można robić formularz po formularzu, a nie
„wielkim wybuchem”.

Każde wywołanie metod CVA zapisuję w tablicy (`calls`). Zmierzone przy montowaniu:

```text
MEASURE cva-mount: ["registerOnChange","registerOnTouched","writeValue(0)","setDisabledState(false)"]
```

Kolejność: **najpierw rejestracja callbacków, potem `writeValue`, potem `setDisabledState(false)`**
— także wtedy, gdy pole nigdy nie jest wyłączone. Jeśli twój `setDisabledState` robi coś
kosztownego, wywoła się przy montowaniu.

Z debounce — to samo co w #15/#19, tylko „blur” przychodzi z `registerOnTouched`:

```text
MEASURE cva-pick-blur: {"during":{"current":4,"model":0,"touched":false,"dirty":true,"errors":["min"], ...},
                        "afterBlur":{"model":4,"touched":true,"errors":[], ...}}
```

- Podczas oczekiwania: UI pokazuje 4 gwiazdki, **model ma 0**, walidator `min` widzi model (stary
  błąd, jak w #19).
- Po `onTouched()` (u mnie `(blur)` na przycisku): model 4, `touched` `true`.
- **Brak echa:** zmiana z UI nie wraca do kontrolki przez `writeValue` (lista `calls` identyczna
  przed i po). Zapis programowy `f.rating().value.set(2)` — owszem, kończy się `writeValue(2)`.
- Po zniszczeniu kontrolki (`@if`) z oczekującym wpisem model dostaje wartość (`0 → 3`) — to ten sam
  `flushSync` co w #19, działa także na ścieżce CVA.

> Zapamiętaj: w CVA `onTouched()` to **odpowiednik outputu `touch`**. Zapomnisz go wywołać —
> `debounce('blur')` nie domknie się nigdy. Ten sam błąd, inna składnia.

---

## 3️⃣ Co z CVA przechodzi, a co nie

### 🎣 Dlaczego to ważne

Dyrektywa mapuje stan pola na kontrolkę, ale CVA ma bardzo wąski interfejs. Zmierzone:

| Stan pola | Co dostaje komponent CVA |
|---|---|
| `disabled` (schemat) | `setDisabledState(true)` ⇒ `["…","setDisabledState(false)","setDisabledState(true)"]` |
| `readonly` (schemat) | **brak metody CVA.** Dostaje go tylko zwykły `input()` o nazwie `readonly` na komponencie (u mnie `readonlyInput: true`); `setDisabledState(false)` wołane przy wyjściu z `locked` |
| walidatory ze schematu | działają jak zwykle (`min` ⇒ `"min"`) |
| `NG_VALIDATORS` na hoście | **działają i łączą się ze schematem** |

Stary walidator — dyrektywa `appMinStars` z `NG_VALIDATORS` (klasyczne Reactive Forms) na tym samym
elemencie co `[formField]`. Wartości 0 → 2 → 4:

```text
MEASURE cva-validators: {"r0":["minStars","min"],"r2":["minStars"],"r4":[],"valid":true}
MEASURE cva-validator-only: [{"kind":"minStars","keys":["kind","control","fieldTree","context","message","formField"]}]
```

Klucz słownika błędu (`{ minStars: {...} }`) staje się `kind`. Walidatory legacy występują **przed**
regułami schematu na liście błędów. Źródło (`signals.mjs`, `cvaControlCreate`): `NG_VALIDATORS`
są pobierane z `self: true` — tylko z tego samego elementu, nie z rodzica.

Dla .NET dev: to coś jak `IValidatableObject` obok atrybutów `[Range]` — dwa mechanizmy,
jedna lista `ModelState`.

### 🧨 Obie ścieżki naraz: wygrywa CVA

Komponent implementujący jednocześnie `ControlValueAccessor` i `FormValueControl` (`DualRating`):

```text
MEASURE cva-vs-value: {"calls":["registerOnChange","registerOnTouched","writeValue(0)","writeValue(3)"],"valueModel":0}
MEASURE cva-vs-touch: {"model":0,"touched":false}
```

Zapis `f.rating().value.set(3)` kończy się `writeValue(3)`, a `model` `value` zostaje `0`. Wynik jest
zgodny z kodem (`ɵngControlCreate`: najpierw `if (this.controlValueAccessor)`, potem
`host.customControl`). Konsekwencja: **output `touch` jest ignorowany** — `debounce('blur')`
nie domknie się przez `touch.emit()`. Jeśli przepisujesz CVA na nowy kontrakt, **usuń
`NG_VALUE_ACCESSOR` z `providers`**, inaczej nowy kod jest martwy.

---

## 4️⃣ ⚠️ `reset()` w trakcie debounce: UI się cofa, wpis zostaje

### 🎣 Dlaczego to ważne

Scenariusz: użytkownik kliknął 5 gwiazdek (wpis czeka na blur), program woła
`FormField.reset()` („wyczyść formularz”). Zmierzone:

```text
MEASURE cva-reset: {"afterReset":{"current":0,"model":0,"last":"writeValue(0)"},
                    "afterBlur":{"current":5,"model":5}}
```

`reset()` zrobił `writeValue(0)` (UI wraca do zera), model `0`. Ale **oczekujący wpis `5` nie został
anulowany**: gdy użytkownik wychodzi z pola (blur), model dostaje `5`, a `writeValue(5)` przywraca
gwiazdki. Formularz „wyczyszczony”, po czym samoistnie „odżywa”. Na kodzie, który robi „Wyczyść”
i od razu przenosi fokus, trafia to w produkcję.

Obejście: nie zakładaj, że `reset()` czyści kolejkę debounce. Pomysł: najpierw domknąć wpis
(wywołać `touch`/`onTouched`, czyli zrobić blur), a dopiero potem zresetować model. Tego
obejścia **nie weryfikowałem** — pomiar dotyczy tylko samej pułapki (test
`FormField.reset() w trakcie oczekującego wpisu NIE anuluje wpisu`).

Dla własnej kontrolki z `reset()` (`ConsentToggle`) zmierzone jedno: `FormField.reset()` woła
`reset()` kontrolki dokładnie raz (`resetCalls: 1`).

---

## 5️⃣ Weryfikacja — prawdziwy output

Node w tej sesji: **v22.14.0**, a CLI 22.2.2 wymaga `>=22.22.3`. Obejście jak w #9/#12–#19:
lokalna jednoliniowa edycja stałej `SUPPORTED_NODE_VERSIONS` w
`node_modules/@angular/cli/src/utilities/node-version.js` (`^22.22.3` → `^22.14.0`), poza repo
(`node_modules/` w `.gitignore`), **do powtórzenia po każdym `npm ci`/`npm install`**.
Instalacja zgłasza dużo ostrzeżeń `EBADENGINE` (warning npm, nie błąd). To, że obejście nie wpływa na
wyniki, jest założeniem.

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

Test mutacyjny: (a) usunąłem `debounce(p.newsletter, 300)` ze schematu, (b) zamieniłem
`onTouched()` w `StarRating.markTouched()` na komentarz. Padło **5** testów (klik z debounce,
trzy kliknięcia, pick+blur, reset, walidatory — w tym ostatnim `minStars` wraca, bo model
nie dostał wartości). Po przywróceniu 18/18.

`package-lock.json` wygenerowany na nowo (`cp` z poprzedniego wydania zablokowany w
środowisku, nie obchodziłem): Angular 22.2.2, Vitest **5.0.4** (w #19 było 5.0.3).

### ⚠️ Co jest niezweryfikowane (wprost)

- **`ng serve`/przeglądarka**: kliknięcia i `blur` są syntetyczne (jsdom); realne
  zachowanie fokusu w przeglądarkach nie było sprawdzane.
- Obejście pułapki z `reset()` — tylko zaproponowane, nietestowane.
- CVA z `ngModel`/`FormControl` jednocześnie z `[formField]` (mieszane formularze).
- `NG_ASYNC_VALIDATORS` pod `[formField]`, `Validators.required` (`hasValidator`) w interopie.
- SSR/hydration, `mapResponse()` w `@ngrx/effects`, `aria-*` czytnikiem ekranu.

---

## 🧭 Do zapamiętania

| Potrzeba | Co zrobić |
|---|---|
| Własny przełącznik boolean | `FormCheckboxControl`: `checked = model(false)`, bez `value` |
| `debounce` na checkboxie | działa jak na tekście; `dirty()` zostaje `true` przy podwójnym kliku |
| Stary CVA pod `[formField]` | bez zmian w komponencie, `[formField]` wystarcza |
| `debounce('blur')` na CVA | wołaj `onTouched()` na blur (odpowiednik `touch`) |
| Stan `readonly` w CVA | nie ma metody; dodaj `input()` o nazwie `readonly` |
| Stare `NG_VALIDATORS` | działają i są **przed** regułami schematu |
| CVA + `FormValueControl` na jednej klasie | wygrywa CVA, `value`/`touch` martwe |
| `reset()` w trakcie debounce | wpis czeka i wraca po blurze — nie zakładaj, że kolejka jest czyszczona |

**Następnym razem (propozycja):** SSR/hydration formularzy, `mapResponse()` z `@ngrx/operators`
w `@ngrx/effects`, `ng serve` w prawdziwej przeglądarce (jeśli będzie dostępna), obejście
pułapki `reset()`.

---

## 📎 Jak uruchomić

Zobacz [`code/README.md`](code/README.md).

---

<div align="center">

[← wszystkie artykuły: 🅰️ Angular](../README.md) · [spis rubryk](../../../README.md)

</div>
