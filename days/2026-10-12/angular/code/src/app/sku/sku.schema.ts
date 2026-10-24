import {
  debounce,
  disabled,
  hidden,
  maxLength,
  pattern,
  readonly,
  required,
  schema,
} from '@angular/forms/signals';

/** Tryb pola SKU - steruje trzema różnymi "wyłączeniami" tego samego pola. */
export type SkuMode = 'edit' | 'locked' | 'readonly' | 'hidden';

export interface SkuModel {
  sku: string;
  mode: SkuMode;
}

export const emptySku = (): SkuModel => ({ sku: '', mode: 'edit' });

export const LOCK_REASON = 'Magazyn zablokował edycję SKU';

/**
 * Jedno pole, trzy sposoby wyłączenia. Wszystkie trzy (disabled/readonly/hidden) wg kodu
 * `shouldSkipValidation` pomijają walidację - to mierzy `sku-control.spec.ts`.
 */
export const skuSchema = schema<SkuModel>((p) => {
  debounce(p.sku, 'blur');
  required(p.sku, { message: 'SKU jest wymagane' });
  pattern(p.sku, /^[A-Z]{3}-\d{4}$/, { message: 'Format: ABC-1234' });
  maxLength(p.sku, 8);
  disabled(p.sku, {
    when: ({ valueOf }) => (valueOf(p.mode) === 'locked' ? LOCK_REASON : false),
  });
  readonly(p.sku, { when: ({ valueOf }) => valueOf(p.mode) === 'readonly' });
  hidden(p.sku, { when: ({ valueOf }) => valueOf(p.mode) === 'hidden' });
});
