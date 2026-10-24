import { ChangeDetectionStrategy, Component, input, model, output } from '@angular/core';
import { DisabledReason, FormValueControl, ValidationError, WithOptionalFieldTree } from '@angular/forms/signals';

/**
 * Własna kontrolka z PEŁNYM opcjonalnym kontraktem `FormUiControl`: każdy `input()` poniżej jest
 * automatycznie zasilany przez dyrektywę `[formField]` stanem pola (bez ręcznego bindowania w szablonie).
 * Dla pola bez danej reguły dostaje wartość domyślną (np. `required` = false, `pattern` = []).
 */
@Component({
  selector: 'app-sku-input',
  changeDetection: ChangeDetectionStrategy.OnPush,
  template: `
    <input
      type="text"
      [value]="value()"
      [disabled]="disabled()"
      [readOnly]="readonly()"
      [attr.aria-required]="required()"
      [attr.aria-invalid]="invalid()"
      [attr.name]="name()"
      (input)="onInput($event)"
      (blur)="touch.emit()"
      (keydown.enter)="touch.emit()"
    />
    @if (disabledReasons().length > 0) {
      <small class="hint">{{ disabledReasons()[0].message }}</small>
    }
  `,
})
export class SkuInput implements FormValueControl<string> {
  /** Jedyny WYMAGANY element kontraktu. */
  readonly value = model('');

  // --- pola opcjonalne (stan pola) ---
  readonly errors = input<readonly ValidationError.WithOptionalFieldTree[]>([]);
  readonly disabled = input(false);
  readonly disabledReasons = input<readonly WithOptionalFieldTree<DisabledReason>[]>([]);
  readonly readonly = input(false);
  readonly hidden = input(false);
  readonly invalid = input(false);
  readonly pending = input(false);
  readonly touched = input(false);
  readonly dirty = input(false);
  readonly name = input('');
  readonly required = input(false);
  readonly minLength = input<number | undefined>(undefined);
  readonly maxLength = input<number | undefined>(undefined);
  readonly pattern = input<readonly RegExp[]>([]);

  /**
   * Bez tego outputu `debounce('blur')` nigdy się nie domknie (zob. NoTouchSkuInput i test).
   * Emituj na `blur` (utrata fokusu), NIE na `focus`.
   */
  readonly touch = output<void>();

  protected onInput(event: Event): void {
    this.value.set((event.target as HTMLInputElement).value);
  }
}

/**
 * Ta sama kontrolka, ALE bez outputu `touch` - celowo zepsuta, żeby zmierzyć co się dzieje.
 * Spełnia kontrakt `FormValueControl` (wymagane jest tylko `value`), więc kompiluje się bez ostrzeżeń.
 */
@Component({
  selector: 'app-no-touch-sku-input',
  changeDetection: ChangeDetectionStrategy.OnPush,
  template: `<input type="text" [value]="value()" (input)="onInput($event)" />`,
})
export class NoTouchSkuInput implements FormValueControl<string> {
  readonly value = model('');

  protected onInput(event: Event): void {
    this.value.set((event.target as HTMLInputElement).value);
  }
}
