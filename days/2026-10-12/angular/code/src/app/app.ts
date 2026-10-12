import { Component } from '@angular/core';
import { SkuForm } from './sku/sku-form';

@Component({
  selector: 'app-root',
  imports: [SkuForm],
  template: `
    <h1>Angular: <code>debounce('blur')</code> na własnej kontrolce <code>FormValueControl</code></h1>
    <app-sku-form />
  `,
})
export class App {}
