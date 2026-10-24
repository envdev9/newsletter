import { ChangeDetectionStrategy, Component, Directive, forwardRef, inject, signal } from '@angular/core';
import {
  AbstractControl,
  AsyncValidator,
  ControlValueAccessor,
  NG_ASYNC_VALIDATORS,
  NG_VALUE_ACCESSOR,
  ValidationErrors,
} from '@angular/forms';
import { Observable, from, map } from 'rxjs';
import { AvailabilityApi } from './availability.api';

/**
 * Klasyczny `ControlValueAccessor` dla pola tekstowego (tak pisało się kontrolki do Reactive Forms).
 * `calls` zapisuje każde wywołanie metod CVA - materiał pomiarowy dla testów.
 */
@Component({
  selector: 'app-code-input',
  changeDetection: ChangeDetectionStrategy.OnPush,
  providers: [{ provide: NG_VALUE_ACCESSOR, useExisting: forwardRef(() => CodeInput), multi: true }],
  template: `
    <input
      type="text"
      [value]="current()"
      [disabled]="isDisabled()"
      (input)="type($event)"
      (blur)="markTouched()"
    />
  `,
})
export class CodeInput implements ControlValueAccessor {
  readonly current = signal('');
  readonly isDisabled = signal(false);
  readonly calls: string[] = [];

  private onChange: (v: string) => void = () => {};
  private onTouched: () => void = () => {};

  writeValue(value: string | null): void {
    this.calls.push(`writeValue(${JSON.stringify(value)})`);
    this.current.set(value ?? '');
  }
  registerOnChange(fn: (v: string) => void): void {
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

  type(event: Event): void {
    const value = (event.target as HTMLInputElement).value;
    this.current.set(value);
    this.onChange(value);
  }
  markTouched(): void {
    this.onTouched();
  }
}

/**
 * STARY asynchroniczny walidator w stylu Reactive Forms: `NG_ASYNC_VALIDATORS`, `validate()`
 * zwraca Observable. Pod `[formField]` nie jest nigdy wołany (zob. test) - `validateCalls` to dowód.
 */
@Directive({
  selector: '[appCodeAvailable]',
  providers: [{ provide: NG_ASYNC_VALIDATORS, useExisting: forwardRef(() => CodeAvailableValidator), multi: true }],
})
export class CodeAvailableValidator implements AsyncValidator {
  private readonly api = inject(AvailabilityApi);
  readonly validateCalls: string[] = [];

  validate(control: AbstractControl): Observable<ValidationErrors | null> {
    const code = String(control.value ?? '');
    this.validateCalls.push(code);
    return from(this.api.check(code)).pipe(map((taken) => (taken ? { taken: true } : null)));
  }
}
