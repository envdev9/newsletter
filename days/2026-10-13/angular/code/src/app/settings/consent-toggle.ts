import { ChangeDetectionStrategy, Component, input, model, output } from '@angular/core';
import { FormCheckboxControl } from '@angular/forms/signals';

/**
 * Własny przełącznik zgody (switch) jako `FormCheckboxControl`.
 * Różnica względem `FormValueControl<boolean>`: wymagany model nazywa się `checked`, nie `value`
 * (kontrakt zabrania mieć oba - `value?: undefined` w typie `FormCheckboxControl`).
 */
@Component({
  selector: 'app-consent-toggle',
  changeDetection: ChangeDetectionStrategy.OnPush,
  template: `
    <button
      type="button"
      role="switch"
      [attr.aria-checked]="checked()"
      [disabled]="disabled()"
      (click)="toggle()"
      (blur)="touch.emit()"
    >
      {{ checked() ? 'TAK' : 'NIE' }}
    </button>
  `,
})
export class ConsentToggle implements FormCheckboxControl {
  /** Jedyny WYMAGANY element kontraktu checkboxa. */
  readonly checked = model(false);

  readonly disabled = input(false);
  readonly touched = input(false);
  readonly dirty = input(false);
  readonly invalid = input(false);

  /** Emituj na blur - bez tego `debounce('blur')` nie domknie się nigdy (zob. #19). */
  readonly touch = output<void>();

  /** Licznik instancji `reset()` wywołanych przez dyrektywę (do testów). */
  resetCalls = 0;

  toggle(): void {
    this.checked.update((v) => !v);
  }

  /** Opcjonalny element kontraktu `FormUiControl`; wołany przez `FormField.reset()`. */
  reset(): void {
    this.resetCalls++;
  }
}
