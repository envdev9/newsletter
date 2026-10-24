<div align="center">

# 📰 TECH PRASÓWKA
### Wydanie #21 rubryki Angular — 14 października 2026

![Angular](https://img.shields.io/badge/Angular-DD0031?style=for-the-badge&logo=angular&logoColor=white)
![Signal Forms](https://img.shields.io/badge/Signal_Forms-reset_%2B_async-1565C0?style=for-the-badge)

## Obejście pułapki `reset()` z #20 — i `NG_ASYNC_VALIDATORS`, który Signal Forms cicho ignorują

</div>

---

> _"Note this does not change the data model, which can be reset directly if desired."_
> — komentarz nad `FieldState.reset()`, `@angular/forms` 22.2.2.

Wczoraj (#20) zostawiłem otwarty wątek: `reset()` w trakcie `debounce` cofa UI, ale nie anuluje
oczekującego wpisu. Obejście było tylko „zaproponowane”. Dziś jest sprawdzone testami — a przy okazji
wyszło, że problem jest gorszy niż myślałem, i że stary **asynchroniczny walidator CVA nie działa pod
`[formField]` w ogóle**, bez żadnego ostrzeżenia. Dla .NET developera: to jak `IAsyncValidator`
(np. „czy login jest wolny”), który po cichu przestaje być wołany po zmianie kontenera formularzy.

| | |
|---|---|
| 🧱 Stack | `@angular/forms` **22.2.2**, `@angular/core` 22.2.2, CLI/build 22.2.2, TypeScript **6.0.3**, `rxjs` 7.8.2 |
| 🖥️ Środowisko | Node **v22.14.0**, npm 10.9.2, Vitest **5.0.4** + jsdom 30.1.2 (zdarzenia syntetyczne, bez przeglądarki) |
| ✅ Weryfikacja | `npm install` (279 pakietów), `ng build` OK (6,9 s, 208,59 kB), `ng test` **14/14** (2 pliki) + test mutacyjny (4 testy padają) |
| 📦 Kod | [`code/`](code/) — `CodeInput` (CVA), `CodeAvailableValidator` (`NG_ASYNC_VALIDATORS`), `validateAsync`, `SignupForm` |

**Plan:** (1) dwa różne `reset()`, (2) pułapka z bliska, (3) obejście, (4) `NG_ASYNC_VALIDATORS` pod
`[formField]`, (5) zamiennik: `validateAsync`, (6) weryfikacja i luki.

---

## 1️⃣ Dwa różne `reset()` — i żaden nie „czyści formularza”

### 🎣 Dlaczego to ważne

W API są dwie metody o tej samej nazwie i zupełnie innych zadaniach:

| Metoda | Co robi | Czego **nie** robi |
|---|---|---|
| `FormField.reset()` (dyrektywa na elemencie) | przepisuje **aktualną wartość modelu** do kontrolki (`writeValue`) i czyści błąd parsowania | nie zmienia modelu, nie zeruje `dirty`/`touched` |
| `FieldState.reset(value?)` (`f.code().reset('')`) | zeruje `touched`/`dirty` pola i potomków; z argumentem — ustawia model | nie dotyka kontrolki jawnie (ale zmiana modelu ją odświeży) |

Pierwsza nazwa kusi („reset kontrolki” = „wyczyść”), a robi tylko „pokaż to, co jest w modelu”.
Wynik z testu na polu z modelem startowym `"START"` i `debounce(300)`: po wpisaniu `TYPED`
i `FormField.reset()` kontrolka pokazuje `START`, nie pusty tekst.

---

## 2️⃣ ⚠️ Pułapka z bliska: model i UI rozjeżdżają się

### 🎣 Dlaczego to ważne

W #20 pokazałem wersję z `debounce('blur')` (wpis wraca po blurze). Z `debounce(300)` jest gorzej:
**wpis wraca sam, po 300 ms, bez żadnego zdarzenia — a UI o tym nie wie**. Zmierzone
(`FormField.reset()` zaraz po wpisaniu `TYPED`, kolejno: po resecie, po 300 ms, po blurze):

```text
MEASURE reset-naive-300: {
  "typing":     {"ui":"TYPED","model":"START","dirty":true,"touched":false},
  "afterReset": {"ui":"START","model":"START","dirty":true,"touched":false},
  "later":      {"ui":"START","model":"TYPED","dirty":true,"touched":false},
  "laterTick":  {"ui":"START","model":"TYPED","dirty":true,"touched":false},
  "afterBlur":  {"ui":"TYPED","model":"TYPED","dirty":true,"touched":true} }
```

Po 300 ms **model ma `TYPED`, a pole na ekranie `START`**. Użytkownik widzi „wyczyszczone” pole,
kliknie „Zapisz” i wyśle coś, czego nie widzi. Rozjazd zostaje do pierwszego blura; dopiero wtedy
UI dogania model. Dodatkowy `TestBed.tick()` (`laterTick`) nic nie zmienia.

Dlaczego? To **wniosek z kodu**, nie z debuggera: w `cvaControlCreate` reset kontrolki zapisuje
w pamięci podręcznej bindingu starą wartość, a efekt odświeżający UI zależy od sygnału
`controlValue`, który się nie zmienił (użytkownik już wpisał `TYPED`). Efekt odpala się znów dopiero
gdy zmieni się inny odczytywany stan, np. `touched`.

---

## 3️⃣ Obejście: najpierw `FieldState.reset(wartość)`, potem `FormField.reset()`

### 🎣 Dlaczego to ważne

Zapis wartości z kodu (nie z UI) **kasuje oczekujący wpis debounce** — to ustalenie z #15
(„zapis programowy omija debounce i kasuje oczekujący wpis UI”). `FieldState.reset('')` wykorzystuje
dokładnie ten mechanizm, a przy okazji zeruje `dirty`/`touched`:

```typescript
safeReset(): void {
  this.f.code().reset('');   // model = '', dirty/touched = false, oczekujący wpis skasowany
  this.field().reset();      // kontrolka dostaje writeValue('')
}
```

Zmierzone (ten sam scenariusz: wpis `TYPED` w oknie debounce, potem obejście):

```text
MEASURE reset-workaround-300:  {"afterReset":{"ui":"","model":"","dirty":false,"touched":false},
                                "later":     {"ui":"","model":"","dirty":false,"touched":false},
                                "afterBlur": {"ui":"","model":"","dirty":false,"touched":true}}
MEASURE reset-workaround-blur: {"afterBlur":{"ui":"","model":"","dirty":false,"touched":true}}
```

Nic nie wraca — ani po 1 s, ani po blurze, zarówno dla `debounce(300)`, jak i `debounce('blur')`.
Warianty, które sprawdziłem, żeby wiedzieć, które z dwóch wywołań jest potrzebne:

| Wariant | Wynik |
|---|---|
| `value.set('')` + `FormField.reset()` | UI i model puste, ale **`dirty()` zostaje `true`** |
| samo `FieldState.reset('')` (bez `FormField.reset()`) | UI i model puste, `dirty` `false` — UI odświeża się samo |
| `FieldState.reset('')` + `FormField.reset()` | jak wyżej; dwa wywołania są bezpieczne |

Wniosek praktyczny: **wystarczy samo `FieldState.reset(wartość)`**. `FormField.reset()` dokładam
wtedy, gdy kontrolka ma własny stan wewnętrzny, który `writeValue` ma wyzerować (błąd parsowania w
`transformedValue`, #9). Co ważne: bez podania wartości `FieldState.reset()` modelu nie zmieni —
„wyczyść formularz” wymaga wartości.

Test w DOM (`SignupForm`, przyciski „naiwnie” / „obejście”) dodatkowo pokazuje: naiwny przycisk po
zatwierdzonym wpisie `FREE` zostawia `model="FREE"` i `input="FREE"` — nie czyści niczego.

---

## 4️⃣ `NG_ASYNC_VALIDATORS` pod `[formField]` — cisza

### 🎣 Dlaczego to ważne

W #20 stare `NG_VALIDATORS` na elemencie z `[formField]` działały. Naturalne pytanie: a async?
`CodeAvailableValidator` to klasyczna dyrektywa z `NG_ASYNC_VALIDATORS`, `validate()` zwraca
`Observable` i pyta „serwer”, czy kod jest zajęty (`TAKEN` = zajęty). Kontrola (ten sam komponent,
ten sam walidator) pod klasycznym `[formControl]`, potem pod `[formField]`:

```text
MEASURE reactive-forms-control: {"validateCalls":["TAKEN"],"requests":["TAKEN"],"errors":{"taken":true},"status":"INVALID"}
MEASURE formfield-legacy-async: {"validateCalls":[],"requests":[],"model":"TAKEN2","errors":[],"valid":true,"pending":false}
```

Pod `[formField]` walidator **nie jest wołany ani razu** — ani przy montowaniu, ani po wpisie i
debounce. Pole jest `valid`, `pending` jest `false`, żadnego błędu, żadnego ostrzeżenia w konsoli
testu. Potwierdzenie w źródle: `fesm2022/signals.mjs` w ogóle nie odwołuje się do
`NG_ASYNC_VALIDATORS` (grep), a `cvaControlCreate` pobiera tylko `NG_VALIDATORS` (`self: true`).

Konsekwencja przy migracji formularza: „unikalność loginu/kodu/NIP” przestaje być sprawdzana,
formularz przechodzi, a błąd wyjdzie dopiero na backendzie. W .NET to odpowiednik sytuacji, w której
po zmianie z `IValidatableObject` na inny pipeline walidator asynchroniczny po prostu nie jest
rejestrowany — kompiluje się, nic nie ostrzega.

---

## 5️⃣ Zamiennik: `validateAsync` + `resource()`

### 🎣 Dlaczego to ważne

Walidację przenosimy do schematu (znane z #5/#13, tu na polu obsługiwanym przez CVA). Zasada „zdarzenie
→ debounce → zapytanie → wynik” jest jawna w kodzie:

```typescript
validateAsync(p.code, {
  params: (ctx) => ctx.value() || undefined,           // undefined = nie waliduj
  factory: (params) => resource({ params, loader: ({ params: code, abortSignal }) => api.check(code, abortSignal) }),
  onSuccess: (taken) => (taken ? { kind: 'taken', message: 'Kod jest zajęty' } : undefined),
  onError: () => ({ kind: 'check-failed', message: 'Nie udało się sprawdzić kodu' }),
});
```

Zmierzona oś czasu (wpis `TAKEN`, `debounce(300)`, „serwer” 200 ms):

```text
MEASURE validate-async-timeline: {"t0":  {"model":"","pending":false,"requests":[]},
                                  "t299":{"model":"","requests":[]},
                                  "t300":{"model":"TAKEN","pending":true,"requests":["TAKEN"]},
                                  "t500":{"pending":false,"errors":["taken"],"valid":false}}
MEASURE validate-async-free: {"requests":["FREE"],"errors":[],"valid":true}
```

Trzy szybkie wpisy (`F`, `FR`, `FREE`) → **jedno** zapytanie. Zwróć uwagę na `t0`: w oknie debounce
walidacja nie wie jeszcze o nowej wartości, więc `pending` jest `false`, a pole `valid`
(w #13 `validateHttp` zachowywał się inaczej — tam `pending` startował w oknie debounce; tu
`debounce` jest regułą schematu na polu, nie opcją walidatora). To trzeba uwzględnić w UI:
przycisk „Zapisz” nie powinien opierać się wyłącznie na `valid()`, jeśli ktoś może kliknąć
w oknie 300 ms (zob. #15: `submit()` w trakcie debounce waliduje stary model).

Obejście z punktu 3 działa też **w trakcie lecącego zapytania**: wpis `TAKEN`, po 300 ms zapytanie
w locie (`pending: true`), kliknięcie „obejście” → po 1 s `model: ""`, `pending: false`,
błędy `["required"]` — błąd `taken` zniknął.

```text
MEASURE signup-safe-in-flight: {"inFlight":{"pending":true,"requests":["TAKEN"]},
                                "after":{"model":"","pending":false,"errors":["required"],"input":""}}
```

---

## 6️⃣ Weryfikacja — prawdziwy output

Node w tej sesji: **v22.14.0**, a CLI 22.2.2 wymaga `>=22.22.3`. Obejście jak w #9–#20:
lokalna jednoliniowa edycja stałej `SUPPORTED_NODE_VERSIONS` w
`node_modules/@angular/cli/src/utilities/node-version.js` (`^22.22.3` → `^22.14.0`), poza repo
(`node_modules/` w `.gitignore`), do powtórzenia po każdym `npm install`/`npm ci`. To, że obejście
nie wpływa na wyniki, jest założeniem. Instalacja zgłasza dużo ostrzeżeń `EBADENGINE`.

```text
$ npm install --no-audit --no-fund
added 279 packages in 56s

$ npm run build
main-7L7H5UNI.js    | main   | 208.59 kB | 57.51 kB
Application bundle generation complete. [6.896 seconds]

$ npm test
 Test Files  2 passed (2)
      Tests  14 passed (14)
```

Test mutacyjny: (a) z `safeReset()` usunąłem `FieldState.reset('')`, (b) ze schematu usunąłem
`debounce(p.code, 300)`. Padły **4** testy (oś czasu, „szybkie wpisy = jedno zapytanie”, obejście w
locie, obejście po zatwierdzonym wpisie). Po przywróceniu 14/14. Przy okazji potwierdziło to, że
obejście nie przechodzi „przypadkiem”: bez `FieldState.reset('')` model zostaje `FREE`.

Przy pierwszym uruchomieniu jeden test padł — moje założenie, że po 300 ms UI pokaże `TYPED`.
Pokazało `START` (punkt 2). Poprawiłem test do tego, co jest naprawdę.

### ⚠️ Co jest niezweryfikowane (wprost)

- **`ng serve`/przeglądarka**: zdarzenia `input`/`blur` są syntetyczne (jsdom); realny fokus,
  autouzupełnianie i IME nie były sprawdzane.
- Wyjaśnienie rozjazdu UI/model (punkt 2) to **wniosek z czytania kodu**, nie z debuggera.
- `NG_ASYNC_VALIDATORS` zmierzone tylko na CVA; natywny `<input>` z takim walidatorem nie był testowany.
- CVA z `ngModel`/`FormControl` jednocześnie z `[formField]`, mieszane formularze.
- Anulowanie lecącego zapytania przez `abortSignal` przy resecie — widać efekt (`taken` znika),
  nie mierzyłem samego sygnału abort.
- SSR/hydration, `mapResponse()` w `@ngrx/effects`, `aria-*` czytnikiem ekranu.

---

## 🧭 Do zapamiętania

| Potrzeba | Co zrobić |
|---|---|
| „Wyczyść formularz” w trakcie debounce | `f.pole().reset(wartośćPusta)` — kasuje oczekujący wpis i zeruje `dirty`/`touched` |
| `FormField.reset()` | tylko odświeża kontrolkę z modelu; **nie czyści** i nie anuluje wpisu |
| `value.set(...)` zamiast `reset(value)` | wpis skasowany, ale `dirty()` zostaje `true` |
| Stary async walidator (`NG_ASYNC_VALIDATORS`) | pod `[formField]` **nieużywany, bez ostrzeżenia** — przepisz na `validateAsync` |
| Unikalność przez serwer | `validateAsync` + `resource()`; `pending` w oknie debounce jest jeszcze `false` |
| Migracja formularza z CVA | testuj nie tylko „kompiluje się”, ale „walidator jest wołany” (licznik wywołań) |

**Następnym razem (propozycja):** SSR/hydration formularza (`renderApplication` w Node), `mapResponse()`
w `@ngrx/effects`, `ng serve` w prawdziwej przeglądarce (jeśli będzie dostępna), CVA z `ngModel`.

---

## 📎 Jak uruchomić

Zobacz [`code/README.md`](code/README.md).

---

<div align="center">

[← wszystkie artykuły: 🅰️ Angular](../README.md) · [spis rubryk](../../../README.md)

</div>
