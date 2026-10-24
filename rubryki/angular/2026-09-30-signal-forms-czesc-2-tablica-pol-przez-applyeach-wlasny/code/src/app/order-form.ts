import { Component, signal } from '@angular/core';
import { FormField, FormRoot, applyEach, form, required } from '@angular/forms/signals';
import { lineItemSchema, type LineItem } from './line-item-schema';
import { placeOrder } from './order-backend';
import { QuantityStepper } from './quantity-stepper';

interface OrderModel {
  customerName: string;
  items: LineItem[];
}

function emptyLineItem(): LineItem {
  return { productName: '', quantity: 1 };
}

/**
 * Formularz zamówienia: nazwa klienta + DYNAMICZNA tablica pozycji (produkt + ilość).
 *
 * Dwie rzeczy, których nie było w wydaniu #5 (28.09):
 *  1. `applyEach(f.items, lineItemSchema)` - jedna, reużywalna `schema<LineItem>()` zastosowana
 *     do KAŻDEGO elementu tablicy, niezależnie od tego ile ich w danej chwili jest (dodawanie/
 *     usuwanie pozycji to zwykłe `signal.update()` na modelu, żadnej rejestracji/wyrejestrowania
 *     walidatorów).
 *  2. Ilość edytowana przez WŁASNY komponent `<app-quantity-stepper>` (nie `<input>`) - a mimo to
 *     `[formField]` wiąże go identycznie jak natywne pole, bo implementuje `FormValueControl`.
 */
@Component({
  selector: 'app-order-form',
  imports: [FormField, FormRoot, QuantityStepper],
  template: `
    <form [formRoot]="orderForm">
      <div class="field">
        <label for="customerName">Klient</label>
        <input id="customerName" type="text" [formField]="orderForm.customerName" />
        @for (e of orderForm.customerName().errors(); track e.kind) {
          <p class="error">{{ e.message }}</p>
        }
      </div>

      <table class="items">
        <thead>
          <tr>
            <th>Produkt</th>
            <th>Ilość</th>
            <th></th>
          </tr>
        </thead>
        <tbody>
          @for (item of orderForm.items; track $index; let i = $index) {
            <tr class="item-row">
              <td>
                <input type="text" [formField]="item.productName" placeholder="Nazwa produktu" />
                @for (e of item.productName().errors(); track e.kind) {
                  <p class="error">{{ e.message }}</p>
                }
              </td>
              <td>
                <app-quantity-stepper [formField]="item.quantity" />
                @for (e of item.quantity().errors(); track e.kind) {
                  <p class="error">{{ e.message }}</p>
                }
              </td>
              <td>
                <button
                  type="button"
                  class="remove-item"
                  (click)="removeItem(i)"
                  [disabled]="model().items.length <= 1"
                >
                  Usuń
                </button>
              </td>
            </tr>
          }
        </tbody>
      </table>

      <button type="button" class="add-item" (click)="addItem()">+ dodaj pozycję</button>

      <button type="submit" [disabled]="orderForm().submitting() || !orderForm().valid()">
        @if (orderForm().submitting()) {
          Wysyłanie…
        } @else {
          Złóż zamówienie
        }
      </button>

      @switch (lastResult()) {
        @case ('success') {
          <p class="result ok">Zamówienie przyjęte ({{ submitCallCount() }}× wywołano backend).</p>
        }
      }
    </form>
  `,
})
export class OrderForm {
  protected readonly model = signal<OrderModel>({
    customerName: '',
    items: [emptyLineItem()],
  });

  protected readonly lastResult = signal<'idle' | 'success'>('idle');

  // Licznik faktycznych wywołań fake-backendu - używany w teście na blokadę współbieżnego submit().
  protected readonly submitCallCount = signal(0);

  protected readonly orderForm = form(
    this.model,
    (f) => {
      required(f.customerName, { message: 'Nazwa klienta jest wymagana' });
      // Jedna reużywalna schema zastosowana do wszystkich elementów f.items - bez pętli,
      // bez ręcznej rejestracji per-index.
      applyEach(f.items, lineItemSchema);
    },
    {
      submission: {
        action: async (f) => {
          this.submitCallCount.update((n) => n + 1);
          await placeOrder(f().value());
          this.lastResult.set('success');
          return undefined;
        },
      },
    },
  );

  protected addItem(): void {
    this.model.update((m) => ({ ...m, items: [...m.items, emptyLineItem()] }));
  }

  protected removeItem(index: number): void {
    this.model.update((m) => ({ ...m, items: m.items.filter((_, i) => i !== index) }));
  }
}
