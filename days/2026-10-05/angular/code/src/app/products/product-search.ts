import { Component, inject } from '@angular/core';
import { SearchStore } from './search.store';

@Component({
  selector: 'app-product-search',
  templateUrl: './product-search.html',
})
export class ProductSearch {
  protected readonly store = inject(SearchStore);

  protected onInput(value: string): void {
    this.store.search(value);
  }
}
