import { Component } from '@angular/core';
import { OrderForm } from './order-form';

@Component({
  selector: 'app-root',
  imports: [OrderForm],
  template: `
    <h1>Angular: Signal Forms - <code>transformedValue()</code> + pełny <code>FormUiControl</code></h1>
    <app-order-form />
  `,
})
export class App {}
