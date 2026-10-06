<div align="center">

# 📰 TECH PRASÓWKA
### Wydanie #13 rubryki Angular — 6 października 2026

![Angular](https://img.shields.io/badge/Angular-DD0031?style=for-the-badge&logo=angular&logoColor=white)
![Signal Forms](https://img.shields.io/badge/Signal_Forms-validateHttp-1976D2?style=for-the-badge)

## `validateHttp`: walidacja pola „czy ta nazwa jest wolna?" jednym wywołaniem — i trzy rzeczy, które zmierzyłem zamiast uwierzyć

</div>

---

> _"Async validation for a field only runs once all synchronous validation is passing."_
> — komentarz nad `validateHttp` w `@angular/forms` 22.2.1. Zdanie na pozór oczywiste;
> dziś sprawdzam, co z niego wynika dla liczby requestów, i znajduję jedną pułapkę, której
> dokumentacja nie wymienia.

W wydaniu #5 (28.09) zrobiłem asynchroniczną walidację przez `validateAsync` + `resource()` z
własnym loaderem. Dziś ten sam problem ("czy login/nazwa jest zajęta?") w wersji, którą
pewnie 90% z Was napisze w praktyce: **`validateHttp`** — wariant `validateAsync`
wyspecjalizowany pod `HttpClient`. Dla .NET developera: to jak różnica między ręcznym
`IAsyncValidator`, w którym sam woła się `HttpClient`, a gotowym `MustAsync(...)` z
FluentValidation, które już wie o anulowaniu i debounce.

| | |
|---|---|
| 🧱 Stack | `@angular/core`/`common`/`forms` **22.2.1**, `@angular/cli` 22.2.1, TypeScript **6.0.3**, `rxjs` 7.8.x (dziś bez własnych operatorów) |
| 🖥️ Środowisko | Node **v22.14.0**, npm 10.9.2, Vitest **5.0.3** + jsdom, `HttpTestingController` |
| ✅ Weryfikacja | `npm ci` (281 pakietów, 10 s), `ng build` OK (5,2 s, 232,62 kB), `ng test` **13/13** (3 pliki) + test mutacyjny |
| 📦 Kod | [`code/`](code/) — formularz „nazwa projektu": dwa schematy (poprawny i naiwny) do porównania |

**Plan:** (1) co `validateHttp` faktycznie jest (czytam skompilowane źródło), (2) trzy
pomiary: liczba requestów, kodowanie parametrów, `when`, (3) pułapka z pierwszą wartością,
(4) weryfikacja i czego NIE sprawdziłem.

---

## 1️⃣ Co to właściwie jest — i jak wygląda w użyciu

### 🎣 Dlaczego to ważne

Najczęstsza asynchroniczna walidacja w prawdziwych formularzach to „zapytaj serwer": login,
e-mail, numer faktury, slug. Bez wsparcia frameworka każdy pisze to po swojemu i każdy robi
te same błędy: request na każdy klawisz, spóźniona odpowiedź nadpisująca nowszą, request
wysyłany dla wartości, która i tak jest niepoprawna składniowo. `validateHttp` zamyka te
trzy dziury w jednej deklaracji.

Źródło (`@angular/forms/fesm2022/signals.mjs`), cała implementacja:

```javascript
function validateHttp(path, opts) {
  validateAsync(path, {
    params: opts.request,
    debounce: opts.debounce,
    factory: request => httpResource(request, opts.options),
    onSuccess: opts.onSuccess,
    onError: opts.onError,
    when: opts.when
  });
}
```

Czyli: `validateAsync` (wydanie #5) + `httpResource` (wydanie #3). Nic nowego do nauki w
mechanice — nowe jest tylko to, że składa się to w jedną linijkę. A `debounce` w
`validateAsync` to z kolei `debounced()` z rdzenia Angulara (w `.d.ts`: `@experimental 22.0`
— sama `validateHttp` jest `@publicApi 22.0`, ale pod spodem siedzi coś eksperymentalnego).

Użycie (`project.schema.ts`):

```typescript
export const projectSchema = schema<ProjectModel>((p) => {
  required(p.name, { message: 'Nazwa jest wymagana' });
  minLength(p.name, 3, { message: 'Nazwa musi mieć co najmniej 3 znaki' });

  validateHttp<string, ExistsResponse>(p.name, {
    request: (ctx) => ({ url: '/api/projects/exists', params: { name: ctx.value() } }),
    debounce: 300,
    when: ({ valueOf }) => !valueOf(p.offline),
    onSuccess: (res) =>
      res.taken ? { kind: 'taken', message: `Nazwa jest zajęta - spróbuj "${res.suggestion}"` } : undefined,
    onError: () => ({ kind: 'check-failed', message: 'Nie udało się sprawdzić unikalności nazwy' }),
  });
});
```

`onSuccess` zwraca błąd (albo `undefined`, gdy wszystko OK); `onError` — jak
zareagować, gdy sam request padł. Oba są **wymagane** przez typ `HttpValidatorOptions`
(bez `?`) — nie da się zapomnieć o ścieżce błędu sieci.

---

## 2️⃣ Trzy pomiary

Testy działają na samym drzewie pól (`form(model, schema)` w kontekście wstrzykiwania) +
`HttpTestingController`, bez DOM — dzięki temu widać dokładnie, ile requestów wyszło.

### a) Sync blokuje HTTP, debounce zbija serię w jeden request

Wpisuję znak po znaku `pra → pras → prase → prasow` co 100 ms, raz w schemacie z
`debounce: 300` i raz w „naiwnym" (bez debounce, URL sklejany ręcznie):

| Wariant | Requestów | Z czego anulowanych |
|---|---|---|
| `projectSchema` (debounce 300) | **1** (`name=prasow`) | 0 |
| `naiveProjectSchema` | **4** | 3 |

Anulowane — bo `httpResource` sam anuluje poprzednie żądanie przy zmianie parametrów
(spóźniona odpowiedź nie nadpisze nowszej; osobny test to potwierdza). Dwa dodatkowe
fakty z testów: nazwa `ab` (za krótka, `minLength`) = **0 requestów** nawet po sekundzie i
`pending() === false`; a w oknie debounce `pending()` jest już `true` przy 0 wysłanych
requestach — spinner „Sprawdzam…" pojawi się od razu, nie dopiero po 300 ms.

**Test mutacyjny** (żeby upewnić się, że dowód nie jest przypadkowy): usunąłem
`debounce: 300` z `projectSchema` i odpaliłem testy — padły 3 (dwa na schemacie, jeden w DOM):

```text
- "/api/projects/exists?name=prasow"            (oczekiwane: 1 request)
+ "/api/projects/exists?name=pra", "...name=pras", "...name=prase", "...name=prasow"
```

Zmiana wycofana, po powrocie 13/13.

### b) `{url, params}` zamiast sklejania stringa

Nazwa `Ala & Ola` (znak `&` w wartości to klasyczny bug „parametr ucięty w połowie"):

```text
projectSchema      -> /api/projects/exists?name=Ala%20%26%20Ola
naiveProjectSchema -> /api/projects/exists?name=Ala & Ola
```

`request` może zwrócić sam `string` (wtedy to GET na ten URL — `request` w `.d.ts`:
`string | HttpResourceRequest | undefined`), ale gdy w grę wchodzi wartość od użytkownika,
zwracaj obiekt z `params` — kodowanie robi Angular. Dla .NET developera: to różnica między
`$"?name={name}"` a `QueryHelpers.AddQueryString`.

### c) `when` — kiedy NIE sprawdzać

`when: ({ valueOf }) => !valueOf(p.offline)` wyłącza walidację, gdy sąsiednie pole
(checkbox „pracuję offline") jest zaznaczone. Test: `offline = true` + nazwa `prasowka`
(zajęta) → po sekundzie **0 requestów** i pole `valid`; po odznaczeniu checkboxa po 300 ms
leci request i pojawia się błąd `taken`. `valueOf(path)` czyta wartość innego pola w
kontekście reguły, więc walidacja zależy reaktywnie od całego modelu, nie tylko od siebie.

---

## 3️⃣ Pułapka: pierwsza wartość nie jest debounce'owana

### 🎣 Dlaczego to ważne

Pierwszy napisany przeze mnie test — „ustaw `pra`, poczekaj, policz requesty" — pokazał
**1 request natychmiast**, mimo `debounce: 300`. Powód widać w implementacji `debounced()`
w rdzeniu: `computation` zwraca `previous.value`, gdy poprzednia wartość istnieje, a **pierwsza
wartość przechodzi od razu**. Metadane walidatora są leniwe — jeśli nikt nie przeczytał
pola przed `set('pra')`, to `'pra'` JEST pierwszą wartością i leci bez czekania.

W prawdziwym UI szablon czyta `errors()`/`pending()` od pierwszego renderu (wtedy pierwszą
wartością jest `undefined`, bo pusta nazwa nie przechodzi `required`), więc debounce
działa. Sprawdziłem oba przypadki:

```text
pole przeczytane przed set('pra'):   0 requestów po 100 ms, pending() = true
pole NIE przeczytane przed set('pra'): 1 request po 0 ms,   pending() = true
```

Wniosek praktyczny: w testach jednostkowych schematów **najpierw przeczytaj pole**
(`f.name().errors()`), inaczej mierzysz coś innego niż użytkownik. Ten sam test w repo
nazywa się „PUŁAPKA: pierwsza wartość NIE jest debounce'owana…" i pilnuje zachowania.
(To obserwacja z Angulara 22.2.1 — traktuję ją jako szczegół implementacji, nie kontrakt.)

---

## 4️⃣ Weryfikacja — prawdziwy output

Node w tej sesji: **v22.14.0** — Angular CLI 22.2.1 wymaga `>=22.22.3`, więc pierwsze
`ng test` skończyło się komunikatem:

```text
Node.js version v22.14.0 detected.
The Angular CLI requires a minimum Node.js version of v22.22.3 or v24.15.0 or v26.0.0.
```

Obejście jak w #9/#12: lokalna edycja progu w `node_modules/@angular/cli/src/utilities/node-version.js`
(poza repo, `node_modules/` jest w `.gitignore`); trzeba je powtórzyć po każdym `npm ci`.
Wynik (z czystego `npm ci`):

```text
$ npm ci --no-audit --no-fund
added 281 packages in 10s

$ npm run build
main-PS6CR6TM.js    | main   | 232.62 kB | 64.96 kB
Application bundle generation complete. [5.199 seconds]

$ npm test
 Test Files  3 passed (3)
      Tests  13 passed (13)
```

13 testów: 10 na schemacie (sync blokuje HTTP, debounce 1 vs 4, `pending` w oknie debounce,
pułapka pierwszej wartości, `taken`, wolna nazwa, HTTP 500 → `check-failed` z odzyskaniem po
zmianie wartości, `when`, kodowanie `params`, anulowanie spóźnionego requestu), 2 w DOM
(komunikat „Sprawdzam…" w oknie debounce, „Nazwa wolna."), 1 smoke test aplikacji.

Po drodze dwa błędy własne: pierwsze wersje testów po `flush()` używały samego
`TestBed.tick()` i padały (5 z 10) — `httpResource` rozstrzyga się asynchronicznie, trzeba
`await advanceTimersByTimeAsync(0)` przed `tick()`. Jak zwykle: `ng test`, nie goły `vitest`.

### ⚠️ Co jest niezweryfikowane (wprost)

- **`ng serve`/przeglądarka** — brak przeglądarki; interceptor `mock-api.interceptor.ts` jest
  napisany pod ręczne próby (`prasowka`, `Ala & Ola`, `boom`), ale nie był uruchomiony.
- `debounce` jako funkcja lub `'blur'` w `validateHttp`, `request` zwracające `undefined`,
  przekazanie `options` (`HttpResourceOptions`) — widziane w typach, bez testów.
- SSR/hydration, `mapResponse()` w `@ngrx/effects`, pozostałe pola `FormUiControl`.

---

## 🧭 Do zapamiętania

| Potrzeba | Narzędzie |
|---|---|
| Walidacja „zapytaj serwer" na polu | `validateHttp(path, { request, onSuccess, onError })` — `onError` wymagany przez typ |
| Nie bombardować API przy pisaniu | `debounce: 300` — zmierzone: 4 zmiany = 1 request (bez: 4, 3 anulowane) |
| Nie wysyłać requestu dla złej składni | nic nie robisz — sync (`required`/`minLength`) blokuje HTTP sam |
| Wartość od użytkownika w URL | `request: ctx => ({ url, params })`, nie sklejanie stringa |
| Wyłączyć sprawdzanie warunkowo | `when: ({ valueOf }) => ...` |
| Test schematu bez DOM | najpierw przeczytaj pole, potem `set()` — inaczej pierwsza wartość omija debounce |

**Następnym razem (propozycja):** `debounce` jako funkcja/`'blur'`, `request` zwracające
`undefined`, pozostałe opcjonalne pola `FormUiControl` (`required`/`pattern`/`readonly`/
`hidden`), SSR/hydration, `mapResponse()` w `@ngrx/effects`.

---

## 📎 Jak uruchomić

Zobacz [`code/README.md`](code/README.md).

---

<div align="center">

[← wróć do wydania (wszystkie rubryki)](../README.md) · [spis wydań](../../../README.md)

</div>
