import { Component, input, model } from '@angular/core';

@Component({
  selector: 'app-quantity-stepper',
  templateUrl: './quantity-stepper.html',
})
export class QuantityStepper {
  // input() (Angular 17.1+, domyślny styl od 19) - sygnałowy odpowiednik
  // dekoratora @Input(). Odczytywany jak każdy inny signal: max(). Tu bez
  // required() - ma wartość domyślną 99.
  readonly max = input(99);

  // model() (Angular 17.2+) - sygnałowy odpowiednik PARY @Input() + @Output()
  // używanej razem do two-way bindingu ([(quantity)]="..." w rodzicu). Rodzic
  // dostaje jednocześnie odczyt i możliwość zapisu, a Angular sam generuje
  // zdarzenie `quantityChange` przy każdej zmianie - bez ręcznego tworzenia
  // EventEmittera, jak trzeba było robić przed model().
  readonly quantity = model(1);

  protected inc(): void {
    this.quantity.update((q) => Math.min(this.max(), q + 1));
  }

  protected dec(): void {
    this.quantity.update((q) => Math.max(1, q - 1));
  }
}
