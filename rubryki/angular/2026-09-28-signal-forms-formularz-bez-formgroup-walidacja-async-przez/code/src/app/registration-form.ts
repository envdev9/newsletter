import { Component, resource, signal } from '@angular/core';
import { FormField, FormRoot, email, form, minLength, pattern, required, validateAsync } from '@angular/forms/signals';
import { registerUser } from './registration-backend';
import { checkUsernameAvailability } from './username-availability';

interface RegistrationModel {
  username: string;
  email: string;
  password: string;
}

/**
 * Formularz rejestracji zbudowany na Signal Forms (`@angular/forms/signals`, publicApi 22.0).
 *
 * Model to zwykły `signal()` - `form()` go NIE kopiuje, tylko owija w drzewo pól (`FieldTree`).
 * Walidacja (schema function) to osobny, deklaratywny opis reguł - odpowiednik FluentValidation
 * w .NET, tylko reaktywny i wpięty bezpośrednio w drzewo pól zamiast osobnego walidatora klasowego.
 */
@Component({
  selector: 'app-registration-form',
  imports: [FormField, FormRoot],
  template: `
    <form [formRoot]="registrationForm">
      <div class="field">
        <label for="username">Login</label>
        <input id="username" type="text" [formField]="registrationForm.username" />
        @if (registrationForm.username().pending()) {
          <p class="hint">Sprawdzam dostępność…</p>
        }
        @for (e of registrationForm.username().errors(); track e.kind) {
          <p class="error">{{ e.message }}</p>
        }
      </div>

      <div class="field">
        <label for="email">E-mail</label>
        <input id="email" type="email" [formField]="registrationForm.email" />
        @for (e of registrationForm.email().errors(); track e.kind) {
          <p class="error">{{ e.message }}</p>
        }
      </div>

      <div class="field">
        <label for="password">Hasło</label>
        <input id="password" type="password" [formField]="registrationForm.password" />
        @for (e of registrationForm.password().errors(); track e.kind) {
          <p class="error">{{ e.message }}</p>
        }
      </div>

      <button type="submit" [disabled]="registrationForm().submitting() || !registrationForm().valid()">
        @if (registrationForm().submitting()) {
          Wysyłanie…
        } @else {
          Zarejestruj
        }
      </button>

      @switch (lastResult()) {
        @case ('success') {
          <p class="result ok">Konto utworzone.</p>
        }
        @case ('error') {
          <p class="result fail">Nie udało się utworzyć konta - zobacz błędy powyżej.</p>
        }
      }
    </form>
  `,
})
export class RegistrationForm {
  protected readonly model = signal<RegistrationModel>({ username: '', email: '', password: '' });
  protected readonly lastResult = signal<'idle' | 'success' | 'error'>('idle');

  protected readonly registrationForm = form(
    this.model,
    (f) => {
      // --- login: sync + async (dostępność sprawdzana "na serwerze") ---
      required(f.username, { message: 'Login jest wymagany' });
      minLength(f.username, 3, { message: 'Login musi mieć co najmniej 3 znaki' });

      // Async walidacja rusza dopiero, gdy required/minLength przechodzą (dokumentacja API:
      // "Async validation for a field only runs once all synchronous validation is passing").
      // `factory` dostaje Signal<params> i musi zwrócić Resource - to jest DOKŁADNIE `resource()`
      // z własnym loaderem i AbortSignal, tylko wpięte w system walidacji formularza.
      validateAsync(f.username, {
        params: (ctx) => ctx.value(),
        debounce: 300,
        factory: (usernameSignal) =>
          resource({
            params: () => usernameSignal(),
            loader: ({ params, abortSignal }) => checkUsernameAvailability(params, abortSignal),
          }),
        onSuccess: (result) =>
          result.available ? undefined : { kind: 'taken', message: `Login "${result.username}" jest zajęty` },
        onError: () => ({ kind: 'check-failed', message: 'Nie udało się sprawdzić dostępności loginu' }),
      });

      // --- e-mail ---
      required(f.email, { message: 'Adres e-mail jest wymagany' });
      email(f.email, { message: 'To nie wygląda na adres e-mail' });

      // --- hasło ---
      required(f.password, { message: 'Hasło jest wymagane' });
      minLength(f.password, 8, { message: 'Hasło musi mieć co najmniej 8 znaków' });
      pattern(f.password, /\d/, { message: 'Hasło musi zawierać przynajmniej jedną cyfrę' });
    },
    {
      submission: {
        // Wywoływane przez [formRoot] po natywnym submit, TYLKO gdy klientowa walidacja przeszła.
        // Błąd "z serwera" mapowany jest z powrotem na konkretne pole przez `fieldTree`.
        action: async (f) => {
          const outcome = await registerUser(f().value());
          if (outcome.kind === 'email-taken') {
            this.lastResult.set('error');
            return [{ fieldTree: f.email, kind: 'server', message: outcome.message }];
          }
          this.lastResult.set('success');
          return undefined;
        },
      },
    },
  );
}
