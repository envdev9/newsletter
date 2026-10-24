import { Component, signal, viewChild } from '@angular/core';
import { ComponentFixture, TestBed } from '@angular/core/testing';
import { FormControl, ReactiveFormsModule } from '@angular/forms';
import { FormField, debounce, form, schema } from '@angular/forms/signals';
import { AvailabilityApi } from './availability.api';
import { CodeAvailableValidator, CodeInput } from './code-input';
import { SignupForm } from './signup-form';

const log = (label: string, value: unknown) =>
  console.log(`MEASURE ${label}: ${JSON.stringify(value)}`);

/** Stary async walidator (NG_ASYNC_VALIDATORS) pod [formField] - bez schematu. */
@Component({
  selector: 'app-legacy-host',
  imports: [FormField, CodeInput, CodeAvailableValidator],
  template: `<app-code-input appCodeAvailable [formField]="f.code" />`,
})
class LegacyHost {
  readonly model = signal({ code: 'TAKEN' });
  readonly f = form(this.model);
  readonly validator = viewChild.required(CodeAvailableValidator);
}

/** Ten sam komponent i ten sam walidator pod klasycznym Reactive Forms (grupa kontrolna). */
@Component({
  selector: 'app-reactive-host',
  imports: [ReactiveFormsModule, CodeInput, CodeAvailableValidator],
  template: `<app-code-input appCodeAvailable [formControl]="ctrl" />`,
})
class ReactiveHost {
  readonly ctrl = new FormControl('TAKEN', { nonNullable: true });
  readonly validator = viewChild.required(CodeAvailableValidator);
}

/** Pole z debounce(ms) lub debounce('blur') i niepustą wartością początkową. */
function makeDebounceHost(wait: number | 'blur') {
  @Component({
    selector: 'app-debounce-host',
    imports: [FormField, CodeInput],
    template: `<app-code-input [formField]="f.code" />`,
  })
  class DebounceHost {
    readonly model = signal({ code: 'START' });
    readonly f = form(this.model, schema<{ code: string }>((p) => debounce(p.code, wait)));
    readonly field = viewChild.required(FormField);
  }
  return DebounceHost;
}

async function wait(ms: number, fixture: ComponentFixture<unknown>) {
  await vi.advanceTimersByTimeAsync(ms);
  fixture.detectChanges();
}

function typeInto(fixture: ComponentFixture<unknown>, text: string) {
  const input = fixture.nativeElement.querySelector('input') as HTMLInputElement;
  input.value = text;
  input.dispatchEvent(new Event('input'));
  fixture.detectChanges();
  return input;
}

function blur(fixture: ComponentFixture<unknown>) {
  const input = fixture.nativeElement.querySelector('input') as HTMLInputElement;
  input.dispatchEvent(new FocusEvent('blur'));
  fixture.detectChanges();
}

describe('NG_ASYNC_VALIDATORS pod [formField]', () => {
  beforeEach(() => vi.useFakeTimers());
  afterEach(() => vi.useRealTimers());

  it('kontrola: ten sam walidator działa pod klasycznym [formControl]', async () => {
    TestBed.configureTestingModule({ imports: [ReactiveHost] });
    const fx = TestBed.createComponent(ReactiveHost);
    fx.detectChanges();
    await wait(300, fx);
    const api = TestBed.inject(AvailabilityApi);
    const snap = {
      validateCalls: fx.componentInstance.validator().validateCalls,
      requests: api.requests,
      errors: fx.componentInstance.ctrl.errors,
      status: fx.componentInstance.ctrl.status,
    };
    log('reactive-forms-control', snap);
    expect(snap.validateCalls).toEqual(['TAKEN']);
    expect(snap.errors).toEqual({ taken: true });
    expect(snap.status).toBe('INVALID');
  });

  it('[formField] NIGDY nie woła NG_ASYNC_VALIDATORS: brak wywołań, brak zapytań, pole valid', async () => {
    TestBed.configureTestingModule({ imports: [LegacyHost] });
    const fx = TestBed.createComponent(LegacyHost);
    fx.detectChanges();
    await wait(1000, fx);
    typeInto(fx, 'TAKEN2');
    await wait(1000, fx);
    const api = TestBed.inject(AvailabilityApi);
    const f = fx.componentInstance.f.code();
    const snap = {
      validateCalls: fx.componentInstance.validator().validateCalls,
      requests: api.requests,
      model: fx.componentInstance.model().code,
      errors: f.errors().map((e) => e.kind),
      valid: f.valid(),
      pending: f.pending(),
    };
    log('formfield-legacy-async', snap);
    expect(snap).toEqual({
      validateCalls: [],
      requests: [],
      model: 'TAKEN2',
      errors: [],
      valid: true,
      pending: false,
    });
  });
});

describe('validateAsync jako zamiennik (schemat + resource)', () => {
  beforeEach(() => vi.useFakeTimers());
  afterEach(() => vi.useRealTimers());

  function mountSignup() {
    TestBed.configureTestingModule({ imports: [SignupForm] });
    const fx = TestBed.createComponent(SignupForm);
    fx.detectChanges();
    const host = fx.componentInstance;
    host.f.code().value(); // pierwsza wartość pola musi być odczytana przed zapisem z UI (zob. #13)
    return { fx, host, api: TestBed.inject(AvailabilityApi) };
  }

  it('oś czasu: wpis → 300 ms debounce → zapytanie → 200 ms → błąd "taken"', async () => {
    const { fx, host, api } = mountSignup();
    typeInto(fx, 'TAKEN');
    const t0 = { model: host.model().code, pending: host.f.code().pending(), requests: [...api.requests] };
    await wait(299, fx);
    const t299 = { model: host.model().code, requests: [...api.requests] };
    await wait(1, fx);
    await wait(0, fx);
    const t300 = { model: host.model().code, pending: host.f.code().pending(), requests: [...api.requests] };
    await wait(200, fx);
    const t500 = {
      pending: host.f.code().pending(),
      errors: host.f.code().errors().map((e) => e.kind),
      valid: host.f.code().valid(),
    };
    log('validate-async-timeline', { t0, t299, t300, t500 });
    expect(t0).toEqual({ model: '', pending: false, requests: [] });
    expect(t299).toEqual({ model: '', requests: [] });
    expect(t300).toEqual({ model: 'TAKEN', pending: true, requests: ['TAKEN'] });
    expect(t500).toEqual({ pending: false, errors: ['taken'], valid: false });
  });

  it('wolny kod przechodzi; szybkie wpisy = jedno zapytanie', async () => {
    const { fx, host, api } = mountSignup();
    typeInto(fx, 'F');
    await wait(100, fx);
    typeInto(fx, 'FR');
    await wait(100, fx);
    typeInto(fx, 'FREE');
    await wait(300, fx);
    await wait(0, fx);
    await wait(200, fx);
    const snap = {
      requests: api.requests,
      errors: host.f.code().errors().map((e) => e.kind),
      valid: host.f.code().valid(),
    };
    log('validate-async-free', snap);
    expect(snap).toEqual({ requests: ['FREE'], errors: [], valid: true });
  });
});

describe('reset() w trakcie debounce - pułapka i obejście', () => {
  beforeEach(() => vi.useFakeTimers());
  afterEach(() => vi.useRealTimers());

  function mount(w: number | 'blur') {
    const Host = makeDebounceHost(w);
    TestBed.configureTestingModule({ imports: [Host] });
    const fx = TestBed.createComponent(Host);
    fx.detectChanges();
    const host = fx.componentInstance;
    const cva = fx.debugElement.children[0].componentInstance as CodeInput;
    const snap = () => ({
      ui: cva.current(),
      model: host.model().code,
      dirty: host.f.code().dirty(),
      touched: host.f.code().touched(),
    });
    return { fx, host, cva, snap };
  }

  it('pułapka (debounce 300): FormField.reset() cofa UI, po 300 ms wpis ląduje w modelu, a UI pokazuje stary tekst', async () => {
    const { fx, host, snap } = mount(300);
    typeInto(fx, 'TYPED');
    const typing = snap();
    host.field().reset();
    fx.detectChanges();
    await wait(0, fx);
    const afterReset = snap();
    await wait(300, fx);
    const later = snap();
    await wait(0, fx);
    TestBed.tick();
    const laterTick = snap();
    blur(fx);
    await wait(0, fx);
    const afterBlur = snap();
    log('reset-naive-300', { typing, afterReset, later, laterTick, afterBlur });
    expect(typing).toEqual({ ui: 'TYPED', model: 'START', dirty: true, touched: false });
    // UI wraca do wartości z modelu ("START"), ale to NIE jest czyszczenie formularza
    expect(afterReset).toEqual({ ui: 'START', model: 'START', dirty: true, touched: false });
    // PO 300 ms model dostaje wpis, ale UI nadal pokazuje "START": rozjazd UI/model, bez żadnego blura...
    expect(later).toEqual({ ui: 'START', model: 'TYPED', dirty: true, touched: false });
    expect(laterTick).toEqual(later);
    // ...który naprawia dopiero przypadkowy blur (efekt kontrolki odpala się ponownie na zmianie `touched`).
    expect(afterBlur).toEqual({ ui: 'TYPED', model: 'TYPED', dirty: true, touched: true });
  });

  it('pułapka (debounce blur): wpis czeka i wraca po blurze', async () => {
    const { fx, host, snap } = mount('blur');
    typeInto(fx, 'TYPED');
    host.field().reset();
    fx.detectChanges();
    await wait(5000, fx);
    const afterReset = snap();
    blur(fx);
    await wait(0, fx);
    const afterBlur = snap();
    log('reset-naive-blur', { afterReset, afterBlur });
    expect(afterReset).toMatchObject({ ui: 'START', model: 'START' });
    expect(afterBlur).toMatchObject({ ui: 'TYPED', model: 'TYPED', touched: true });
  });

  it('obejście: FieldState.reset(wartość) + FormField.reset() - nic nie wraca (debounce 300)', async () => {
    const { fx, host, snap } = mount(300);
    typeInto(fx, 'TYPED');
    host.f.code().reset('');
    host.field().reset();
    fx.detectChanges();
    await wait(0, fx);
    const afterReset = snap();
    await wait(1000, fx);
    const later = snap();
    blur(fx);
    await wait(0, fx);
    const afterBlur = snap();
    log('reset-workaround-300', { afterReset, later, afterBlur });
    expect(afterReset).toEqual({ ui: '', model: '', dirty: false, touched: false });
    expect(later).toEqual({ ui: '', model: '', dirty: false, touched: false });
    expect(afterBlur).toMatchObject({ ui: '', model: '' });
  });

  it('obejście działa też z debounce blur', async () => {
    const { fx, host, snap } = mount('blur');
    typeInto(fx, 'TYPED');
    host.f.code().reset('');
    host.field().reset();
    fx.detectChanges();
    await wait(0, fx);
    blur(fx);
    await wait(0, fx);
    const afterBlur = snap();
    log('reset-workaround-blur', { afterBlur });
    expect(afterBlur).toMatchObject({ ui: '', model: '' });
  });

  it('samo zapisanie wartości (bez FieldState.reset) czyści wpis, ale dirty zostaje', async () => {
    const { fx, host, snap } = mount(300);
    typeInto(fx, 'TYPED');
    host.f.code().value.set('');
    host.field().reset();
    fx.detectChanges();
    await wait(1000, fx);
    const s = snap();
    log('reset-set-only', s);
    expect(s).toEqual({ ui: '', model: '', dirty: true, touched: false });
  });

  it('samo FieldState.reset(wartość), bez FormField.reset(): UI dociąga się z modelu', async () => {
    const { fx, host, snap } = mount(300);
    typeInto(fx, 'TYPED');
    host.f.code().reset('');
    fx.detectChanges();
    await wait(1000, fx);
    const s = snap();
    log('reset-field-state-only', s);
    expect(s).toEqual({ ui: '', model: '', dirty: false, touched: false });
  });
});

describe('SignupForm: przyciski "Wyczyść" w DOM', () => {
  beforeEach(() => vi.useFakeTimers());
  afterEach(() => vi.useRealTimers());

  function mount() {
    TestBed.configureTestingModule({ imports: [SignupForm] });
    const fx = TestBed.createComponent(SignupForm);
    fx.detectChanges();
    fx.componentInstance.f.code().value();
    const click = (id: string) => {
      (fx.nativeElement.querySelector(id) as HTMLButtonElement).click();
      fx.detectChanges();
    };
    return { fx, host: fx.componentInstance, click, api: TestBed.inject(AvailabilityApi) };
  }

  it('obejście w trakcie lecącego zapytania: błąd "taken" znika, model pusty', async () => {
    const { fx, host, click, api } = mount();
    typeInto(fx, 'TAKEN');
    await wait(300, fx);
    await wait(0, fx);
    const inFlight = { pending: host.f.code().pending(), requests: [...api.requests] };
    click('#safe');
    await wait(1000, fx);
    const after = {
      model: host.model().code,
      pending: host.f.code().pending(),
      errors: host.f.code().errors().map((e) => e.kind),
      input: (fx.nativeElement.querySelector('input') as HTMLInputElement).value,
    };
    log('signup-safe-in-flight', { inFlight, after });
    expect(inFlight).toEqual({ pending: true, requests: ['TAKEN'] });
    expect(after.model).toBe('');
    expect(after.pending).toBe(false);
    expect(after.input).toBe('');
    // sam `required` jest po wyczyszczeniu aktywny; błąd async ("taken") zniknął
    expect(after.errors).not.toContain('taken');
  });

  it('naiwny przycisk po zapisanym wpisie nie czyści niczego', async () => {
    const { fx, host, click } = mount();
    typeInto(fx, 'FREE');
    await wait(300, fx);
    await wait(0, fx);
    await wait(200, fx);
    click('#naive');
    await wait(1000, fx);
    const s = {
      model: host.model().code,
      input: (fx.nativeElement.querySelector('input') as HTMLInputElement).value,
    };
    log('signup-naive-after-commit', s);
    expect(s).toEqual({ model: 'FREE', input: 'FREE' });
  });

  it('przycisk obejścia po zapisanym wpisie czyści model i UI', async () => {
    const { fx, host, click } = mount();
    typeInto(fx, 'FREE');
    await wait(300, fx);
    await wait(0, fx);
    await wait(200, fx);
    click('#safe');
    await wait(1000, fx);
    const s = {
      model: host.model().code,
      input: (fx.nativeElement.querySelector('input') as HTMLInputElement).value,
    };
    log('signup-safe-after-commit', s);
    expect(s).toEqual({ model: '', input: '' });
  });
});
