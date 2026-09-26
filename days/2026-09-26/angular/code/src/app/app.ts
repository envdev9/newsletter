import { Component } from '@angular/core';
import { ProductBrowser } from './products/product-browser';

@Component({
  selector: 'app-root',
  imports: [ProductBrowser],
  template: `
    <h1>Angular 19+: linkedSignal, httpResource, signal store + HTTP</h1>
    <app-product-browser />
  `,
})
export class App {}
