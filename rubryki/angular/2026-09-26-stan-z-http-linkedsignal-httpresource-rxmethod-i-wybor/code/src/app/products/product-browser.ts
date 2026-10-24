import { httpResource } from '@angular/common/http';
import { Component, inject, linkedSignal } from '@angular/core';
import { ProductDetails } from './product.model';
import { ProductsStore } from './products.store';

@Component({
  selector: 'app-product-browser',
  templateUrl: './product-browser.html',
})
export class ProductBrowser {
  protected readonly store = inject(ProductsStore);

  /**
   * linkedSignal w formie rozszerzonej (source + computation z dostępem do poprzedniej wartości):
   * gdy lista produktów się zmieni, ZACHOWAJ zaznaczenie jeśli produkt nadal jest na liście,
   * w przeciwnym razie wybierz pierwszy. Użytkownik może nadpisać wybór przez select(id).
   */
  protected readonly selectedId = linkedSignal<{ id: number }[], number | undefined>({
    source: this.store.products,
    computation: (products, previous) =>
      products.find((p) => p.id === previous?.value)?.id ?? products[0]?.id,
  });

  /**
   * httpResource: reaktywne żądanie GET. Funkcja-URL czyta signal selectedId - przy każdej
   * zmianie resource sam anuluje poprzednie żądanie i wysyła nowe. Zwrócenie undefined
   * oznacza "nie ładuj" (status 'idle').
   */
  protected readonly details = httpResource<ProductDetails>(() => {
    const id = this.selectedId();
    return id === undefined ? undefined : `/api/products/${id}`;
  });

  protected onSearch(value: string): void {
    this.store.search(value);
  }

  protected select(id: number): void {
    this.selectedId.set(id);
  }

  protected order(): void {
    const id = this.selectedId();
    if (id !== undefined) {
      this.store.placeOrder(id);
    }
  }
}
