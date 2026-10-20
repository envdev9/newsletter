import { Component, signal } from '@angular/core';
import { FormControl, Validators } from '@angular/forms';
import { FormField, required } from '@angular/forms/signals';
import { compatForm } from '@angular/forms/signals/compat';
import { StarRating } from './star-rating';

/**
 * compatForm: model Signal Forms, w którym JEDNO pole to stary `FormControl`.
 * Imię jest nowoczesne (schemat + [formField]), ocena - stara (FormControl + Validators.min + CVA).
 */
@Component({
  selector: 'app-profile-form',
  imports: [FormField, StarRating],
  template: `
    <form>
      <input id="name" [formField]="f.name" />
      <app-star-rating [formField]="f.rating" />
      @for (e of f.rating().errors(); track e.kind) {
        <p class="error">rating: {{ e.kind }}</p>
      }
    </form>
  `,
})
export class ProfileForm {
  readonly ratingControl = new FormControl(0, { nonNullable: true, validators: [Validators.min(3)] });
  readonly model = signal({ name: '', rating: this.ratingControl });
  readonly f = compatForm(this.model, (p) => {
    required(p.name);
  });
}
