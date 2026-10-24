import { Component } from '@angular/core';
import { ProductSearch } from './products/product-search';

@Component({
  selector: 'app-root',
  imports: [ProductSearch],
  template: `
    <h1>Angular: <code>tapResponse()</code> z <code>@ngrx/operators</code> - gdzie naprawdę pomaga</h1>
    <app-product-search />
  `,
})
export class App {}
