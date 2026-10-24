import { Component, effect, computed, signal } from '@angular/core';

// UWAGA: ten plik to zbior antywzorcow do testu skanera - NIE kopiuj go do
// prawdziwego projektu. Wersja poprawiona: ../samples/good.component.ts

@Component({
  selector: 'app-cart-bad',
  standalone: true,
  template: `
    <p>{{ fullName() }}</p>
    <p>Suma: {{ total() }}</p>
    <ul>
      <li *ngFor="let item of items()">{{ item.name }}</li>
    </ul>
  `,
  // (celowo brak strategii detekcji zmian - patrz ONPUSH-MISSING w artykule)
})
export class CartBadComponent {
  firstName = signal('Jan');
  lastName = signal('Kowalski');
  fullName = signal('Jan Kowalski');

  count = signal(0);

  items = signal<{ name: string; price: number }[]>([
    { name: 'Kawa', price: 12 },
    { name: 'Herbata', price: 8 },
  ]);
  total = signal(0);

  constructor() {
    // ANTYWZOREC 1: effect() zamiast computed() do synchronizacji stanu.
    // fullName jest w calosci wyliczana z firstName/lastName - to podrecznikowy
    // przypadek dla computed(), nie effect() (EFFECT-STATE-SYNC).
    effect(() => {
      this.fullName.set(`${this.firstName()} ${this.lastName()}`);
    });

    // ANTYWZOREC 2: effect() czyta i zapisuje ten sam sygnal - kazde
    // wywolanie planuje kolejne (EFFECT-SELF-WRITE). W tym przykladzie akurat
    // nie petli w nieskonczonosc (count rosnie tylko raz na inny trigger),
    // ale to przypadkowe, nie zamierzone.
    effect(() => {
      if (this.count() < 1) {
        this.count.set(this.count() + 1);
      }
    });

    // ANTYWZOREC 3 (INFO, nie WARN): effect() czyta dwa sygnaly bez untracked().
    // Jesli logowanie ceny nie powinno wywolywac ponownego effectu przy kazdej
    // zmianie samego `items` (a tylko przy zmianie `count`), warto rozwazyc
    // untracked() (UNTRACKED-CANDIDATE).
    effect(() => {
      console.log(`count=${this.count()}, items=${this.items().length}`);
    });
  }

  // ANTYWZOREC 4: computed() z efektem ubocznym - mutuje inny sygnal (total)
  // w trakcie liczenia. computed() ma byc CZYSTA (COMPUTED-SIDE-EFFECT).
  cartSummary = computed(() => {
    const sum = this.items().reduce((acc, i) => acc + i.price, 0);
    this.total.set(sum);
    return sum;
  });

  addItem(name: string, price: number): void {
    // ANTYWZOREC 5: update() mutuje tablice w miejscu (push) i zwraca TĘ SAMĄ
    // referencje - domyslna rownosc sygnalu jest referencyjna (===), wiec to
    // dziala "przez przypadek" tylko dlatego, ze zwracamy nowa tablice z push
    // ponizej. Gdyby ktos zwrocil `list` bez zmiany referencji, subskrybenci
    // porownujący przez === nie zauwazyliby zmiany (MUTATING-UPDATE).
    this.items.update((list) => {
      list.push({ name, price });
      return list;
    });
  }
}
