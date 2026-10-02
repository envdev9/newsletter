import { Component, computed, signal } from '@angular/core';
import { FormField, FormRoot, applyEach, form, required } from '@angular/forms/signals';
import { emptyLineItem, lineItemSchema, type LineItem } from './line-item-schema';
import { placeOrder } from './order-backend';
import { formatPrice, PriceInput } from './price-input';
import { QuantityStepper } from './quantity-stepper';

interface OrderModel {
  customerName: string;
  items: LineItem[];
}

/**
 * Formularz zamówienia: nazwa klienta + tablica pozycji (produkt, ilość, cena). Nowości
 * względem wydania #7 (30.09 - `applyEach` + pierwsza wersja `FormValueControl`):
 *
 *  1. Nowe pole `unitPrice` edytowane przez `<app-price-input>` - własny kontrolek używający
 *     `transformedValue()` do parsowania tekstu z przecinkiem dziesiętnym ("12,50") na `number`.
 *     Błędny tekst NIE psuje formularza - `parse()` zgłasza błąd zamiast rzucać wyjątkiem.
 *  2. `<app-quantity-stepper>` i `<app-price-input>` renderują TERAZ własne błędy WEWNĄTRZ
 *     siebie (`errors` z kontraktu `FormUiControl`) - host nie musi już ręcznie iterować
 *     `item.quantity().errors()` w szablonie, tak jak robił to w wydaniu #7.
 *  3. Przyciski "Fokus" i "Resetuj wiersz" wołają `focusBoundControl()`/`reset()` wprost na
 *     `FieldState` - dowód na żywo, że to WŁASNE komponenty (`focus()`/`reset()`) odpowiadają na
 *     te wywołania, nie coś wbudowanego tylko dla `<input>`.
 */
@Component({
  selector: 'app-order-form',
  imports: [FormField, FormRoot, PriceInput, QuantityStepper],
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
            <th>Cena jedn.</th>
            <th>Wartość</th>
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
              </td>
              <td>
                <app-price-input [formField]="item.unitPrice" />
              </td>
              <td class="line-total">{{ lineTotal(i) }}</td>
              <td class="row-actions">
                <button type="button" class="focus-price" (click)="focusPrice(i)">Fokus na cenę</button>
                <button type="button" class="reset-row" (click)="resetRow(i)">Resetuj wiersz</button>
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

      <p class="order-total">Razem: {{ orderTotalFormatted() }} zł</p>

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

  protected readonly orderTotal = computed(() =>
    this.model().items.reduce((sum, it) => sum + it.quantity * it.unitPrice, 0),
  );
  protected readonly orderTotalFormatted = computed(() => formatPrice(this.orderTotal()));

  protected readonly orderForm = form(
    this.model,
    (f) => {
      required(f.customerName, { message: 'Nazwa klienta jest wymagana' });
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

  protected lineTotal(index: number): string {
    const item = this.model().items[index];
    return formatPrice(item.quantity * item.unitPrice);
  }

  protected addItem(): void {
    this.model.update((m) => ({ ...m, items: [...m.items, emptyLineItem()] }));
  }

  protected removeItem(index: number): void {
    this.model.update((m) => ({ ...m, items: m.items.filter((_, i) => i !== index) }));
  }

  protected focusPrice(index: number): void {
    this.orderForm.items[index].unitPrice().focusBoundControl();
  }

  protected resetRow(index: number): void {
    this.orderForm.items[index]().reset();
  }
}
