<div align="center">

# 📰 TECH PRASÓWKA
### Wydanie #5 rubryki Angular — 28 września 2026

![Angular](https://img.shields.io/badge/Angular-DD0031?style=for-the-badge&logo=angular&logoColor=white)

## Signal Forms: formularz bez `FormGroup`, walidacja async przez `resource()` + `AbortSignal`

</div>

---

> _"W Reactive Forms `FormGroup` trzyma własną kopię wartości i synchronizuje ją z modelem
> ręcznie. W Signal Forms `form()` NIE kopiuje niczego - owija istniejący `signal()` w drzewo
> pól. Ustawiasz wartość pola, model się zmienia. To nie jest analogia do sygnałów, to SĄ
> sygnały, od pierwszej do ostatniej warstwy."_

Wydania #1-#4 zbudowały fundament: `signal`/`computed`/`effect`, signal store, `linkedSignal`,
`httpResource`, router z `withComponentInputBinding` i `@defer`. STATE.md sugerował na dziś:
formularze na signals, SSR/hydration, `resource()` z własnym loaderem, `tapResponse`. Zanim
cokolwiek obiecałem, sprawdziłem w realnie zainstalowanym Angularze **22.2.0** (ten sam co
wczoraj - to nadal najnowsza stabilna wersja), co z tego istnieje. Wynik: **Signal Forms
istnieją** jako `@angular/forms/signals` i niemal cała ich publiczna powierzchnia API
(`form`, `schema`, `required`, `minLength`, `pattern`, `email`, `validate`, `validateAsync`,
`FormField`, `FormRoot`, `submit`...) ma w plikach `.d.ts` znacznik `@publicApi 22.0`, NIE
`@experimental` - jedynym `@experimental` w tym pakiecie jest integracja z WebMCP
(`provideExperimentalWebMcpForms`), z formularzami samymi w sobie niezwiązana. To wystarczyło,
żeby zrobić z tego dzisiejszy temat, połączony z drugą sugestią z listy: `resource()` z
własnym loaderem, bo Signal Forms używają go bezpośrednio do walidacji asynchronicznej.

| | |
|---|---|
| 🧱 Stack | `@angular/core` i `@angular/forms` **22.2.0** (w tym `@angular/forms/signals`), TypeScript **6.0.3** |
| 🖥️ Środowisko | Node **v22.23.3**, npm **10.9.9**, testy: Vitest **5.0.2** + jsdom |
| ✅ Weryfikacja | `npm ci` (274 pakiety, 12 s), `ng build` OK (8 s), `ng test` **15/15** (output w sekcji 4) |
| 📦 Kod | [`code/`](code/) - formularz rejestracji: login/e-mail/hasło, walidacja sync + async |

**Plan:** (1) `form()`/`schema()` jako model bez kopiowania, (2) walidacja sync (`required`,
`minLength`, `pattern`, `email`) i `[formField]`/`[formRoot]`, (3) walidacja async: `validateAsync`
+ `resource()` z własnym loaderem i `AbortSignal`, (4) `submit()` i błąd "z serwera" wracający na
konkretne pole, (5) weryfikacja i pułapki złapane na żywym uruchomieniu testów.

---

## 1️⃣ `form()`: model bez kopiowania

### 🎣 Dlaczego to ważne

W Reactive Forms (`FormGroup`/`FormControl`) budujesz drzewo kontrolek OSOBNO od modelu
danych i ręcznie je synchronizujesz (`patchValue`, `valueChanges.subscribe(...)`). W .NET to
odpowiednik trzymania osobnego DTO na potrzeby UI i osobnego modelu domenowego, które musisz
ręcznie mapować w obie strony. Signal Forms tego nie robi:

```typescript
import { form } from '@angular/forms/signals';

const model = signal({ username: '', email: '', password: '' });
const registrationForm = form(model);

registrationForm.username().value.set('john');
registrationForm().value();  // { username: 'john', email: '', password: '' }
model();                     // { username: 'john', email: '', password: '' } - TEN SAM obiekt
```

`form()` zwraca `FieldTree` - obiekt, który jest jednocześnie **funkcją** (wywołanie daje
`FieldState` całego drzewa: `.value()`, `.valid()`, `.errors()`, `.submitting()`) i **kontenerem
pól** (`registrationForm.username` to child `FieldTree` z tymi samymi właściwościami dla
samego loginu). Żadnego mapowania - `model` i `registrationForm` to dwa widoki na te same dane.

Drugi argument `form()` to **schema**: funkcja (albo `schema()` do wielokrotnego użytku), w
której deklarujesz reguły dla poszczególnych pól - dokładnie jak `AbstractValidator<T>` we
FluentValidation, tylko że reguły są reaktywne i wpięte bezpośrednio w drzewo pól, a nie w
osobny obiekt walidatora wołany z zewnątrz.

---

## 2️⃣ Walidacja synchroniczna i `[formField]`/`[formRoot]`

### 🎣 Dlaczego to ważne

Każdy walidator to osobna funkcja wołana WEWNĄTRZ schema function, nie łańcuch metod na
kontrolce:

```typescript
const registrationForm = form(model, (f) => {
  required(f.username, { message: 'Login jest wymagany' });
  minLength(f.username, 3, { message: 'Login musi mieć co najmniej 3 znaki' });

  required(f.email, { message: 'Adres e-mail jest wymagany' });
  email(f.email, { message: 'To nie wygląda na adres e-mail' });

  required(f.password, { message: 'Hasło jest wymagane' });
  minLength(f.password, 8, { message: 'Hasło musi mieć co najmniej 8 znaków' });
  pattern(f.password, /\d/, { message: 'Hasło musi zawierać przynajmniej jedną cyfrę' });
});
```

W szablonie pole łączy się z natywnym `<input>` przez dyrektywę `[formField]` (selektor
zweryfikowany w `.d.ts`: `"[formField]"`, nie `[field]`, jak można by zgadywać z nazwy typu
`Field` widocznej w eksportach):

```html
<input id="username" type="text" [formField]="registrationForm.username" />
@for (e of registrationForm.username().errors(); track e.kind) {
  <p class="error">{{ e.message }}</p>
}
```

`[formField]` robi dwukierunkowe wiązanie wartości ORAZ synchronizuje `disabled`/`required`/
`touched`/`errors` z polem - jeden atrybut zamiast `[value]`+`(input)`+`[class.invalid]` ręcznie
sklejanych. Cały `<form>` spina dyrektywa `[formRoot]`:

```html
<form [formRoot]="registrationForm"> ... </form>
```

`[formRoot]` ustawia `novalidate`, przechwytuje natywny `submit` (`preventDefault`) i sam woła
`submit()` na drzewie pól - ale **tylko** jeśli `form()` dostał opcję `submission` (sekcja 4).
Bez niej `[formRoot]` i tak zablokuje przeładowanie strony, ale nic więcej nie zrobi.

---

## 3️⃣ Walidacja asynchroniczna: `validateAsync` + `resource()` z `AbortSignal`

### 🎣 Dlaczego to ważne

Sprawdzenie "czy login jest zajęty" wymaga zapytania do serwera - i to jest dokładnie
przypadek użycia `resource()` z własnym loaderem: reaktywne żądanie, `AbortSignal` anulujący
poprzednie zapytanie, gdy użytkownik pisze dalej. Signal Forms mają na to gotowy hak,
`validateAsync`, którego `factory` dostaje `Signal` parametrów i ma zwrócić `Resource`:

```typescript
validateAsync(f.username, {
  params: (ctx) => ctx.value(),
  debounce: 300,
  factory: (usernameSignal) =>
    resource({
      params: () => usernameSignal(),
      loader: ({ params, abortSignal }) => checkUsernameAvailability(params, abortSignal),
    }),
  onSuccess: (result) =>
    result.available ? undefined : { kind: 'taken', message: `Login "${result.username}" jest zajęty` },
  onError: () => ({ kind: 'check-failed', message: 'Nie udało się sprawdzić dostępności loginu' }),
});
```

`checkUsernameAvailability` to mój udawany endpoint (300 ms opóźnienia + realna obsługa
`AbortSignal` - `clearTimeout` i `reject` na `abort`), dokładnie w kształcie, jakiego chce
`ResourceLoader<T, R>`: `(params: ResourceLoaderParams<R>) => PromiseLike<T>`.

Najważniejsza właściwość, potwierdzona testem: **walidacja async w ogóle nie startuje, dopóki
walidacja synchroniczna nie przechodzi** (tak stoi wprost w dokumentacji API - "Async
validation for a field only runs once all synchronous validation is passing"). Test
`za krótki login... NIE odpala sprawdzania dostępności` wpisuje 2-znakowy login, czeka 1000 ms
i sprawdza, że nigdzie nie pojawia się "Sprawdzam dostępność" - bo `minLength` blokuje całą
resztę. W ASP.NET Core / FluentValidation taką kolejność (najpierw tanie reguły, potem drogie
zapytanie do bazy) trzeba by ustawić ręcznie (`.When(...)` albo kaskadowy tryb `CascadeMode`);
tutaj to domyślne zachowanie frameworku, za darmo.

### ⚠️ Pułapka złapana na żywym teście: jeden duży skok fake timera nie wystarczy

Pierwsza wersja testu robiła `await vi.advanceTimersByTimeAsync(600)` w jednym kroku (300 ms
debounce + 300 ms fake-backend). Test **failował** - pole nadal pokazywało "Sprawdzam
dostępność" mimo że 600 ms formalnie minęło:

```text
AssertionError: expected 'LoginSprawdzam dostępność…...' not to contain 'Sprawdzam dostępność'
```

Przyczyna: timer wewnętrznego `loader`-a jest tworzony DOPIERO wewnątrz callbacku timera
debounce'a, więc jego docelowy czas trafia dokładnie na granicę żądanego skoku - zbyt kruche,
żeby polegać na jednym wywołaniu. Naprawa: dwa oddzielne kroki, `advanceTimersByTimeAsync(300)`
→ `detectChanges` → `advanceTimersByTimeAsync(300)` → `detectChanges`, dokładnie jak w
`product-browser.spec.ts` z wydania #3 (wzorzec `settle()` już tam wypracowany). Wniosek: gdy w
teście łańcuch dwóch zależnych opóźnień (debounce → sieć), NIE skracaj do jednego skoku fake
timera, nawet jeśli suma się zgadza.

---

## 4️⃣ `submit()`: błąd "z serwera" trafia na konkretne pole

### 🎣 Dlaczego to ważne

Formularz może przejść walidację kliencką, a mimo to serwer go odrzuci (e-mail już
zarejestrowany). `submit()` przyjmuje `action`, które zwraca listę błędów wskazujących
**konkretne pole** przez właściwość `fieldTree` - odpowiednik
`ModelState.AddModelError(nameof(Model.Email), "...")` w ASP.NET Core, tylko reaktywnie:

```typescript
const registrationForm = form(model, (f) => { /* ...walidatory... */ }, {
  submission: {
    action: async (f) => {
      const outcome = await registerUser(f().value());
      if (outcome.kind === 'email-taken') {
        return [{ fieldTree: f.email, kind: 'server', message: outcome.message }];
      }
      return undefined;
    },
  },
});
```

`[formRoot]` woła to automatycznie po natywnym `submit`. `undefined` = sukces. Zwrócona lista
błędów trafia na `f.email` - w szablonie pojawia się dokładnie tam, gdzie inline błędy
walidacji klienckiej, bez żadnego dodatkowego kodu spinającego. Concurrent submit jest
blokowany przez sam framework: drugie kliknięcie "Zarejestruj" w trakcie trwającej submisji
zwraca `false` natychmiast, bez wywołania `action` (opisane w dokumentacji `submit()`, nie
testowałem tego jawnie osobnym testem - patrz "niezweryfikowane").

---

## 5️⃣ Weryfikacja - prawdziwy output

```text
$ npm ci --no-audit --no-fund
added 274 packages in 12s

$ npm run build
main-7KZRZIW3.js    | main    | 208.97 kB |  57.63 kB
styles-5INURTSO.css | styles  |   0 bytes |   0 bytes
Application bundle generation complete. [7.678 seconds]

$ npm test
 Test Files  4 passed (4)
      Tests  15 passed (15)
   Duration  3.14s
```

15 testów w 4 plikach: `username-availability.spec.ts` (4 - dostępny/zajęty login,
przerwanie natychmiastowe i w trakcie oczekiwania przez `AbortSignal`), `registration-backend.spec.ts`
(2 - fake-rejestracja: sukces i zajęty e-mail), `registration-form.spec.ts` (8 - required na
starcie, minLength blokuje async check, zajęty/wolny login po realnym debounce+fetchu, format
e-maila, pattern hasła, pełny submit sukces i submit z błędem z "serwera" na polu e-mail),
`app.spec.ts` (1 - kompozycja komponentu głównego).

Pierwsze podejście do dwóch testów (`wolny login`, `poprawny formularz`) faktycznie **nie
przeszło** za pierwszym razem (sekcja 3 wyżej) - poprawka jest częścią finalnego kodu w `code/`.

### ⚠️ Co jest niezweryfikowane (wprost)

- **`ng serve`/przeglądarka nie były uruchamiane.** Cała weryfikacja to `ng build` (kompilacja +
  bundle) i testy w jsdom (Vitest) - brak dostępu do prawdziwej przeglądarki w tym środowisku.
  Zachowanie `[formField]` na natywnym `<input>` w jsdom może różnić się subtelnie od
  prawdziwego DOM-u (np. natywna walidacja `type="email"` przeglądarki).
- **Znacznik `@publicApi 22.0` to fakt z plików `.d.ts` w zainstalowanym pakiecie, nie z
  oficjalnej dokumentacji/ogłoszenia Angular.** Nie mam dostępu do internetu w tym środowisku,
  więc nie mogłem sprawdzić, czy angular.dev nadal opisuje Signal Forms jako "developer
  preview" mimo wewnętrznego znacznika stabilności - traktuj to jako silną poszlakę, nie
  potwierdzenie marketingowe.
- **Blokada współbieżnego `submit()`** (drugie kliknięcie w trakcie trwającej submisji zwraca
  `false`) - opisana w dokumentacji, nie pokryta osobnym testem.
- **`validateHttp`** (wariant `validateAsync` oparty wprost o `httpResource`, bez ręcznego
  `resource()`) - widziany w typach, nie użyty; wybrałem `resource()` ręcznie, żeby pokazać
  mechanikę `AbortSignal` explicite.
- **SSR/hydration i `tapResponse`** - wciąż nieruszone (patrz "następnym razem").
- Fake-backendy (`checkUsernameAvailability`, `registerUser`) to `setTimeout` w pamięci, nie
  prawdziwe HTTP - celowo, żeby skupić się na Signal Forms, nie na warstwie sieciowej.

---

## 🧭 Do zapamiętania

| Potrzeba | Narzędzie |
|---|---|
| Formularz jako drzewo sygnałów bez kopiowania modelu | `form(modelSignal, schemaFn, options?)` z `@angular/forms/signals` |
| Reguła walidacji (sync) | `required`/`minLength`/`maxLength`/`pattern`/`email`/`min`/`max`/`validate` wołane w schema function |
| Wiązanie pola z natywnym `<input>`/`<textarea>` | dyrektywa `[formField]` |
| Spięcie całego `<form>` (novalidate + submit) | dyrektywa `[formRoot]`, wymaga `submission` w opcjach `form()` |
| Walidacja async z anulowaniem poprzedniego żądania | `validateAsync` + `factory: (params) => resource({ params, loader })` |
| Błąd "z serwera" na konkretnym polu po `submit()` | zwróć `[{ fieldTree: pole, kind, message }]` z `action` |

**Następnym razem (propozycja):** `validateHttp` (async walidacja wprost na `httpResource`),
`applyEach`/`schema()` do wielokrotnego użytku na tablicach pól, własny `FormValueControl`
(niestandardowy kontrolek zamiast natywnego `<input>`), SSR/hydration, `tapResponse`
z `@ngrx/operators`, `ng serve` w przeglądarce (jeśli środowisko na to pozwoli).

---

## 📎 Jak uruchomić

Zobacz [`code/README.md`](code/README.md).

---

<div align="center">

[← wróć do wydania (wszystkie rubryki)](../README.md) · [spis wydań](../../README.md)

</div>
