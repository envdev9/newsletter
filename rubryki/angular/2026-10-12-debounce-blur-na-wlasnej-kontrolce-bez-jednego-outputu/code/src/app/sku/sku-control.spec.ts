import { Component, signal } from '@angular/core';
import { ComponentFixture, TestBed } from '@angular/core/testing';
import { By } from '@angular/platform-browser';
import { FormField, form, submit } from '@angular/forms/signals';
import { NoTouchSkuInput, SkuInput } from './sku-input';
import { LOCK_REASON, SkuModel, emptySku, skuSchema } from './sku.schema';
import { SkuForm } from './sku-form';

/** Host z kontrolką BEZ outputu `touch` oraz natywnym <input> dla porównania. */
@Component({
  selector: 'app-host',
  imports: [FormField, NoTouchSkuInput],
  template: `
    @if (visible()) {
      <app-no-touch-sku-input [formField]="f.sku" />
    }
  `,
})
class NoTouchHost {
  readonly model = signal<SkuModel>(emptySku());
  readonly f = form(this.model, skuSchema);
  readonly visible = signal(true);
}

@Component({
  selector: 'app-native-host',
  imports: [FormField],
  template: `<input id="n" type="text" [formField]="f.sku" />`,
})
class NativeHost {
  readonly model = signal<SkuModel>(emptySku());
  readonly f = form(this.model, skuSchema);
}

/** Pole hidden RENDEROWANE bez @if - łamie zalecenie z JSDoc `hidden()`. */
@Component({
  selector: 'app-unguarded-host',
  imports: [FormField, SkuInput],
  template: `<app-sku-input [formField]="f.sku" />`,
})
class UnguardedHost {
  readonly model = signal<SkuModel>({ sku: '', mode: 'hidden' });
  readonly f = form(this.model, skuSchema);
}

function mount() {
  TestBed.configureTestingModule({ imports: [SkuForm] });
  const fixture: ComponentFixture<SkuForm> = TestBed.createComponent(SkuForm);
  fixture.detectChanges();
  const host = fixture.componentInstance;
  const root = fixture.nativeElement as HTMLElement;
  const inner = () => root.querySelector('app-sku-input input') as HTMLInputElement;
  const control = () => fixture.debugElement.query(By.directive(SkuInput))?.componentInstance as SkuInput;
  const type = (v: string) => {
    const el = inner();
    el.value = v;
    el.dispatchEvent(new Event('input'));
    fixture.detectChanges();
  };
  const blur = () => {
    inner().dispatchEvent(new FocusEvent('blur'));
    fixture.detectChanges();
  };
  const enter = () => {
    inner().dispatchEvent(new KeyboardEvent('keydown', { key: 'Enter' }));
    fixture.detectChanges();
  };
  const setMode = (m: Parameters<SkuForm['setMode']>[0]) => {
    host.setMode(m);
    fixture.detectChanges();
  };
  return { fixture, host, root, inner, control, type, blur, enter, setMode };
}

const log = (label: string, value: unknown) =>
  console.log(`MEASURE ${label}: ${JSON.stringify(value)}`);

describe('debounce("blur") na własnej kontrolce FormValueControl', () => {
  it('kontrakt: wszystkie opcjonalne pola są zasilane automatycznie (stan początkowy, tryb edit)', () => {
    const m = mount();
    const c = m.control();
    const snapshot = {
      value: c.value(),
      required: c.required(),
      pattern: c.pattern().map((r) => String(r)),
      minLength: c.minLength(),
      maxLength: c.maxLength(),
      name: c.name(),
      disabled: c.disabled(),
      disabledReasons: c.disabledReasons().length,
      readonly: c.readonly(),
      hidden: c.hidden(),
      invalid: c.invalid(),
      pending: c.pending(),
      touched: c.touched(),
      dirty: c.dirty(),
      errors: c.errors().map((e) => e.kind),
    };
    log('contract-initial', snapshot);
    expect(snapshot.required).toBe(true);
    expect(snapshot.pattern).toEqual(['/^[A-Z]{3}-\\d{4}$/']);
    expect(snapshot.maxLength).toBe(8);
    expect(snapshot.minLength).toBeUndefined();
    expect(snapshot.name).toMatch(/\.form\d+\.sku$/);
    expect(snapshot.invalid).toBe(true);
    expect(snapshot.errors).toEqual(['required']);
  });

  it('natywny <input> dostaje required/maxLength/name jako własności DOM, a custom host NIE', () => {
    TestBed.configureTestingModule({ imports: [NativeHost, SkuForm] });
    const nf = TestBed.createComponent(NativeHost);
    nf.detectChanges();
    const n = nf.nativeElement.querySelector('#n') as HTMLInputElement;
    const nativeProps = {
      required: n.required,
      maxLength: n.maxLength,
      name: n.name,
      pattern: n.pattern,
      disabled: n.disabled,
      readOnly: n.readOnly,
      hidden: n.hidden,
    };
    log('native-input-dom', nativeProps);
    expect(nativeProps.required).toBe(true);
    expect(nativeProps.maxLength).toBe(8);
    expect(nativeProps.name).toMatch(/\.sku$/);
    expect(nativeProps.pattern).toBe('');

    const sf = TestBed.createComponent(SkuForm);
    sf.detectChanges();
    const hostEl = sf.nativeElement.querySelector('app-sku-input') as HTMLElement;
    const customHost = {
      requiredAttr: hostEl.hasAttribute('required'),
      nameAttr: hostEl.hasAttribute('name'),
      maxlengthAttr: hostEl.hasAttribute('maxlength'),
    };
    log('custom-host-dom', customHost);
    expect(customHost).toEqual({ requiredAttr: false, nameAttr: false, maxlengthAttr: false });
  });

  it('debounce("blur"): model stoi w miejscu, kontrolka i dirty reagują, a błąd "required" jest NIEAKTUALNY', () => {
    const m = mount();
    m.type('abc-1234');
    const during = {
      innerText: m.inner().value,
      controlValue: m.control().value(),
      model: m.host.model().sku,
      dirty: m.host.skuForm.sku().dirty(),
      touched: m.host.skuForm.sku().touched(),
      errors: m.host.skuForm.sku().errors().map((e) => e.kind),
    };
    log('during-typing', during);
    expect(during).toEqual({
      innerText: 'abc-1234',
      controlValue: 'abc-1234',
      model: '',
      dirty: true,
      touched: false,
      errors: ['required'],
    });
    m.blur();
    const after = {
      model: m.host.model().sku,
      touched: m.host.skuForm.sku().touched(),
      errors: m.host.skuForm.sku().errors().map((e) => e.kind),
    };
    log('after-blur', after);
    expect(after).toEqual({ model: 'abc-1234', touched: true, errors: ['pattern'] });
  });

  it('kontrolka BEZ outputu touch: model nie zapisze się po blurze, nigdy', async () => {
    TestBed.configureTestingModule({ imports: [NoTouchHost] });
    const fx = TestBed.createComponent(NoTouchHost);
    fx.detectChanges();
    const el = fx.nativeElement.querySelector('input') as HTMLInputElement;
    el.value = 'ABC-1234';
    el.dispatchEvent(new Event('input'));
    el.dispatchEvent(new FocusEvent('blur'));
    fx.detectChanges();
    await fx.whenStable();
    await new Promise((r) => setTimeout(r, 1000));
    fx.detectChanges();
    const res = {
      model: fx.componentInstance.model().sku,
      touched: fx.componentInstance.f.sku().touched(),
      dirty: fx.componentInstance.f.sku().dirty(),
    };
    log('no-touch-after-1s', res);
    expect(res).toEqual({ model: '', touched: false, dirty: true });
  });

  it('zniszczenie kontrolki z oczekującym wpisem DOMYKA go (flushSync w cleanup bindingu)', async () => {
    TestBed.configureTestingModule({ imports: [NoTouchHost] });
    const fx = TestBed.createComponent(NoTouchHost);
    fx.detectChanges();
    const el = fx.nativeElement.querySelector('input') as HTMLInputElement;
    el.value = 'ABC-1234';
    el.dispatchEvent(new Event('input'));
    fx.detectChanges();
    const before = fx.componentInstance.model().sku;
    fx.componentInstance.visible.set(false);
    fx.detectChanges();
    await fx.whenStable();
    const after = fx.componentInstance.model().sku;
    log('destroy-flush', { before, after });
    expect(before).toBe('');
    expect(after).toBe('ABC-1234');
  });

  it('Enter emitujący touch domyka wpis, więc submit() widzi aktualny model (pułapka z #15 obejściem)', async () => {
    const m = mount();
    m.type('ABC-1234');
    expect(m.host.model().sku).toBe('');
    m.enter();
    expect(m.host.model().sku).toBe('ABC-1234');
    const ok = await submit(m.host.skuForm, async () => {
      m.host.submitCalls.push(m.host.model().sku);
    });
    log('enter-then-submit', { ok, calls: m.host.submitCalls });
    expect(ok).toBe(true);
    expect(m.host.submitCalls).toEqual(['ABC-1234']);
  });

  it('bez Entera/blura: submit() z kodu waliduje stary model i nie odpala akcji', async () => {
    const m = mount();
    m.type('ABC-1234');
    const ok = await submit(m.host.skuForm, async () => {
      m.host.submitCalls.push('NIE POWINNO SIĘ ODPALIĆ');
    });
    log('submit-without-flush', { ok, calls: m.host.submitCalls, model: m.host.model().sku });
    expect(m.host.submitCalls).toEqual([]);
    expect(m.host.model().sku).toBe('');
  });

  it('disabled: disabledReasons i disabled docierają do kontrolki, a walidacja jest pomijana', () => {
    const m = mount();
    expect(m.host.skuForm.sku().errors().map((e) => e.kind)).toEqual(['required']);
    m.setMode('locked');
    const c = m.control();
    const res = {
      disabled: c.disabled(),
      reasons: c.disabledReasons().map((r) => r.message),
      innerDisabled: m.inner().disabled,
      errors: c.errors().length,
      invalid: c.invalid(),
      valid: m.host.skuForm.sku().valid(),
      reasonText: (m.root.querySelector('app-sku-input small') as HTMLElement).textContent,
    };
    log('mode-locked', res);
    expect(res.disabled).toBe(true);
    expect(res.reasons).toEqual([LOCK_REASON]);
    expect(res.errors).toBe(0);
    expect(res.invalid).toBe(false);
    expect(res.innerDisabled).toBe(true);
  });

  it('readonly też pomija walidację i zeruje touched/dirty (tylko readonly: true w kontrolce)', () => {
    const m = mount();
    m.type('abc');
    m.blur();
    const before = {
      touched: m.control().touched(),
      dirty: m.control().dirty(),
      errors: m.control().errors().map((e) => e.kind),
    };
    m.setMode('readonly');
    const c = m.control();
    const during = {
      readonly: c.readonly(),
      disabled: c.disabled(),
      touched: c.touched(),
      dirty: c.dirty(),
      errors: c.errors().length,
      innerReadOnly: m.inner().readOnly,
    };
    m.setMode('edit');
    const back = {
      touched: m.control().touched(),
      dirty: m.control().dirty(),
      errors: m.control().errors().map((e) => e.kind),
    };
    log('mode-readonly', { before, during, back });
    expect(before).toEqual({ touched: true, dirty: true, errors: ['pattern'] });
    expect(during).toEqual({
      readonly: true,
      disabled: false,
      touched: false,
      dirty: false,
      errors: 0,
      innerReadOnly: true,
    });
    expect(back).toEqual(before);
  });

  it('hidden: pole bez walidacji i submit() przechodzi mimo pustego, wymaganego SKU', async () => {
    const m = mount();
    const visibleOk = await submit(m.host.skuForm, async () => {});
    m.setMode('hidden');
    const rendered = !!m.root.querySelector('app-sku-input');
    const hiddenOk = await submit(m.host.skuForm, async () => {
      m.host.submitCalls.push(`'${m.host.model().sku}'`);
    });
    log('mode-hidden', { visibleOk, rendered, hiddenOk, calls: m.host.submitCalls });
    expect(visibleOk).toBe(false);
    expect(rendered).toBe(false);
    expect(hiddenOk).toBe(true);
    expect(m.host.submitCalls).toEqual(["''"]);
  });

  it('hidden bez @if: kontrolka dostaje hidden=true i NIE znika, a dev-mode ostrzega w konsoli', () => {
    const warn = vi.spyOn(console, 'warn').mockImplementation(() => {});
    TestBed.configureTestingModule({ imports: [UnguardedHost] });
    const fx = TestBed.createComponent(UnguardedHost);
    fx.detectChanges();
    const c = fx.debugElement.query(By.directive(SkuInput)).componentInstance as SkuInput;
    const inDom = !!fx.nativeElement.querySelector('app-sku-input input');
    const warnings = warn.mock.calls.map((a) => String(a[0]).slice(0, 110));
    warn.mockRestore();
    log('hidden-unguarded', { controlHidden: c.hidden(), inDom, warnings });
    expect(c.hidden()).toBe(true);
    expect(inDom).toBe(true);
    expect(warnings.length).toBe(1);
    expect(warnings[0]).toContain('is hidden but is being rendered');
  });

  it('oczekujący wpis + zmiana trybu na locked + blur: co trafia do modelu', () => {
    const m = mount();
    m.type('ABC-1234');
    m.setMode('locked');
    m.blur();
    const res = { model: m.host.model().sku, touchedState: m.host.skuForm.sku().touched() };
    log('pending-then-locked-then-blur', res);
    // Zapis jest wykonywany mimo disabled (debounce tego nie sprawdza) - dokumentujemy zmierzone zachowanie.
    expect(res.model).toBe('ABC-1234');
    expect(res.touchedState).toBe(false);
  });
});
