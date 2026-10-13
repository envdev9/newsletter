import { ChangeDetectionStrategy, Component, Directive, forwardRef, input, model, output, signal } from '@angular/core';
import {
  AbstractControl,
  ControlValueAccessor,
  NG_VALIDATORS,
  NG_VALUE_ACCESSOR,
  ValidationErrors,
  Validator,
} from '@angular/forms';
import { FormValueControl } from '@angular/forms/signals';

/**
 * "Stary" komponent: klasyczny `ControlValueAccessor` (tak pisało się kontrolki do Reactive Forms).
 * Podpinany pod Signal Forms przez `[formField]` bez zmian w kodzie komponentu.
 * `calls` zapisuje każde wywołanie metod CVA - to jest materiał pomiarowy dla testów.
 */
@Component({
  selector: 'app-star-rating',
  changeDetection: ChangeDetectionStrategy.OnPush,
  providers: [{ provide: NG_VALUE_ACCESSOR, useExisting: forwardRef(() => StarRating), multi: true }],
  template: `
    @for (n of stars; track n) {
      <button
        type="button"
        [disabled]="isDisabled()"
        [class.on]="n <= current()"
        (click)="pick(n)"
        (blur)="markTouched()"
      >
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

  /** Zwykłe `input()` na komponencie z CVA: dyrektywa też je zasila (zob. test). */
  readonly readonly = input(false);

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
    if (this.readonly()) return;
    this.current.set(n);
    this.onChange(n);
  }
  markTouched(): void {
    this.onTouched();
  }
}

/** Stary walidator jako dyrektywa z `NG_VALIDATORS` (styl Reactive Forms): min. 3 gwiazdki. */
@Directive({
  selector: '[appMinStars]',
  providers: [{ provide: NG_VALIDATORS, useExisting: forwardRef(() => MinStarsValidator), multi: true }],
})
export class MinStarsValidator implements Validator {
  validate(control: AbstractControl): ValidationErrors | null {
    const v = control.value as number | null;
    return (v ?? 0) >= 3 ? null : { minStars: { min: 3, actual: v ?? 0 } };
  }
}

/**
 * Kontrolka, która implementuje JEDNOCZEŚNIE `ControlValueAccessor` i `FormValueControl`.
 * Pytanie pomiarowe: którą ścieżkę wybierze `[formField]`?
 */
@Component({
  selector: 'app-dual-rating',
  changeDetection: ChangeDetectionStrategy.OnPush,
  providers: [{ provide: NG_VALUE_ACCESSOR, useExisting: forwardRef(() => DualRating), multi: true }],
  template: `<span>{{ value() }}</span>`,
})
export class DualRating implements ControlValueAccessor, FormValueControl<number> {
  readonly value = model(0);
  readonly touch = output<void>();
  readonly calls: string[] = [];

  writeValue(v: number | null): void {
    this.calls.push(`writeValue(${v})`);
  }
  registerOnChange(): void {
    this.calls.push('registerOnChange');
  }
  registerOnTouched(): void {
    this.calls.push('registerOnTouched');
  }
}
