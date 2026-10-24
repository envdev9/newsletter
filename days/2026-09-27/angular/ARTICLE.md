<div align="center">

# 📰 TECH PRASÓWKA
### Wydanie #4 rubryki Angular — 27 września 2026

![Angular](https://img.shields.io/badge/Angular-DD0031?style=for-the-badge&logo=angular&logoColor=white)

## Router bez boilerplate'u: resolvery, `withComponentInputBinding` i `@defer`

</div>

---

> _"Komponent, który sam wyciąga parametry z URL-a, sam pobiera dane i sam obsługuje
> 'nie znaleziono', ma trzy powody do zmiany. Dobry routing zostawia mu jeden: wyświetlić
> dane."_

Wczoraj (#3) był stan z HTTP: `linkedSignal`, `httpResource`, `rxMethod`. Dziś wchodzimy
piętro wyżej: **jak dane trafiają do komponentu przez router**. Zakładam, że znasz
ASP.NET Core (routing, model binding, filtry), ale nie Angulara.

| | |
|---|---|
| 🧱 Stack | `@angular/core` i `@angular/router` **22.2.0**, `rxjs` **7.8.2**, TypeScript **6.0.3** |
| 🖥️ Środowisko | Node **v22.23.3**, testy: Vitest **4.1.11** + jsdom |
| ✅ Weryfikacja | `npm ci` OK, `ng build` OK, `ng test` **6/6** (output w sekcji 4) |
| 📦 Kod | [`code/`](code/) - lista artykułów + szczegóły z resolverem i leniwymi komentarzami |

**Plan:** (1) `withComponentInputBinding` - router wypełnia `input()`-y, (2) resolver z
`RedirectCommand`, (3) `@defer` sterowany query paramem, (4) weryfikacja i luki.

---

## 1️⃣ `withComponentInputBinding`: URL jako model binding

### 🎣 Dlaczego to ważne

Dawniej komponent wstrzykiwał `ActivatedRoute`, subskrybował `paramMap`, `queryParamMap`
i `data`, i pamiętał o `takeUntilDestroyed`. To odpowiednik ręcznego czytania
`HttpContext.Request.RouteValues` w kontrolerze zamiast `[FromRoute]`. Jedna flaga w
`provideRouter` zamienia to w **model binding**:

```typescript
provideRouter(routes, withComponentInputBinding())
```

Teraz komponent trasy deklaruje zwykłe `input()`-y, a router je wypełnia:

```typescript
export class ArticleDetail {
  readonly id      = input.required<string>();        // <- /articles/:id
  readonly article = input.required<Article>();       // <- resolve: { article: ... }
  readonly tab     = input<string | undefined>();     // <- ?tab=comments
}
```

Wiązanie idzie **po nazwie**: parametr ścieżki, query param i klucz z `resolve`/`data`
o tej samej nazwie co input. To sygnały, więc `computed(() => this.tab() === 'comments')`
reaguje na zmianę URL-a bez żadnej subskrypcji.

### ⚠️ Pułapki (zweryfikowane testami)

- Parametr ścieżki jest **zawsze `string`** - `id = input.required<string>()`, nie `number`.
  Test: `expect(cmp.id()).toBe('2')`.
- Brakujący opcjonalny query param daje `undefined` (test: `cmp.tab()` jest `undefined`), więc
  typuj input jako `T | undefined`.
- Zmiana samego query paramu **nie tworzy komponentu na nowo** - ta sama instancja dostaje
  nową wartość inputu (test: `routeDebugElement.componentInstance` to ten sam obiekt).

---

## 2️⃣ Resolver: dane przed wejściem na trasę

### 🎣 Dlaczego to ważne

Bez resolvera komponent renderuje się pusty, pobiera dane, miga spinnerem i musi obsłużyć
"nie ma takiego id". Z resolverem router **czeka z aktywacją trasy** na dane, a komponent
dostaje gotowy `article` (typ z `input.required`, bez `undefined` i bez `@if`). To odpowiednik
filtra akcji, który ładuje encję i zwraca 404, zanim kontroler ruszy.

```typescript
export const articleResolver: ResolveFn<Article> = (route) => {
  const router = inject(Router);
  const notFound = new RedirectCommand(router.parseUrl('/not-found'));
  const id = Number(route.paramMap.get('id'));
  if (!Number.isInteger(id)) return notFound;
  return inject(ArticlesService).get(id).pipe(map((a) => a ?? notFound));
};
```

```typescript
{ path: 'articles/:id', resolve: { article: articleResolver }, loadComponent: ... }
```

Resolver to zwykła **funkcja** (`ResolveFn`), a `inject()` działa w niej, bo router woła ją
w kontekście wstrzykiwania. Może zwrócić wartość, `Promise` albo `Observable`; przy
Observable router bierze pierwszą wyemitowaną wartość.

**`RedirectCommand`** to czysty sposób na "nie znaleziono": zamiast rzucać wyjątek (co
kończy się błędem nawigacji), resolver zwraca komendę przekierowania. Testy: `/articles/999`
oraz `/articles/abc` kończą na `/not-found` (sprawdzone przez `Location.path()`).

Kompromis: resolver **blokuje nawigację** - użytkownik nie widzi nowego ekranu, dopóki dane
nie przyjdą. Przy wolnym API lepsze bywa `httpResource` z wczoraj (natychmiast szkielet,
potem dane). Resolver wybieraj, gdy bez danych ekran nie ma sensu (np. 404 musi być
decyzją routera).

---

## 3️⃣ `@defer`: ciężki fragment dopiero na żądanie

### 🎣 Dlaczego to ważne

Sekcja komentarzy jest potrzebna mniejszości użytkowników. `@defer` pozwala kompilatorowi
wyciąć ją do **osobnego chunku JS**, który ładuje się dopiero, gdy warunek jest spełniony.
Bez `import()` w kodzie i bez ręcznego `ViewContainerRef`.

```html
@if (showComments()) {
  @defer (when showComments()) {
    <app-article-comments [articleId]="article().id" />
  } @loading (minimum 10ms) {
    <p>Wczytuję moduł komentarzy...</p>
  } @error {
    <p>Nie udało się wczytać komentarzy.</p>
  }
} @else {
  <a [routerLink]="[]" [queryParams]="{ tab: 'comments' }">Pokaż komentarze</a>
}
```

Spójność zestawu: `?tab=comments` (query param) → input `tab` (binding routera) → `computed`
→ `@defer (when ...)`. Adres URL steruje ładowaniem kodu, a link da się wkleić koledze.

Dowód, że to naprawdę osobny chunk - wynik `ng build`:

```text
Lazy chunk files | Names            |  Raw size
chunk-TNazxX7A.js | article-comments |   814 bytes
```

Komponent w `@defer` musi być `standalone` i wykorzystywany **tylko** w bloku (inaczej
kompilator zostawia go w głównym chunku). Inne wyzwalacze, które istnieją w Angularze, a
których tu nie użyłem: `on viewport`, `on idle`, `on interaction`, `on hover`, `on timer`,
`prefetch on ...` (z pamięci, nie testowane w tym projekcie).

### ⚠️ Pułapka z realnego builda: `@` w szablonie

Mój pierwszy `ng build` padł. Nagłówek szablonu `<h1>... i @defer</h1>` kompilator
potraktował jako początek bloku:

```text
✘ [ERROR] NG5002: Incomplete block "defer". If you meant to write the @ character,
  you should use the "&#64;" HTML entity instead.
```

Każde literalne `@` w szablonie (np. `user@firma.pl` w tekście - uwaga na maile) to teraz
składnia sterująca. Zamień na `&#64;`.

---

## 4️⃣ Weryfikacja - prawdziwy output

```text
$ npm ci --no-audit --no-fund
added 290 packages in 11s

$ npm run build
Initial chunk files | Names            |  Raw size | Estimated transfer size
main-NBXYMUTJ.js    | main             | 235.22 kB |                64.01 kB
styles-YDSRV2IW.css | styles           | 186 bytes |               186 bytes

                    | Initial total    | 235.41 kB |                64.20 kB

Lazy chunk files    | Names            |  Raw size | Estimated transfer size
chunk-BurTXq99.js   | article-detail   |   1.57 kB |               803 bytes
chunk-KN7SEQUX.js   | -                | 957 bytes |               957 bytes
chunk-CLE9I8P3.js   | article-list     | 863 bytes |               863 bytes
chunk-TNazxX7A.js   | article-comments | 814 bytes |               814 bytes
chunk-ChiBr1vl.js   | not-found        | 406 bytes |               406 bytes

Application bundle generation complete. [5.789 seconds]

$ npm test
 Test Files  1 passed (1)
      Tests  6 passed (6)
   Duration  3.19s
```

(Pierwszy `ng build` padł na `@defer` w szablonie - patrz wyżej; poprawiony i powtórzony.)

Testy (`RouterTestingHarness`, prawdziwy router, bez mockowania): binding `id`/`article`/`tab`;
brak komentarzy bez `?tab`; `?tab=comments` ładuje komponent z `@defer` (asercja na dokładną
treść `<li>`); zmiana query paramu zachowuje instancję; przekierowanie 999 i `abc`.

### ⚠️ Co jest niezweryfikowane (wprost)

- **Nie uruchamiałem `ng serve` ani przeglądarki.** Faktyczne ładowanie chunku przez sieć
  widziałem tylko jako osobny plik w buildzie; w testach (jsdom) `@defer` przechodzi, ale to
  nie dowód zachowania w przeglądarce.
- Test `@defer` czeka stałe 300 ms (`setTimeout`) - proste, ale kruche. Angular ma
  `DeferBlockFixture`/`deferBlockBehavior` w TestBed; nie użyłem ich.
- **Signal Forms, `tapResponse` i `resource()` z własnym loaderem** - nie ruszałem dziś
  (patrz "następnym razem").
- Dane to serwis w pamięci z `delay(50)`, nie HTTP - celowo, by skupić się na routerze.

---

## 🧭 Do zapamiętania

| Potrzeba | Narzędzie |
|---|---|
| Param ścieżki / query / dane z resolvera jako `input()` | `provideRouter(routes, withComponentInputBinding())` |
| Dane muszą być, zanim ekran się pokaże; 404 jako decyzja routera | `resolve` + `ResolveFn` + `RedirectCommand` |
| Rzadko używany, ciężki fragment UI | `@defer` (osobny chunk) |
| Literalny `@` w szablonie | `&#64;` |

**Następnym razem (propozycja):** Signal Forms (sprawdzić, czy w 22.2 są stabilne),
`resource()` z własnym loaderem i `AbortSignal`, `tapResponse`, testy `@defer` przez
`DeferBlockFixture`, functional guards.

---

## 📎 Jak uruchomić

Zobacz [`code/README.md`](code/README.md).

---

<div align="center">

[← wróć do wydania (wszystkie rubryki)](../README.md) · [spis wydań](../../README.md)

</div>
