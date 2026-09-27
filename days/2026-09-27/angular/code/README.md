# Kod do wydania Angular z 27.09.2026 — router: resolver, `withComponentInputBinding`, `@defer`

Pełny artykuł: [`../ARTICLE.md`](../ARTICLE.md).

Wymagania: **Node.js 20+** (weryfikowane na v22.23.3) i **npm**. Wersje: `@angular/core` i
`@angular/router` **22.2.0**, `rxjs` **7.8.2**, `vitest` **4.1.11** (jsdom, bez przeglądarki).

## Fragment prasówki, którego dotyczy ten kod

> **`withComponentInputBinding`.** Jedna flaga w `provideRouter` i router wypełnia `input()`-y
> komponentu trasy: parametr ścieżki (`/articles/:id` → `id`, zawsze `string`), query param
> (`?tab=comments` → `tab`, `undefined` gdy brak) i dane resolvera (`resolve: { article }` →
> `article`). Zmiana samego query paramu nie tworzy komponentu na nowo.
>
> **Resolver** (`ResolveFn`) to funkcja z `inject()`: router czeka na dane przed aktywacją
> trasy. Zwrócenie `RedirectCommand` to czysty sposób na "nie znaleziono" (tu → `/not-found`).
> Kompromis: resolver blokuje nawigację.
>
> **`@defer (when ...)`** wycina fragment szablonu do osobnego chunku JS ładowanego na
> żądanie; `@loading`/`@error` opisują stany pośrednie. Pułapka: literalne `@` w szablonie
> trzeba zapisać jako `&#64;`.

## Struktura

```
src/app/
  app.config.ts        -> provideRouter(routes, withComponentInputBinding())
  app.routes.ts        -> trasy (lazy loadComponent, resolve, /not-found)
  article.resolver.ts  -> ResolveFn + RedirectCommand
  articles.service.ts  -> dane w pamięci z delay(50)
  article-list.ts      -> lista
  article-detail.ts    -> input()-y z routera + @defer
  article-comments.ts  -> komponent ładowany przez @defer
  app.spec.ts          -> 6 testów (RouterTestingHarness)
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
added 290 packages in 11s

$ npm run build
main-NBXYMUTJ.js    | main             | 235.22 kB
chunk-TNazxX7A.js   | article-comments |   814 bytes   (osobny chunk z @defer)
Application bundle generation complete. [5.789 seconds]

$ npm test
 Test Files  1 passed (1)
      Tests  6 passed (6)
```

Niezweryfikowane: `ng serve`/przeglądarka, `DeferBlockFixture`, inne wyzwalacze `@defer`.
