import { Component } from '@angular/core';
import { OrderForm } from './order-form';

@Component({
  selector: 'app-root',
  imports: [OrderForm],
  template: `
    <h1>Angular: Signal Forms - <code>applyEach()</code> + własny <code>FormValueControl</code></h1>
    <app-order-form />
  `,
})
export class App {}
