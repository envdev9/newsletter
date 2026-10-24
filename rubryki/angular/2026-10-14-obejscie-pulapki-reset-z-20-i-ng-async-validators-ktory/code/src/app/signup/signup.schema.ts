import { inject, resource } from '@angular/core';
import { debounce, required, schema, validateAsync } from '@angular/forms/signals';
import { AvailabilityApi } from './availability.api';

export interface SignupModel {
  code: string;
}

export const emptySignup = (): SignupModel => ({ code: '' });

/**
 * Wariant "nowy": walidacja asynchroniczna po stronie schematu (`validateAsync` + `resource`).
 * To zastępuje `NG_ASYNC_VALIDATORS`, które Signal Forms ignoruje na kontrolce CVA.
 */
export const signupSchema = schema<SignupModel>((p) => {
  required(p.code);
  debounce(p.code, 300);
  validateAsync(p.code, {
    params: (ctx) => ctx.value() || undefined,
    factory: (params) => {
      const api = inject(AvailabilityApi);
      return resource({
        params,
        loader: ({ params: code, abortSignal }) => api.check(code, abortSignal),
      });
    },
    onSuccess: (taken) => (taken ? { kind: 'taken', message: 'Kod jest zajęty' } : undefined),
    onError: () => ({ kind: 'check-failed', message: 'Nie udało się sprawdzić kodu' }),
  });
});
