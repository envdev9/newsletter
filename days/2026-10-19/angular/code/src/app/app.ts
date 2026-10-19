import { Component } from '@angular/core';
import { CheckoutForm } from './checkout/checkout-form';

@Component({
  selector: 'app-root',
  imports: [CheckoutForm],
  template: `
    <h1>Angular: Signal Forms w SSR i hydracji</h1>
    <app-checkout-form />
  `,
})
export class App {}
