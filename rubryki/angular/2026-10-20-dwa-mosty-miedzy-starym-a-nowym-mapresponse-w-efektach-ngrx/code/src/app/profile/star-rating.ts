import { ChangeDetectionStrategy, Component, forwardRef, signal } from '@angular/core';
import { ControlValueAccessor, NG_VALUE_ACCESSOR } from '@angular/forms';

/**
 * Klasyczny ControlValueAccessor (CVA) - "stary" kontrakt kontrolek formularzy Angulara
 * (odpowiednik interfejsu, który implementuje się, żeby własny widget dało się wpiąć w formularz).
 * Komponent NIE wie, kto go steruje: ngModel, [formControl], formControlName albo [formField].
 * `calls` zapisuje każde wywołanie z zewnątrz - to materiał pomiarowy dla testów.
 */
@Component({
  selector: 'app-star-rating',
  changeDetection: ChangeDetectionStrategy.OnPush,
  providers: [{ provide: NG_VALUE_ACCESSOR, useExisting: forwardRef(() => StarRating), multi: true }],
  template: `
    @for (n of stars; track n) {
      <button type="button" [disabled]="isDisabled()" (click)="pick(n)" (blur)="touch()">
        {{ n <= current() ? '★' : '☆' }}
      </button>
    }
  `,
})
export class StarRating implements ControlValueAccessor {
  readonly stars = [1, 2, 3, 4, 5];
  readonly current = signal(0);
  readonly isDisabled = signal(false);
  readonly calls: string[] = [];

  private onChange: (v: number) => void = () => {};
  private onTouched: () => void = () => {};

  writeValue(value: number | null): void {
    this.calls.push(`writeValue(${value})`);
    this.current.set(value ?? 0);
  }
  registerOnChange(fn: (v: number) => void): void {
    this.calls.push('registerOnChange');
    this.onChange = fn;
  }
  registerOnTouched(fn: () => void): void {
    this.calls.push('registerOnTouched');
    this.onTouched = fn;
  }
  setDisabledState(isDisabled: boolean): void {
    this.calls.push(`setDisabledState(${isDisabled})`);
    this.isDisabled.set(isDisabled);
  }

  pick(n: number): void {
    this.current.set(n);
    this.onChange(n);
  }
  touch(): void {
    this.onTouched();
  }
}
