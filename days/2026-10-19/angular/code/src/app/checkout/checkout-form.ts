import { ChangeDetectionStrategy, Component, afterNextRender, inject, signal } from '@angular/core';
import { FormField, form } from '@angular/forms/signals';
import { DRAFT, Draft, checkoutSchema } from './checkout.schema';

@Component({
  selector: 'app-checkout-form',
  changeDetection: ChangeDetectionStrategy.OnPush,
  imports: [FormField],
  template: `
    <form>
      <label>Imię <input id="name" [formField]="f.name" /></label>
      <label>Kod <input id="code" [formField]="f.code" /></label>
      @if (f.code().pending()) {
        <p id="pending">Sprawdzam kod…</p>
      }
      @for (e of f.code().errors(); track e.kind) {
        <p class="error">{{ e.message }}</p>
      }
      <p id="mode">{{ hydrated() ? 'JS aktywny' : 'tylko HTML' }}</p>
    </form>
  `,
})
export class CheckoutForm {
  readonly model = signal<Draft>({ ...inject(DRAFT) });
  readonly f = form(this.model, checkoutSchema);
  /** `afterNextRender` nie odpala się na serwerze - HTML z SSR zawsze mówi "tylko HTML". */
  readonly hydrated = signal(false);

  constructor() {
    afterNextRender(() => this.hydrated.set(true));
  }
}
