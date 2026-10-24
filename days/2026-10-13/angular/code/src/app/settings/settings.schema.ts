import { debounce, disabled, min, readonly, schema } from '@angular/forms/signals';

export type SettingsMode = 'edit' | 'locked' | 'readonly';

export interface SettingsModel {
  newsletter: boolean;
  rating: number;
  mode: SettingsMode;
}

export const emptySettings = (): SettingsModel => ({ newsletter: false, rating: 0, mode: 'edit' });

/**
 * - `newsletter` (FormCheckboxControl): debounce 300 ms - szybkie klikanie zbiera się w jeden zapis.
 * - `rating` (stary ControlValueAccessor): debounce('blur') - zapis dopiero po `onTouched()`.
 */
export const settingsSchema = schema<SettingsModel>((p) => {
  debounce(p.newsletter, 300);
  debounce(p.rating, 'blur');
  min(p.rating, 1, { message: 'Wybierz co najmniej 1 gwiazdkę' });
  disabled(p.rating, { when: ({ valueOf }) => valueOf(p.mode) === 'locked' });
  readonly(p.rating, { when: ({ valueOf }) => valueOf(p.mode) === 'readonly' });
});
