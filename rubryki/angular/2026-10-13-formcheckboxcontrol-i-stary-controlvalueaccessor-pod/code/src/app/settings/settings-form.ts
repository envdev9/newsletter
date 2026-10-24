import { Component, signal } from '@angular/core';
import { FormField, form } from '@angular/forms/signals';
import { ConsentToggle } from './consent-toggle';
import { SettingsMode, SettingsModel, emptySettings, settingsSchema } from './settings.schema';
import { MinStarsValidator, StarRating } from './star-rating';

@Component({
  selector: 'app-settings-form',
  imports: [FormField, ConsentToggle, StarRating, MinStarsValidator],
  template: `
    <form>
      <label>Newsletter (FormCheckboxControl, debounce 300 ms)</label>
      <app-consent-toggle [formField]="f.newsletter" />

      <label>Ocena (stary ControlValueAccessor, debounce 'blur')</label>
      <app-star-rating appMinStars [formField]="f.rating" />

      <p class="hint">
        Model: newsletter=<code id="m-news">{{ model().newsletter }}</code>,
        rating=<code id="m-rating">{{ model().rating }}</code>
      </p>
      @for (e of f.rating().errors(); track e.kind) {
        <p class="error">{{ e.kind }}</p>
      }
    </form>
  `,
})
export class SettingsForm {
  readonly model = signal<SettingsModel>(emptySettings());
  readonly f = form(this.model, settingsSchema);

  setMode(mode: SettingsMode): void {
    this.model.update((m) => ({ ...m, mode }));
  }
}
