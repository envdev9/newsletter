import { Component, input, model } from '@angular/core';
import type { FormValueControl } from '@angular/forms/signals';

/**
 * Własny "kontrolek" formularza - ZAMIAST natywnego `<input type="number">`. Jedyny warunek,
 * żeby dyrektywa `[formField]` mogła go bindować dokładnie tak samo jak `<input>`, to
 * zaimplementowanie kontraktu `FormValueControl<TValue>` z `@angular/forms/signals`:
 *
 *  - `value: ModelSignal<TValue>` (JEDYNE pole wymagane) - dwukierunkowy `model()`, ten sam
 *    mechanizm co w `[(ngModel)]`/`@Input()`+`@Output()`, tylko jako jeden sygnał.
 *  - reszta (`disabled`, `min`, `max`, `errors`, `touched`, ...) to OPCJONALNE `input()`,
 *    które `[formField]` wypełnia samo, jeśli je zadeklarujemy - i to bez żadnego kodu
 *    spinającego, w odróżnieniu od `ControlValueAccessor` z Reactive Forms, gdzie trzeba
 *    ręcznie zaimplementować `writeValue`/`registerOnChange`/`registerOnTouched`.
 *
 * `min`/`max` poniżej NIE są ustawiane ręcznie w szablonie hosta (`order-form.ts`) -
 * `[formField]` czyta je z walidatorów `min()`/`max()` zadeklarowanych w `lineItemSchema`
 * i wstrzykuje tutaj automatycznie. Stąd przyciski +/- poprawnie się blokują na granicach
 * 1..99 bez ani jednej linijki kodu łączącego to jawnie.
 */
@Component({
  selector: 'app-quantity-stepper',
  template: `
    <div class="stepper" [class.is-disabled]="disabled()">
      <button type="button" class="step-btn" (click)="decrement()" [disabled]="disabled() || !canDecrement()">
        −
      </button>
      <span class="qty-value">{{ value() }}</span>
      <button type="button" class="step-btn" (click)="increment()" [disabled]="disabled() || !canIncrement()">
        +
      </button>
    </div>
  `,
})
export class QuantityStepper implements FormValueControl<number> {
  readonly value = model.required<number>();
  readonly disabled = input<boolean>(false);
  readonly min = input<number | undefined>(undefined);
  readonly max = input<number | undefined>(undefined);

  protected canDecrement(): boolean {
    return this.min() === undefined || this.value() > this.min()!;
  }

  protected canIncrement(): boolean {
    return this.max() === undefined || this.value() < this.max()!;
  }

  protected increment(): void {
    if (this.canIncrement()) {
      this.value.update((v) => v + 1);
    }
  }

  protected decrement(): void {
    if (this.canDecrement()) {
      this.value.update((v) => v - 1);
    }
  }
}
