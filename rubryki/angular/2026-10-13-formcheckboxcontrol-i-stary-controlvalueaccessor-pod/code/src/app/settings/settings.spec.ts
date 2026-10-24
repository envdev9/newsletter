import { Component, signal } from '@angular/core';
import { ComponentFixture, TestBed } from '@angular/core/testing';
import { By } from '@angular/platform-browser';
import { FormField, debounce, form, schema } from '@angular/forms/signals';
import { ConsentToggle } from './consent-toggle';
import { SettingsForm } from './settings-form';
import { SettingsModel, emptySettings } from './settings.schema';
import { DualRating, MinStarsValidator, StarRating } from './star-rating';

const log = (label: string, value: unknown) =>
  console.log(`MEASURE ${label}: ${JSON.stringify(value)}`);

/** Natywny checkbox - punkt odniesienia dla własnego FormCheckboxControl. */
@Component({
  selector: 'app-native-host',
  imports: [FormField],
  template: `<input id="n" type="checkbox" [formField]="f.newsletter" />`,
})
class NativeCheckboxHost {
  readonly model = signal<SettingsModel>(emptySettings());
  readonly f = form(
    this.model,
    schema<SettingsModel>((p) => debounce(p.newsletter, 300)),
  );
}

/** Własny checkbox, ale z debounce('blur'). */
@Component({
  selector: 'app-blur-host',
  imports: [FormField, ConsentToggle],
  template: `<app-consent-toggle [formField]="f.newsletter" />`,
})
class BlurToggleHost {
  readonly model = signal<SettingsModel>(emptySettings());
  readonly f = form(
    this.model,
    schema<SettingsModel>((p) => debounce(p.newsletter, 'blur')),
  );
}

@Component({
  selector: 'app-dual-host',
  imports: [FormField, DualRating],
  template: `<app-dual-rating [formField]="f.rating" />`,
})
class DualHost {
  readonly model = signal<SettingsModel>(emptySettings());
  readonly f = form(this.model);
}

@Component({
  selector: 'app-dual-blur-host',
  imports: [FormField, DualRating],
  template: `<app-dual-rating [formField]="f.rating" />`,
})
class DualBlurHost {
  readonly model = signal<SettingsModel>(emptySettings());
  readonly f = form(
    this.model,
    schema<SettingsModel>((p) => debounce(p.rating, 'blur')),
  );
}

/** Gwiazdki z debounce('blur') pod @if - do testu zniszczenia kontrolki. */
@Component({
  selector: 'app-cva-if-host',
  imports: [FormField, StarRating],
  template: `
    @if (visible()) {
      <app-star-rating [formField]="f.rating" />
    }
  `,
})
class CvaIfHost {
  readonly model = signal<SettingsModel>(emptySettings());
  readonly f = form(
    this.model,
    schema<SettingsModel>((p) => debounce(p.rating, 'blur')),
  );
  readonly visible = signal(true);
}

/** Kontrolka CVA BEZ walidatora i z zerowym schematem - żeby zobaczyć sam walidator. */
@Component({
  selector: 'app-validator-host',
  imports: [FormField, StarRating, MinStarsValidator],
  template: `<app-star-rating appMinStars [formField]="f.rating" />`,
})
class ValidatorHost {
  readonly model = signal<SettingsModel>(emptySettings());
  readonly f = form(this.model);
}

function mount() {
  TestBed.configureTestingModule({ imports: [SettingsForm] });
  const fixture: ComponentFixture<SettingsForm> = TestBed.createComponent(SettingsForm);
  fixture.detectChanges();
  const host = fixture.componentInstance;
  const root = fixture.nativeElement as HTMLElement;
  const toggle = () => fixture.debugElement.query(By.directive(ConsentToggle)).componentInstance as ConsentToggle;
  const stars = () => fixture.debugElement.query(By.directive(StarRating)).componentInstance as StarRating;
  const toggleBtn = () => root.querySelector('app-consent-toggle button') as HTMLButtonElement;
  const starBtn = (n: number) =>
    root.querySelectorAll('app-star-rating button')[n - 1] as HTMLButtonElement;
  const click = (el: HTMLElement) => {
    el.dispatchEvent(new MouseEvent('click', { bubbles: true }));
    fixture.detectChanges();
  };
  const blur = (el: HTMLElement) => {
    el.dispatchEvent(new FocusEvent('blur'));
    fixture.detectChanges();
  };
  const setMode = (m: Parameters<SettingsForm['setMode']>[0]) => {
    host.setMode(m);
    fixture.detectChanges();
  };
  return { fixture, host, root, toggle, stars, toggleBtn, starBtn, click, blur, setMode };
}

async function wait(ms: number, fixture: ComponentFixture<unknown>) {
  await vi.advanceTimersByTimeAsync(ms);
  fixture.detectChanges();
}

describe('FormCheckboxControl + debounce(ms)', () => {
  beforeEach(() => vi.useFakeTimers());
  afterEach(() => vi.useRealTimers());

  it('kontrakt: checked zamiast value, stan pola zasila kontrolkę', () => {
    const m = mount();
    const t = m.toggle();
    const snap = {
      checked: t.checked(),
      disabled: t.disabled(),
      touched: t.touched(),
      dirty: t.dirty(),
      invalid: t.invalid(),
    };
    log('checkbox-contract', snap);
    expect(snap).toEqual({ checked: false, disabled: false, touched: false, dirty: false, invalid: false });
  });

  it('klik: kontrolka zmienia się od razu, model po 300 ms', async () => {
    const m = mount();
    m.click(m.toggleBtn());
    const t0 = { control: m.toggle().checked(), model: m.host.model().newsletter, dirty: m.host.f.newsletter().dirty() };
    await wait(299, m.fixture);
    const t299 = { model: m.host.model().newsletter };
    await wait(1, m.fixture);
    const t300 = { model: m.host.model().newsletter };
    log('checkbox-click', { t0, t299, t300 });
    expect(t0).toEqual({ control: true, model: false, dirty: true });
    expect(t299.model).toBe(false);
    expect(t300.model).toBe(true);
  });

  it('parzysta liczba klików w oknie: model nie zmienia się, dirty zostaje', async () => {
    const m = mount();
    m.click(m.toggleBtn());
    m.click(m.toggleBtn());
    await wait(300, m.fixture);
    const snap = {
      control: m.toggle().checked(),
      model: m.host.model().newsletter,
      dirty: m.host.f.newsletter().dirty(),
    };
    log('checkbox-even-clicks', snap);
    expect(snap).toEqual({ control: false, model: false, dirty: true });
  });

  it('trzy kliknięcia w oknie: jeden zapis z ostatnią wartością', async () => {
    const m = mount();
    m.click(m.toggleBtn());
    await wait(100, m.fixture);
    m.click(m.toggleBtn());
    await wait(100, m.fixture);
    m.click(m.toggleBtn());
    const before = m.host.model().newsletter;
    await wait(299, m.fixture);
    const mid = m.host.model().newsletter;
    await wait(1, m.fixture);
    const after = m.host.model().newsletter;
    log('checkbox-three-clicks', { before, mid, after });
    expect({ before, mid, after }).toEqual({ before: false, mid: false, after: true });
  });

  it('natywny <input type=checkbox>: czy debounce(300) działa i kiedy touched', async () => {
    TestBed.configureTestingModule({ imports: [NativeCheckboxHost] });
    const fx = TestBed.createComponent(NativeCheckboxHost);
    fx.detectChanges();
    const el = fx.nativeElement.querySelector('#n') as HTMLInputElement;
    el.click();
    fx.detectChanges();
    const immediately = {
      domChecked: el.checked,
      model: fx.componentInstance.model().newsletter,
      touched: fx.componentInstance.f.newsletter().touched(),
      dirty: fx.componentInstance.f.newsletter().dirty(),
    };
    await wait(300, fx);
    const after300 = fx.componentInstance.model().newsletter;
    log('native-checkbox', { immediately, after300 });
    expect(immediately).toEqual({ domChecked: true, model: false, touched: false, dirty: true });
    expect(after300).toBe(true);
  });

  it('własny checkbox z debounce(blur): klik nie zapisuje, blur zapisuje', async () => {
    TestBed.configureTestingModule({ imports: [BlurToggleHost] });
    const fx = TestBed.createComponent(BlurToggleHost);
    fx.detectChanges();
    const btn = fx.nativeElement.querySelector('button') as HTMLButtonElement;
    btn.click();
    fx.detectChanges();
    await wait(5000, fx);
    const afterClick = fx.componentInstance.model().newsletter;
    btn.dispatchEvent(new FocusEvent('blur'));
    fx.detectChanges();
    const snap = {
      afterClick5s: afterClick,
      afterBlur: fx.componentInstance.model().newsletter,
      touched: fx.componentInstance.f.newsletter().touched(),
    };
    log('checkbox-blur', snap);
    expect(snap).toEqual({ afterClick5s: false, afterBlur: true, touched: true });
  });

  it('reset() kontrolki jest podpinany (FormField.reset)', () => {
    const m = mount();
    const ff = m.fixture.debugElement.query(By.directive(ConsentToggle)).injector.get(FormField);
    ff.reset();
    log('checkbox-reset', { resetCalls: m.toggle().resetCalls });
    expect(m.toggle().resetCalls).toBe(1);
  });
});

describe('ControlValueAccessor pod [formField]', () => {
  beforeEach(() => vi.useFakeTimers());
  afterEach(() => vi.useRealTimers());

  it('cykl życia: jakie metody CVA wołane są przy montowaniu', () => {
    const m = mount();
    log('cva-mount', m.stars().calls);
    expect(m.stars().calls).toEqual([
      'registerOnChange',
      'registerOnTouched',
      'writeValue(0)',
      'setDisabledState(false)',
    ]);
  });

  it('pick() z debounce(blur): model stoi, writeValue nie jest wołane echem; blur -> onTouched -> zapis', async () => {
    const m = mount();
    m.click(m.starBtn(4));
    await wait(5000, m.fixture);
    const during = {
      current: m.stars().current(),
      model: m.host.model().rating,
      touched: m.host.f.rating().touched(),
      dirty: m.host.f.rating().dirty(),
      errors: m.host.f.rating().errors().map((e) => e.kind),
      calls: [...m.stars().calls],
    };
    m.blur(m.starBtn(4));
    const afterBlur = {
      model: m.host.model().rating,
      touched: m.host.f.rating().touched(),
      errors: m.host.f.rating().errors().map((e) => e.kind),
      calls: [...m.stars().calls],
    };
    log('cva-pick-blur', { during, afterBlur });
    expect(during).toMatchObject({ current: 4, model: 0, touched: false, dirty: true, errors: ['min'] });
    expect(afterBlur).toMatchObject({ model: 4, touched: true, errors: [] });
    // brak "echa": zmiana z UI nie wraca do kontrolki przez writeValue
    expect(afterBlur.calls).toEqual(during.calls);
    expect(afterBlur.calls.filter((c) => c.startsWith('writeValue'))).toEqual(['writeValue(0)']);
  });

  it('zapis programowy do modelu -> writeValue', async () => {
    const m = mount();
    m.host.f.rating().value.set(2);
    m.fixture.detectChanges();
    await wait(0, m.fixture);
    log('cva-programmatic', { current: m.stars().current(), calls: m.stars().calls });
    expect(m.stars().current()).toBe(2);
    expect(m.stars().calls.at(-1)).toBe('writeValue(2)');
  });

  it('FormField.reset() w trakcie oczekującego wpisu NIE anuluje wpisu (blur po resecie go zapisuje)', async () => {
    const m = mount();
    m.click(m.starBtn(5));
    const ff = m.fixture.debugElement.query(By.directive(StarRating)).injector.get(FormField);
    ff.reset();
    m.fixture.detectChanges();
    await wait(0, m.fixture);
    const afterReset = { current: m.stars().current(), model: m.host.model().rating, last: m.stars().calls.at(-1) };
    // co z wpisem, który czekał na blur? czy "wskrzeszony" blurem po resecie?
    m.blur(m.starBtn(5));
    await wait(0, m.fixture);
    const afterBlur = { current: m.stars().current(), model: m.host.model().rating };
    log('cva-reset', { afterReset, afterBlur });
    expect(afterReset).toEqual({ current: 0, model: 0, last: 'writeValue(0)' });
    // PUŁAPKA: reset() cofnął UI, ale NIE anulował oczekującego wpisu - blur "wskrzesza" 5
    expect(afterBlur).toEqual({ current: 5, model: 5 });
  });

  it('disabled -> setDisabledState, readonly -> tylko input()', async () => {
    const m = mount();
    m.setMode('locked');
    await wait(0, m.fixture);
    const locked = {
      isDisabled: m.stars().isDisabled(),
      readonlyInput: m.stars().readonly(),
      disabledBtn: m.starBtn(1).disabled,
      calls: [...m.stars().calls],
    };
    m.setMode('readonly');
    await wait(0, m.fixture);
    const ro = {
      isDisabled: m.stars().isDisabled(),
      readonlyInput: m.stars().readonly(),
      calls: [...m.stars().calls],
    };
    log('cva-disabled-readonly', { locked, ro });
    expect(locked).toMatchObject({ isDisabled: true, readonlyInput: false, disabledBtn: true });
    expect(locked.calls.at(-1)).toBe('setDisabledState(true)');
    expect(ro).toMatchObject({ isDisabled: false, readonlyInput: true });
    // readonly nie ma odpowiednika w CVA: żadnego wywołania "setReadonlyState"
    expect(ro.calls.at(-1)).toBe('setDisabledState(false)');
  });

  it('stary walidator NG_VALIDATORS + reguła schematu na jednym polu', async () => {
    const m = mount();
    const kinds = () => m.host.f.rating().errors().map((e) => e.kind);
    const r0 = kinds();
    m.click(m.starBtn(2));
    m.blur(m.starBtn(2));
    await wait(0, m.fixture);
    const r2 = kinds();
    m.click(m.starBtn(4));
    m.blur(m.starBtn(4));
    await wait(0, m.fixture);
    const r4 = kinds();
    log('cva-validators', { r0, r2, r4, valid: m.host.f.rating().valid() });
    expect(r0).toEqual(['minStars', 'min']);
    expect(r2).toEqual(['minStars']);
    expect(r4).toEqual([]);
    expect(m.host.f.rating().valid()).toBe(true);
  });

  it('sam stary walidator (bez schematu)', async () => {
    TestBed.configureTestingModule({ imports: [ValidatorHost] });
    const fx = TestBed.createComponent(ValidatorHost);
    fx.detectChanges();
    const err = fx.componentInstance.f.rating().errors();
    log('cva-validator-only', err.map((e) => ({ kind: e.kind, keys: Object.keys(e) })));
    expect(err.map((e) => e.kind)).toEqual(['minStars']);
  });

  it('kontrolka z CVA i FormValueControl naraz: która ścieżka wygrywa', async () => {
    TestBed.configureTestingModule({ imports: [DualHost] });
    const fx = TestBed.createComponent(DualHost);
    fx.detectChanges();
    fx.componentInstance.f.rating().value.set(3);
    fx.detectChanges();
    await wait(0, fx);
    const dual = fx.debugElement.query(By.directive(DualRating)).componentInstance as DualRating;
    log('cva-vs-value', { calls: dual.calls, valueModel: dual.value() });
    expect(dual.calls.at(-1)).toBe('writeValue(3)');
    expect(dual.value()).toBe(0); // ścieżka FormValueControl jest ignorowana
  });

  it('CVA wygrywa też z outputem touch: debounce(blur) nie domyka się przez touch.emit()', async () => {
    TestBed.configureTestingModule({ imports: [DualBlurHost] });
    const fx = TestBed.createComponent(DualBlurHost);
    fx.detectChanges();
    const dual = fx.debugElement.query(By.directive(DualRating)).componentInstance as DualRating;
    // symulacja wpisu użytkownika przez ścieżkę value (tej, którą dyrektywa ignoruje)
    dual.value.set(4);
    fx.detectChanges();
    dual.touch.emit();
    fx.detectChanges();
    await wait(5000, fx);
    const snap = { model: fx.componentInstance.model().rating, touched: fx.componentInstance.f.rating().touched() };
    log('cva-vs-touch', snap);
    expect(snap).toEqual({ model: 0, touched: false });
  });

  it('zniszczenie kontrolki CVA z oczekującym wpisem', async () => {
    TestBed.configureTestingModule({ imports: [CvaIfHost] });
    const fx = TestBed.createComponent(CvaIfHost);
    fx.detectChanges();
    const btn = fx.nativeElement.querySelectorAll('button')[2] as HTMLButtonElement;
    btn.click();
    fx.detectChanges();
    const before = fx.componentInstance.model().rating;
    fx.componentInstance.visible.set(false);
    fx.detectChanges();
    await wait(0, fx);
    const after = fx.componentInstance.model().rating;
    log('cva-destroy', { before, after });
    expect({ before, after }).toEqual({ before: 0, after: 3 });
  });
});
