# Kod do wydania #1 — Signals, `linkedSignal()`, sygnałowe `input()`/`model()`, `@ngrx/signals`, RxJS

Pełny artykuł: [`../ARTICLE.md`](../ARTICLE.md). Poniżej ten sam kod + jak go odpalić.

Wymagania: **Node.js 20+** i **npm**. Projekt wygenerowany Angular CLI **22.2.0**,
z `@ngrx/signals` **22.0.1**.

## Fragment prasówki, którego dotyczy ten kod

> **Signal** to opakowana wartość, którą odczytujesz jak funkcję - `count()`, nie
> `count`. Przy odczycie Angular **rejestruje**, kto właśnie odczytał ten sygnał, więc
> przy zmianie wie precyzyjnie, co trzeba odświeżyć - bez przechodzenia po całym drzewie
> komponentów i bez Zone.js.
>
> `linkedSignal()` (Angular 19) to sygnał wyliczany z innego sygnału, ale ręcznie
> nadpisywalny - i automatycznie resetujący się do nowej wartości domyślnej, gdy zmieni
> się źródło.
>
> `input()` / `model()` (stabilne od Angular 19) to sygnałowe odpowiedniki
> `@Input()`/`@Output()` - `model()` sam generuje zdarzenie `xChange` potrzebne do
> two-way bindingu `[(x)]`.
>
> `@ngrx/signals` (osobna biblioteka od `@ngrx/store`!) buduje `signalStore()` wprost na
> fundamencie `signal()`/`computed()`: `withState()` (stan), `withComputed()`
> (selektory-computed), `withMethods()` (akcje przez `patchState()`) - bez akcji,
> reducerów i `dispatch()` znanych z klasycznego Redux/NgRx.
>
> RxJS wciąż ma sens tam, gdzie signal nie wystarcza: strumienie zdarzeń w czasie,
> zwłaszcza z `debounceTime` + `distinctUntilChanged` + `switchMap` (anulowanie
> poprzedniego żądania) + `catchError`. Most między światami: `toSignal()` /
> `toObservable()`.

## Struktura projektu

```
src/app/
  counter/            -> 1. signal() + computed() + effect()
  shipping/            -> 2. linkedSignal()
  quantity-stepper/    -> 3. input() + model() (sygnałowe two-way binding)
  cart/                -> 4. @ngrx/signals - signalStore() (cart.store.ts + cart.ts)
  search/              -> 5. RxJS (debounceTime/distinctUntilChanged/switchMap) + toSignal()
  app.ts / app.html    -> spina wszystkie cztery przykłady na jednej stronie
```

## Jak uruchomić od zera

```bash
cd code
npm install          # albo: npm ci (lockfile jest w repo)
npx ng build         # produkcyjny build do dist/code/
npx ng serve         # dev server na http://localhost:4200/ (opcjonalnie)
```

## Realna weryfikacja wykonana w tej sesji

Maszyna deweloperska ma dysk `/` praktycznie pełny (**~230 MB wolnego miejsca** z 40 GB —
`df -h /` pokazywało `100% /`, `Avail 231M-232M`). Standardowy `npm install` dla
Angulara (`node_modules` samego tego projektu to ~290 MB, plus paczki Node/npm) **nie
mieściłby się** na dysku systemowym. Zgodnie z zasadą "nie sprzątaj cudzych rzeczy na
współdzielonej maszynie", do weryfikacji użyty został **`/dev/shm` (tmpfs, RAM-backed,
15 GB, osobny od dysku `/`)** — czysto lokalny workaround na czas weryfikacji, nic na
dysku `/` nie zostało ruszone ani wyczyszczone. Node.js 22.22.3 + npm 10.9.8 i cały
`node_modules` tego projektu żyły tylko w `/dev/shm/angular-build/`, zniknęły po
zakończeniu sesji (tmpfs nie przeżywa restartu maszyny) — **kod w repo (`code/`) nie
wymaga tego workaroundu**, na maszynie z normalną ilością wolnego miejsca na dysku
wystarczą zwykłe komendy z sekcji wyżej.

Wykonane komendy (kopia `code/` z repo, identyczny `package.json`/`package-lock.json` -
zweryfikowane `diff`, zero różnic):

```bash
$ npm ci
added 223 packages, and audited 224 packages in 12s
73 packages are looking for funding (run `npm fund` for details)
found 0 vulnerabilities

$ npx ng build
❯ Building...
✔ Building...
Initial chunk files | Names         |  Raw size | Estimated transfer size
main-R3ZVB2S3.js    | main          | 135.40 kB |                40.44 kB
styles-RACD6W7T.css | styles        | 453 bytes |               453 bytes

                    | Initial total | 135.85 kB |                40.89 kB

Application bundle generation complete. [7.752 seconds]
Output location: /dev/shm/angular-build/code/dist/code
```

Build zakończony kodem wyjścia `0`, `dist/code/browser/` zawierał realne
`main-R3ZVB2S3.js`, `styles-RACD6W7T.css`, `index.html`, `favicon.ico`. `df -h /` po
całej operacji: bez zmian (`231M` wolnego) — potwierdza, że nic nie trafiło na dysk
systemowy.

Zainstalowane wersje (potwierdzone z `node_modules/*/package.json` po `npm ci`, zgodne
z tym, co deklaruje artykuł):

- `@angular/core` → `22.2.0`
- `@ngrx/signals` → `22.0.1`

**Nie uruchamiano** `ng test` (Vitest) w tej sesji — poza zakresem wymaganej
weryfikacji (`npm install` + `ng build`); wymagałoby to dodatkowego pobierania
zależności testowych bez wyraźnej potrzeby.
