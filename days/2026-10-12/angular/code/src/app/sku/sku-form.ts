import { Component, signal } from '@angular/core';
import { FormField, form, submit } from '@angular/forms/signals';
import { SkuInput } from './sku-input';
import { SkuMode, SkuModel, emptySku, skuSchema } from './sku.schema';

@Component({
  selector: 'app-sku-form',
  imports: [FormField, SkuInput],
  template: `
    <form (submit)="onSubmit($event)">
      <label for="mode">Tryb pola SKU</label>
      <select id="mode" [formField]="skuForm.mode">
        <option value="edit">edit</option>
        <option value="locked">locked (disabled)</option>
        <option value="readonly">readonly</option>
        <option value="hidden">hidden</option>
      </select>

      @if (!skuForm.sku().hidden()) {
        <div>
          <label>SKU</label>
          <app-sku-input [formField]="skuForm.sku" />
        </div>
      }

      <p class="hint">Model: <code id="model-sku">{{ model().sku }}</code></p>
      @for (e of skuForm.sku().errors(); track e.kind) {
        <p class="error">{{ e.message }}</p>
      }
      @if (saved() !== null) {
        <p class="ok">Zapisano: {{ saved() }}</p>
      }
      <button type="submit">Zapisz</button>
    </form>
  `,
})
export class SkuForm {
  readonly model = signal<SkuModel>(emptySku());
  readonly skuForm = form(this.model, skuSchema);
  readonly saved = signal<string | null>(null);
  /** Liczy realne wywołania akcji submit (do testów). */
  readonly submitCalls: string[] = [];

  setMode(mode: SkuMode): void {
    this.model.update((m) => ({ ...m, mode }));
  }

  protected async onSubmit(event: Event): Promise<void> {
    event.preventDefault();
    await submit(this.skuForm, async () => {
      this.submitCalls.push(this.model().sku);
      this.saved.set(this.model().sku);
    });
  }
}
