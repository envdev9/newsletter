import { Component, computed, effect, signal } from '@angular/core';

@Component({
  selector: 'app-counter',
  templateUrl: './counter.html',
})
export class Counter {
  // signal() - najmniejsza jednostka reaktywnego stanu w Angularze. To NIE jest
  // Observable: nie subskrybujesz go, tylko WYWOŁUJESZ jak funkcję, żeby odczytać
  // aktualną wartość (`this.count()`). Angular sam wie, kto go odczytał (np. który
  // fragment template'u albo który computed()) i sam odświeży tylko te miejsca.
  protected readonly count = signal(0);

  // computed() - wartość WYLICZANA z innych sygnałów. Liczy się leniwie (dopiero
  // przy odczycie) i jest memoizowana - dopóki `count` się nie zmieni, kolejne
  // odczyty `doubled()` nie przeliczają niczego od nowa. Odpowiednik: właściwość
  // tylko do odczytu, która sama wie, kiedy jest "nieaktualna".
  protected readonly doubled = computed(() => this.count() * 2);
  protected readonly parity = computed(() =>
    this.count() % 2 === 0 ? 'parzysta' : 'nieparzysta',
  );

  protected readonly log = signal<string[]>([]);

  constructor() {
    // effect() - efekt uboczny, który Angular uruchamia automatycznie za każdym
    // razem, gdy zmieni się KTÓRYKOLWIEK sygnał odczytany w jego ciele (tu: `count`
    // przez `parity()`). To odpowiednik `.subscribe(...)` z RxJS, ale bez ręcznego
    // zarządzania subskrypcją - Angular sam sprząta effect, gdy komponent, w którym
    // powstał, zostanie zniszczony. Używaj effect() do rzeczy PO PRAWEJ STRONIE
    // stanu (logowanie, synchronizacja z localStorage, wywołanie API) - nigdy do
    // liczenia wartości, od tego jest computed().
    effect(() => {
      const entry = `count = ${this.count()} (${this.parity()})`;
      // update() - nowa wartość liczona na podstawie poprzedniej, bez ręcznego
      // odczytu przed zapisem (odpowiednik `Interlocked`-owego "atomowego" update).
      this.log.update((entries) => [...entries.slice(-4), entry]);
    });
  }

  protected increment(): void {
    this.count.update((value) => value + 1);
  }

  protected decrement(): void {
    this.count.update((value) => value - 1);
  }

  protected reset(): void {
    // set() - twarde nadpisanie wartości, gdy nie zależy od poprzedniej.
    this.count.set(0);
  }
}
