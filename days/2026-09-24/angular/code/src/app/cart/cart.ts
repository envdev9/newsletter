import { Component, inject } from '@angular/core';
import { QuantityStepper } from '../quantity-stepper/quantity-stepper';
import { CartStore } from './cart.store';

@Component({
  selector: 'app-cart',
  imports: [QuantityStepper],
  templateUrl: './cart.html',
})
export class Cart {
  // inject() - wstrzyknięcie signalStore tak samo, jak każdego innego serwisu.
  // `store.lines()`, `store.itemCount()`, `store.total()` to zwykłe sygnały -
  // w template'ie odczytujesz je dokładnie tak jak signal()/computed() z komponentu.
  protected readonly store = inject(CartStore);
}
