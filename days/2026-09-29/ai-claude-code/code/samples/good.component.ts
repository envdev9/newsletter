import { ChangeDetectionStrategy, Component, computed, effect, signal, untracked } from '@angular/core';

// Poprawiona wersja bad.component.ts - te same funkcje, bez antywzorcow.

@Component({
  selector: 'app-cart-good',
  standalone: true,
  changeDetection: ChangeDetectionStrategy.OnPush,
  template: `
    <p>{{ fullName() }}</p>
    <p>Suma: {{ total() }}</p>
    <ul>
      <li *ngFor="let item of items()">{{ item.name }}</li>
    </ul>
  `,
})
export class CartGoodComponent {
  firstName = signal('Jan');
  lastName = signal('Kowalski');

  // POPRAWKA 1: fullName jest w calosci wyliczana z firstName/lastName ->
  // computed(), nie effect() + rączny set(). Cache'owane, bez efektu ubocznego.
  fullName = computed(() => `${this.firstName()} ${this.lastName()}`);

  count = signal(0);

  items = signal<{ name: string; price: number }[]>([
    { name: 'Kawa', price: 12 },
    { name: 'Herbata', price: 8 },
  ]);

  // POPRAWKA 4: total liczony przez computed(), zero efektow ubocznych -
  // computed() tylko czyta i zwraca wartosc, nic nie ustawia.
  total = computed(() => this.items().reduce((acc, i) => acc + i.price, 0));

  constructor() {
    // POPRAWKA 2 + 3: effect() sluzy tu wylacznie do prawdziwego efektu
    // ubocznego (logowanie), nie do liczenia stanu. count() ma wywolywac
    // ponowne uruchomienie effectu, items() nie musi - stad untracked()
    // wokol odczytu items(), zamiast dwoch rownoleglych zaleznosci.
    effect(() => {
      const c = this.count();
      untracked(() => {
        console.log(`count=${c}, items=${this.items().length}`);
      });
    });
  }

  increment(): void {
    this.count.update((c) => c + 1);
  }

  addItem(name: string, price: number): void {
    // POPRAWKA 5: nowa tablica przez spread - stara referencja `list` nigdy
    // nie jest mutowana, wiec kazdy kod trzymajacy poprzednia wartosc sygnalu
    // widzi niezmieniona, spójną tablice.
    this.items.update((list) => [...list, { name, price }]);
  }
}
