import { ChangeDetectionStrategy, Component, signal, viewChild } from '@angular/core';
import { FormField, form } from '@angular/forms/signals';
import { CodeInput } from './code-input';
import { SignupModel, emptySignup, signupSchema } from './signup.schema';

@Component({
  selector: 'app-signup-form',
  changeDetection: ChangeDetectionStrategy.OnPush,
  imports: [FormField, CodeInput],
  template: `
    <label>Kod promocyjny <app-code-input [formField]="f.code" /></label>
    <p class="status">
      model: <code>{{ model().code }}</code> · pending: {{ f.code().pending() }} ·
      błędy: {{ errorKinds() }}
    </p>
    <button type="button" id="naive" (click)="naiveReset()">Wyczyść (naiwnie)</button>
    <button type="button" id="safe" (click)="safeReset()">Wyczyść (obejście)</button>
  `,
})
export class SignupForm {
  readonly model = signal<SignupModel>(emptySignup());
  readonly f = form(this.model, signupSchema);
  private readonly field = viewChild.required(FormField);

  errorKinds(): string {
    return this.f.code().errors().map((e) => e.kind).join(',') || '-';
  }

  /** Naiwnie: tylko `FormField.reset()` - UI wraca do modelu, ale oczekujący wpis zostaje. */
  naiveReset(): void {
    this.field().reset();
  }

  /**
   * Obejście: najpierw `FieldState.reset(wartość)` (zeruje touched/dirty i ustawia model),
   * dopiero potem `FormField.reset()` (przepisuje model do kontrolki).
   */
  safeReset(): void {
    this.f.code().reset('');
    this.field().reset();
  }
}
