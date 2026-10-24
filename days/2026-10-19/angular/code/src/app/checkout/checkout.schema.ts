import { InjectionToken, inject, resource } from '@angular/core';
import { debounce, required, schema, validateAsync } from '@angular/forms/signals';
import { AvailabilityApi } from './availability.api';

export interface Draft {
  name: string;
  code: string;
}

/** Szkic zamówienia, który serwer "załadował z bazy" - tu stała, w prawdziwej appce np. z sesji. */
export const DRAFT = new InjectionToken<Draft>('DRAFT', {
  providedIn: 'root',
  factory: () => ({ name: 'Anna', code: 'TAKEN' }),
});

export const checkoutSchema = schema<Draft>((p) => {
  required(p.name);
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
