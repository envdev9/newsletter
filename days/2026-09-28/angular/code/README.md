# Kod do wydania Angular z 28.09.2026 — Signal Forms + `resource()` z własnym loaderem

Pełny artykuł: [`../ARTICLE.md`](../ARTICLE.md).

Wymagania: **Node.js 20+** (weryfikowane na v22.23.3) i **npm** (weryfikowane na 10.9.9).
Wersje: `@angular/core` i `@angular/forms` **22.2.0** (w tym podpakiet `@angular/forms/signals`),
TypeScript **6.0.3**, `vitest` **5.0.2** (jsdom, bez przeglądarki).

## Fragment prasówki, którego dotyczy ten kod

> **`form()`** owija istniejący `signal()` w drzewo pól (`FieldTree`) - NIE kopiuje danych.
> Ustawienie `registrationForm.username().value.set(...)` zmienia oryginalny model.
>
> **Walidatory sync** (`required`, `minLength`, `pattern`, `email`, ...) wołane są wewnątrz
> funkcji schema, jak reguły FluentValidation, ale reaktywnie i bez osobnego obiektu walidatora.
>
> **`[formField]`** dwukierunkowo wiąże natywny `<input>`/`<textarea>` z polem (wartość,
> `disabled`, `errors`, `touched`...). **`[formRoot]`** spina `<form>`: `novalidate` +
> przechwycenie `submit` + wywołanie `submit()` na drzewie pól (wymaga opcji `submission`
> przekazanej do `form()`).
>
> **`validateAsync`** + `factory: (params) => resource({ params, loader })` to walidacja
> asynchroniczna zbudowana wprost na `resource()` z własnym loaderem i `AbortSignal` -
> **i rusza dopiero, gdy walidacja synchroniczna przechodzi** (nie trzeba tego pilnować ręcznie).
>
> **`submit()`** (wołane przez `[formRoot]`) zwraca listę błędów z `action`; błąd wskazujący
> `fieldTree` (np. `f.email`) trafia na konkretne pole formularza - odpowiednik
> `ModelState.AddModelError(nameof(Model.Email), ...)` w ASP.NET Core.

## Struktura

```
src/app/
  app.ts                        -> host: <app-registration-form />
  registration-form.ts          -> formularz Signal Forms (login/e-mail/hasło, sync + async)
  username-availability.ts      -> fake-backend "czy login zajęty" (AbortSignal, 300ms)
  registration-backend.ts       -> fake-backend rejestracji (200ms, jeden zajęty e-mail)
  *.spec.ts                     -> 15 testów (Vitest + jsdom): backendy osobno + komponent
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

## Realna weryfikacja

```text
$ npm ci --no-audit --no-fund
added 274 packages in 12s

$ npm run build
main-7KZRZIW3.js    | main    | 208.97 kB |  57.63 kB
Application bundle generation complete. [7.678 seconds]

$ npm test
 Test Files  4 passed (4)
      Tests  15 passed (15)
   Duration  3.14s
```

Login `admin`/`root`/`angular` jest "zajęty" (fake-backend), e-mail `taken@example.com` jest
"już zarejestrowany" (fake-backend rejestracji) - użyj ich w `ng serve`, żeby ręcznie zobaczyć
błędy walidacji, jeśli akurat masz pod ręką przeglądarkę (ja nie miałem - patrz artykuł,
sekcja "co niezweryfikowane").

Niezweryfikowane: `ng serve`/przeglądarka, blokada współbieżnego `submit()`, `validateHttp`,
SSR/hydration, `tapResponse`.
