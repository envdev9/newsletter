<div align="center">

# 📰 TECH PRASÓWKA
### Wydanie #1 — 24 września 2026

![Angular](https://img.shields.io/badge/Angular-DD0031?style=for-the-badge&logo=angular&logoColor=white)

## Signals od zera: fundament, `@ngrx/signals` i co nowego w Angularze od wersji 19

</div>

---

> _"Przez dekadę Angular (i React, i Vue) radziły sobie ze zmianą stanu tak: zmień coś,
> gdzieś, i licz na to, że framework sam się domyśli, co przez to trzeba przerysować.
> Signal odwraca to pytanie - zamiast zgadywać, framework WIE dokładnie, co zależy od
> czego."_

Pierwsze wydanie tej rubryki, więc zaczynamy od zera - zakładam, że nigdy nie dotykałeś
Angulara, ale codziennie pracujesz z C#/.NET. Temat na dziś: **signals** jako fundament
całego nowoczesnego Angulara, **`@ngrx/signals`** (signal store) zbudowany na tym
fundamencie, oraz garść nowości frameworka od wersji 19 wzwyż, które warto znać. Na
końcu: które operatory RxJS realnie jeszcze się przydają i kiedy sięgać po signal, a
kiedy po Observable. Wszystko sprawdzone lokalnie na `@angular/core` w wersji **22.2.0**
i `@ngrx/signals` **22.0.1** - kod w [`code/`](code/) realnie się buduje (`ng build`,
output niżej).

---

## 1️⃣ Fundament: `signal()`, `computed()`, `effect()`

### Problem, który to rozwiązuje

W .NET, gdy chcesz, żeby UI zareagował na zmianę danych, sięgasz po
`INotifyPropertyChanged`, `ObservableCollection<T>` albo w WPF/MAUI po bindingi, które
pod spodem i tak polegają na ręcznym `PropertyChanged?.Invoke(...)`. Ty, programista,
musisz pamiętać, żeby to zdarzenie odpalić - framework Ci nie pomoże, jeśli zapomnisz.

Stary Angular (do wersji ~16) miał inny problem: żeby wiedzieć, "czy coś się zmieniło",
uruchamiał tzw. **Zone.js** - patch na wszystkie asynchroniczne API przeglądarki
(`setTimeout`, `addEventListener`, Promise...), który po KAŻDYM takim zdarzeniu kazał
Angularowi przejść przez **całe drzewo komponentów** i sprawdzić, czy cokolwiek się
zmieniło (tzw. dirty checking). Działało, ale było to zgadywanie na grubą skalę - Angular
nie wiedział, KTÓRY komponent faktycznie zależy od zmienionych danych, więc sprawdzał
wszystkie.

### Co się zmieniło

**Signal** (Angular 16+, dziś fundament frameworka) to opakowana wartość, którą
odczytujesz jak funkcję - `count()`, nie `count`. To jest kluczowa różnica względem
zwykłego pola: przy odczycie Angular **rejestruje**, kto właśnie odczytał ten sygnał (inny
`computed()`, `effect()`, albo fragment template'u). Dzięki temu framework buduje sobie
dokładny graf zależności i przy zmianie sygnału wie **precyzyjnie**, co trzeba odświeżyć
- bez przechodzenia po całym drzewie komponentów i bez Zone.js.

```typescript
import { signal, computed, effect } from '@angular/core';

// signal() - najmniejsza jednostka reaktywnego stanu. NIE jest Observable -
// nie subskrybujesz go, wołasz jak funkcję.
const count = signal(0);

// computed() - wartość WYLICZANA z innych sygnałów. Leniwa i memoizowana:
// liczy się od nowa tylko wtedy, gdy naprawdę zmieni się to, od czego zależy.
const doubled = computed(() => count() * 2);

// effect() - efekt uboczny uruchamiany automatycznie, gdy zmieni się
// którykolwiek odczytany w nim sygnał. Odpowiednik .subscribe(), ale bez
// ręcznego sprzątania subskrypcji.
effect(() => console.log(`count = ${count()}, doubled = ${doubled()}`));

count.set(5);      // effect log: "count = 5, doubled = 10"
count.update(v => v + 1); // effect log: "count = 6, doubled = 12"
```

Trzy operacje na sygnale: `set()` (twarde nadpisanie), `update()` (nowa wartość na
podstawie starej - jak `Interlocked.Exchange`, tylko bez wątków) i odczyt przez
wywołanie `count()`.

### Dlaczego to ważne w praktyce

To nie jest kosmetyka - to zmiana modelu wykonania. Bez Zone.js aplikacja jest szybsza
(mniej zbędnych sprawdzeń) i **debugowalna**: skoro Angular wie dokładnie, co zależy od
czego, DevTools potrafi pokazać realny graf reaktywności zamiast "coś się zmieniło,
sprawdzam wszystko". To też fundament pod **zoneless Angular** (sekcja 5) - bez
sygnałów jako podstawy stanu, wyłączenie Zone.js w ogóle nie miałoby sensu.

**Pełny przykład:** [`code/src/app/counter/`](code/src/app/counter/).

---

## 2️⃣ `linkedSignal()` — stan wyliczony, ale nadpisywalny

### Problem, który to rozwiązuje

Klasyczny scenariusz formularza: masz listę opcji wysyłki zależną od wybranego kraju, i
chcesz, żeby domyślnie zaznaczała się najtańsza. Ale user może ręcznie wybrać inną. Co
się dzieje, gdy zmieni kraj? Lista opcji się zmienia - a wcześniej ręcznie wybrana opcja
może już nie istnieć albo być nielogiczna. Chcesz, żeby wybór **zresetował się** do nowej
wartości domyślnej.

`computed()` tu nie wystarczy - jest tylko-do-odczytu, user nie może ręcznie nadpisać
wyniku. Zwykły `signal()` też nie wystarczy - nie wie, kiedy powinien się zresetować przy
zmianie źródła. Przed `linkedSignal()` pisało się to ręcznie: `effect()`, który przy
zmianie źródła robił `set()` na osobnym sygnale - działało, ale było to dwa mechanizmy
sklejone drutem tam, gdzie wystarczy jeden.

### Co się zmieniło

Angular 19 wprowadził `linkedSignal()` - sygnał **wyliczany z innego sygnału, ale
ręcznie nadpisywalny** przez `set()`/`update()`, dokładnie jak zwykły `signal()`. Kluczowa
różnica względem `computed()`: gdy zmieni się sygnał źródłowy, `linkedSignal()`
automatycznie **resetuje się** do nowej wartości wyliczonej z funkcji łączącej -
niezależnie od tego, czy wcześniej był ręcznie nadpisany.

```typescript
const country = signal<'PL' | 'DE'>('PL');
const options = computed(() => OPTIONS_BY_COUNTRY[country()]);

// Domyślnie pierwsza (najtańsza) opcja. User może wybrać inną przez .set().
// Zmiana country() -> zmiana options() -> selectedShipping resetuje się do
// nowej wartości domyślnej, gasząc ręczny wybór z poprzedniego kraju.
const selectedShipping = linkedSignal(() => options()[0]);
```

### Dlaczego to ważne w praktyce

To dokładnie ten rodzaj stanu, który w formularzach .NET (Blazor, WPF) zwykle kończył się
ręcznym `OnParametersSet()`/event handlerem resetującym pole - kod, który łatwo
zapomnieć zaktualizować przy dodaniu nowej zależności. `linkedSignal()` robi to
deklaratywnie, w jednym miejscu, i jest częścią tego samego grafu reaktywności co reszta
sygnałów.

**Pełny przykład:** [`code/src/app/shipping/`](code/src/app/shipping/).

---

## 3️⃣ Sygnałowe `input()` / `model()` / `output()` — koniec dekoratorów?

### Problem, który to rozwiązuje

Klasyczny Angular komponent przyjmował dane z zewnątrz przez `@Input()` i wysyłał
zdarzenia przez `@Output() foo = new EventEmitter<T>()`. Działało, ale `@Input()` to było
zwykłe pole - można je było przypadkiem nadpisać w konstruktorze, zanim Angular zdążył je
ustawić, albo zapomnieć, że jest `undefined` aż do pierwszego `ngOnChanges`. Two-way
binding (`[(value)]="x"`) wymagał ręcznego sklejenia pary `@Input() value` +
`@Output() valueChange` - łatwo było się pomylić w nazwie (`valueChange` musi być
DOKŁADNIE taka, inaczej binding cicho nie zadziała).

### Co się zmieniło

Od Angular 17.1 w górę (stabilne od 19) `@Input()`/`@Output()` mają sygnałowe
odpowiedniki:

```typescript
import { Component, input, model } from '@angular/core';

@Component({ selector: 'app-quantity-stepper', /* ... */ })
export class QuantityStepper {
  // input() - odpowiednik @Input(). Odczytujesz jak każdy inny signal: max().
  readonly max = input(99);
  // input.required<T>() istnieje też - dla pól obowiązkowych, bez wartości domyślnej.

  // model() - odpowiednik PARY @Input()+@Output() do two-way bindingu.
  // Angular SAM generuje zdarzenie `quantityChange` - nie trzeba go pisać ręcznie.
  readonly quantity = model(1);
}
```

W szablonie rodzica działa to identycznie jak wcześniej: `[(quantity)]="wartość"`, albo
jawnie `[quantity]="x" (quantityChange)="x = $event"` (to drugie przydaje się, gdy
wartość nie jest zwykłym polem, tylko np. elementem tablicy w signal store - patrz
przykład z koszykiem w sekcji 4).

### Dlaczego to ważne w praktyce

`input()`/`model()`/`output()` to zwykłe sygnały - można je odczytywać wewnątrz
`computed()` i `effect()` bez żadnej specjalnej obsługi (przy starych `@Input()` trzeba
było ręcznie łapać zmiany przez `ngOnChanges`). Mniej boilerplate'u, mniej okazji do
literówki w nazwie `*Change`, i spójny mentalny model - **wszystko w komponencie jest
signal-em**, niezależnie czy to stan lokalny, dane z rodzica, czy coś wyliczonego.

**Pełny przykład:** [`code/src/app/quantity-stepper/`](code/src/app/quantity-stepper/),
użyty w [`code/src/app/cart/`](code/src/app/cart/).

---

## 4️⃣ `@ngrx/signals` — `signalStore()` na fundamencie signals

### Problem, który to rozwiązuje

Sygnały świetnie sprawdzają się w jednym komponencie. Ale gdy stan (np. koszyk zakupowy)
musi żyć **poza** komponentem, być współdzielony między kilkoma miejscami w aplikacji i
mieć uporządkowane, nazwane operacje zmieniające go - rozsypywanie osobnych `signal()`-i
po serwisie szybko robi się nieczytelne. Klasyczny `@ngrx/store` (ten "prawdziwy" NgRx,
wzorowany na Redux) to rozwiązywał, ale kosztem sporej ceremonii: akcje, reducery,
efekty, `dispatch()` - dużo kodu na coś, co koncepcyjnie jest prostym "kawałkiem stanu z
metodami".

### Co się zmieniło

`@ngrx/signals` to **osobna, dużo lżejsza biblioteka** (nie mylić z `@ngrx/store`!) -
zestaw funkcji budujących wstrzykiwalny obiekt stanu **wprost na fundamencie**
`signal()`/`computed()` z sekcji 1. Trzy klocki:

```typescript
import { computed } from '@angular/core';
import { patchState, signalStore, withComputed, withMethods, withState } from '@ngrx/signals';

interface CartLine { id: string; name: string; unitPrice: number; quantity: number; }

export const CartStore = signalStore(
  { providedIn: 'root' },
  // withState() - startowy stan. Każde pole staje się osobnym, odczytywalnym signal()-em.
  withState({ lines: [] as CartLine[] }),
  // withComputed() - "selektory". To zwykłe computed() z sekcji 1, tylko
  // zdefiniowane razem ze stanem, w jednym miejscu.
  withComputed(({ lines }) => ({
    total: computed(() => lines().reduce((sum, l) => sum + l.quantity * l.unitPrice, 0)),
  })),
  // withMethods() - akcje. patchState() to niemutujący update (jak `with` na C# recordzie).
  withMethods((store) => ({
    setQuantity(id: string, quantity: number): void {
      patchState(store, (state) => ({
        lines: state.lines.map((l) => (l.id === id ? { ...l, quantity } : l)),
      }));
    },
  })),
);
```

Użycie w komponencie to zwykłe `inject()`:

```typescript
export class Cart {
  protected readonly store = inject(CartStore);
  // store.lines(), store.total() - w template'ie czyta się je dokładnie
  // tak samo jak signal()/computed() z sekcji 1.
}
```

### Dlaczego to ważne w praktyce

Jeśli znasz klasyczny NgRx (Redux) - **zapomnij o akcjach i reducerach**. `signalStore`
nie jest "NgRx, tylko z sygnałami" - to zupełnie inny, dużo prostszy model bez
architektury Redux. Dla większości aplikacji (współdzielony koszyk, stan filtra, cache
danych z API) to dziś rekomendowany, znacznie lżejszy sposób na globalny stan niż pełny
`@ngrx/store` - ten drugi ma dziś sens głównie tam, gdzie realnie potrzebujesz jego
mocnych stron: pełnej historii akcji (time-travel debugging), middleware'ów czy bardzo
dużych, złożonych domen z wieloma zespołami.

**Pełny przykład:** [`code/src/app/cart/`](code/src/app/cart/) (`cart.store.ts` +
`cart.ts`).

---

## 5️⃣ Inne nowości od Angular 19 wzwyż, warto wiedzieć że istnieją

Nie wszystko da się (albo warto) demonstrować pełnym przykładem w pierwszym wydaniu -
poniższe warto znać z nazwy, żeby rozpoznać je w kodzie/dokumentacji:

- **Zoneless change detection** (`provideZonelessChangeDetection()`) - możliwość
  całkowitego wyłączenia Zone.js opisanego w sekcji 1, tak żeby wykrywanie zmian opierało
  się WYŁĄCZNIE na sygnałach. Mniejszy bundle (Zone.js patchuje pół API przeglądarki),
  szybszy start aplikacji. Wymaga, żeby cały stan w aplikacji faktycznie płynął przez
  sygnały - stąd sekcje 1-4 tego wydania to properly fundament pod to, nie ciekawostka.
- **`resource()` / `rxResource()` / `httpResource()`** - sygnałowy sposób na pobieranie
  danych asynchronicznych (odpowiednik "signal, który sam wie, że jest `loading`, ma
  `value()` i `error()`"), pomyślany jako signal-owa alternatywa dla ręcznego
  `HttpClient` + `toSignal()` z sekcji 6.
- **Nowa składnia sterowania przepływem w szablonach** (`@if`, `@for`, `@switch` zamiast
  `*ngIf`/`*ngFor`/`*ngSwitch`) - używana już w każdym przykładzie kodu w tym wydaniu
  (patrz `@for` w `counter.html`, `cart.html`). Czytelniejsza, szybsza w kompilacji,
  wbudowana w silnik szablonów zamiast być dyrektywą strukturalną.

Celowo bez kodu na te trzy - część wciąż ewoluuje między wersjami (zwłaszcza
`resource()`), a fundament z sekcji 1-4 daje więcej realnej wartości na start niż
rozjeżdżanie się w API, które może się jeszcze zmienić.

---

## 6️⃣ RxJS dziś: które operatory realnie się przydają, i kiedy signal a kiedy Observable

RxJS nie zniknął - po prostu przestał być jedynym słusznym narzędziem do WSZYSTKIEGO.
Reguła, która sprawdza się w praktyce:

- **signal()** - stan: coś, co MA aktualną wartość w danej chwili (liczba w koszyku,
  wybrany filtr, dane z formularza). Nie ma pojęcia o czasie ani o anulowaniu.
- **Observable (RxJS)** - strumień zdarzeń w czasie, zwłaszcza gdy trzeba: debounce'ować,
  anulować poprzednie żądanie przy nowym, łączyć kilka niezależnych źródeł, albo
  reagować na zdarzenia z DOM-u (scroll, resize, klawiatura) zanim staną się "wartością".

Operatory, które realnie widuje się w produkcyjnym kodzie Angular dziś (nie cały katalog
RxJS):

| Operator | Kiedy używać |
|---|---|
| `debounceTime` | Pole wyszukiwania - nie strzelaj przy każdym naciśnięciu klawisza |
| `distinctUntilChanged` | Nie powtarzaj żądania dla tej samej wartości co ostatnio |
| `switchMap` | Nowe żądanie ANULUJE poprzednie w locie (search-as-you-type, przełączanie zakładek) |
| `catchError` | Błąd jednego żądania nie może ubić całego strumienia (bez tego jeden 500 z API zatrzymuje strumień na zawsze) |
| `combineLatestWith` / `combineLatest` | Łączenie kilku niezależnie zmieniających się źródeł w jedną wartość |
| `takeUntilDestroyed()` | Automatyczne odsubskrybowanie ręcznej subskrypcji przy zniszczeniu komponentu - bez tego wyciek pamięci |

Most między dwoma światami: **`toSignal()`** (Observable → signal, do odczytu w
template'ie bez ręcznej subskrypcji) i **`toObservable()`** (signal → Observable, gdy
trzeba użyć operatora RxJS na wartości, która zaczęła życie jako signal).

```typescript
const results = toSignal(
  query$.pipe(
    debounceTime(300),
    distinctUntilChanged(),
    switchMap((q) => api.search(q)), // anuluje poprzednie zapytanie
  ),
  { initialValue: [] },
);
// W template'ie: zwykły odczyt sygnału, results() - zero wiedzy o RxJS w środku.
```

**Pełny przykład:** [`code/src/app/search/`](code/src/app/search/).

---

## 📎 Jak uruchomić kod z tego wydania

Zobacz [`code/README.md`](code/README.md) - dokładne komendy i prawdziwy output
`ng build`.

---

<div align="center">

[← wróć do wydania #1 (wszystkie rubryki)](../README.md) · [spis wydań](../../README.md)

</div>
