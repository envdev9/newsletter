import { Component, signal, viewChild } from '@angular/core';
import { TestBed } from '@angular/core/testing';
import { FormControl, FormGroup, FormsModule, ReactiveFormsModule, Validators } from '@angular/forms';
import { FormField, form, required } from '@angular/forms/signals';
import { SignalFormControl, extractValue } from '@angular/forms/signals/compat';
import { ProfileForm } from './profile-form';
import { StarRating } from './star-rating';

const measure = (name: string, data: unknown) => console.log(`MEASURE ${name}: ${JSON.stringify(data)}`);
const settle = async (fixture: { whenStable(): Promise<unknown> }) => {
  await fixture.whenStable();
};

@Component({ selector: 'app-h-ngmodel', imports: [FormsModule, StarRating], template: `<app-star-rating [(ngModel)]="rating" />` })
class NgModelHost {
  rating = 2;
  readonly star = viewChild.required(StarRating);
}

@Component({ selector: 'app-h-fc', imports: [ReactiveFormsModule, StarRating], template: `<app-star-rating [formControl]="ctrl" />` })
class FormControlHost {
  readonly ctrl = new FormControl(2);
  readonly star = viewChild.required(StarRating);
}

@Component({ selector: 'app-h-ff', imports: [FormField, StarRating], template: `<app-star-rating [formField]="f.rating" />` })
class FormFieldHost {
  readonly model = signal({ rating: 2 });
  readonly f = form(this.model);
  readonly star = viewChild.required(StarRating);
}

@Component({
  selector: 'app-h-both',
  imports: [FormsModule, FormField, StarRating],
  template: `<app-star-rating [formField]="f.rating" [(ngModel)]="legacy" />`,
})
class BothHost {
  legacy = 1;
  readonly model = signal({ rating: 2 });
  readonly f = form(this.model);
  readonly star = viewChild.required(StarRating);
}

@Component({
  selector: 'app-h-both-rev',
  imports: [FormsModule, FormField, StarRating],
  template: `<app-star-rating [(ngModel)]="legacy" [formField]="f.rating" />`,
})
class BothReversedHost {
  legacy = 1;
  readonly model = signal({ rating: 2 });
  readonly f = form(this.model);
  readonly star = viewChild.required(StarRating);
}

@Component({
  selector: 'app-h-group',
  imports: [ReactiveFormsModule, FormField, StarRating],
  template: `
    <form [formGroup]="group">
      <input id="name" [formField]="name.fieldTree" />
      <app-star-rating formControlName="rating" />
    </form>
  `,
})
class GroupHost {
  readonly name = new SignalFormControl('', (p) => {
    required(p);
  });
  readonly group = new FormGroup({
    name: this.name,
    rating: new FormControl(0, { nonNullable: true, validators: [Validators.min(3)] }),
  });
  readonly star = viewChild.required(StarRating);
}

describe('CVA obok Signal Forms', () => {
  it('ta sama kontrolka pod ngModel, [formControl] i [formField]: kolejność wywołań CVA', async () => {
    const a = TestBed.createComponent(NgModelHost);
    a.detectChanges();
    await settle(a);
    const b = TestBed.createComponent(FormControlHost);
    b.detectChanges();
    await settle(b);
    const c = TestBed.createComponent(FormFieldHost);
    c.detectChanges();
    await settle(c);
    const calls = {
      ngModel: a.componentInstance.star().calls,
      formControl: b.componentInstance.star().calls,
      formField: c.componentInstance.star().calls,
    };
    measure('cva-calls', calls);
    // ngModel: najpierw null (wartość przychodzi asynchronicznie, mikrozadaniem), potem rejestracja, na końcu prawdziwa wartość
    expect(calls.ngModel).toEqual(['writeValue(null)', 'setDisabledState(false)', 'registerOnChange', 'registerOnTouched', 'writeValue(2)']);
    // [formControl]: wartość od razu, potem rejestracja
    expect(calls.formControl).toEqual(['writeValue(2)', 'setDisabledState(false)', 'registerOnChange', 'registerOnTouched']);
    // [formField]: rejestracja, potem wartość i stan disabled
    expect(calls.formField).toEqual(['registerOnChange', 'registerOnTouched', 'writeValue(2)', 'setDisabledState(false)']);
  });

  it('PUŁAPKA: ngModel i [formField] na jednym elemencie - bez błędu, ngModel po cichu wygrywa (obie kolejności atrybutów)', async () => {
    const warn = vi.spyOn(console, 'warn');
    const errorSpy = vi.spyOn(console, 'error');
    const results: Record<string, unknown> = {};
    for (const [name, Host] of [['ngModel-first', BothReversedHost], ['formField-first', BothHost]] as const) {
      const f = TestBed.createComponent(Host);
      f.detectChanges();
      await settle(f);
      const initialCalls = [...f.componentInstance.star().calls];
      f.nativeElement.querySelectorAll('button')[4].click();
      f.detectChanges();
      await settle(f);
      results[name] = {
        initialCalls,
        modelAfterClick: f.componentInstance.model(),
        legacyAfterClick: f.componentInstance.legacy,
        shownStars: f.componentInstance.star().current(),
      };
    }
    measure('both', { results, warns: warn.mock.calls.length, errors: errorSpy.mock.calls.length });
    for (const r of Object.values(results) as { modelAfterClick: { rating: number }; legacyAfterClick: number; shownStars: number }[]) {
      expect(r.legacyAfterClick).toBe(5); // zmienił się model ngModel
      expect(r.modelAfterClick.rating).toBe(2); // model Signal Forms NIETKNIĘTY
      expect(r.shownStars).toBe(5);
    }
    expect(warn).not.toHaveBeenCalled(); // i żadnego ostrzeżenia
    expect(errorSpy).not.toHaveBeenCalled();
    warn.mockRestore();
    errorSpy.mockRestore();
  });

  it('compatForm: FormControl w modelu + CVA - walidator ze starego FormControl widać w errors() pola', async () => {
    const f = TestBed.createComponent(ProfileForm);
    f.detectChanges();
    await settle(f);
    const cmp = f.componentInstance;
    const star = f.debugElement.children[0].children[1].componentInstance as StarRating;
    const init = {
      calls: [...star.calls],
      value: cmp.f.rating().value(),
      errors: cmp.f.rating().errors().map((e) => e.kind),
      valid: cmp.f().valid(),
      nameErrors: cmp.f.name().errors().map((e) => e.kind),
    };
    measure('compat-init', init);
    expect(init.value).toBe(0); // pole zwraca WARTOŚĆ kontrolki, nie obiekt FormControl
    expect(init.errors).toEqual(['min']); // Validators.min(3) ze starego FormControl
    expect(init.nameErrors).toEqual(['required']); // nowy schemat obok
    expect(init.valid).toBe(false);

    (f.nativeElement.querySelectorAll('button')[3] as HTMLButtonElement).click();
    f.detectChanges();
    await settle(f);
    const afterClick = {
      control: cmp.ratingControl.value,
      fieldValue: cmp.f.rating().value(),
      errors: cmp.f.rating().errors().length,
      dirty: cmp.f.rating().dirty(),
      touched: cmp.f.rating().touched(),
      controlDirty: cmp.ratingControl.dirty,
    };
    measure('compat-after-click', afterClick);
    expect(afterClick.control).toBe(4); // klik -> CVA -> FormControl
    expect(afterClick.fieldValue).toBe(4); // ... i widoczne w polu Signal Forms
    expect(afterClick.errors).toBe(0);
    expect(afterClick.dirty).toBe(true);

    (f.nativeElement.querySelectorAll('button')[3] as HTMLButtonElement).dispatchEvent(new Event('blur'));
    f.detectChanges();
    await settle(f);
    const afterBlur = { fieldTouched: cmp.f.rating().touched(), controlTouched: cmp.ratingControl.touched };
    measure('compat-after-blur', afterBlur);

    cmp.ratingControl.setValue(5); // zapis z kodu do starego FormControl
    f.detectChanges();
    await settle(f);
    measure('compat-after-setValue', { lastCall: star.calls.at(-1), fieldValue: cmp.f.rating().value() });
    expect(star.calls.at(-1)).toBe('writeValue(5)'); // CVA dostaje wartość
    expect(cmp.f.rating().value()).toBe(5);

    cmp.ratingControl.disable();
    f.detectChanges();
    await settle(f);
    const afterDisable = { lastCall: star.calls.at(-1), fieldDisabled: cmp.f.rating().disabled() };
    measure('compat-after-disable', afterDisable);

    const extracted = extractValue(cmp.f);
    measure('compat-extract', { extracted, modelStillHoldsControl: cmp.model().rating === cmp.ratingControl });
    expect(extracted).toEqual({ name: '', rating: 5 });
    expect(cmp.model().rating).toBe(cmp.ratingControl); // sygnał trzyma nadal obiekt FormControl
  });

  it('SignalFormControl w FormGroup: nowoczesne pole [formField] i stary CVA formControlName w jednej grupie', async () => {
    const f = TestBed.createComponent(GroupHost);
    f.detectChanges();
    await settle(f);
    const g = f.componentInstance.group;
    const init = {
      valid: g.valid,
      status: g.status,
      nameErrors: f.componentInstance.name.errors,
      ratingErrors: g.controls.rating.errors,
    };
    measure('group-init', init);
    expect(init.valid).toBe(false);
    expect(Object.keys(init.nameErrors ?? {})).toEqual(['required']); // klucz = kind błędu Signal Forms
    expect((init.nameErrors as Record<string, { kind: string }>)['required'].kind).toBe('required');
    expect(init.ratingErrors).toEqual({ min: { min: 3, actual: 0 } });

    const input = f.nativeElement.querySelector('#name') as HTMLInputElement;
    input.value = 'Ola';
    input.dispatchEvent(new Event('input'));
    (f.nativeElement.querySelectorAll('button')[3] as HTMLButtonElement).click();
    f.detectChanges();
    await settle(f);
    const after = { valid: g.valid, value: g.value, dirty: g.dirty, nameTouched: g.controls.name.touched };
    measure('group-after-input', after);
    expect(after.valid).toBe(true);
    expect(after.value).toEqual({ name: 'Ola', rating: 4 });

    input.dispatchEvent(new Event('blur'));
    f.detectChanges();
    await settle(f);
    const afterBlur = { nameTouched: g.controls.name.touched, groupTouched: g.touched };
    measure('group-after-blur', afterBlur);
  });
});
