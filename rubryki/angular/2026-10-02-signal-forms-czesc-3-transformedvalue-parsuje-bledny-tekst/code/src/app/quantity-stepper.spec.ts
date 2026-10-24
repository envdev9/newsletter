import { ComponentFixture, TestBed } from '@angular/core/testing';
import { beforeEach, describe, expect, it, vi } from 'vitest';
import { QuantityStepper } from './quantity-stepper';

describe('QuantityStepper (własny FormValueControl<number>, bez Signal Forms)', () => {
  let fixture: ComponentFixture<QuantityStepper>;
  let component: QuantityStepper;
  let el: HTMLElement;

  function click(index: 0 | 1): void {
    (el.querySelectorAll('.step-btn')[index] as HTMLButtonElement).click();
    fixture.detectChanges();
  }

  beforeEach(() => {
    TestBed.configureTestingModule({});
    fixture = TestBed.createComponent(QuantityStepper);
    component = fixture.componentInstance;
    fixture.componentRef.setInput('value', 5);
    fixture.componentRef.setInput('min', 1);
    fixture.componentRef.setInput('max', 7);
    el = fixture.nativeElement;
    document.body.appendChild(el);
    fixture.detectChanges();
  });

  it('renderuje przekazaną wartość', () => {
    expect(el.querySelector('.qty-value')?.textContent?.trim()).toBe('5');
  });

  it('"+" (index 1) zwiększa wartość aż do max, potem się blokuje', () => {
    click(1); // 6
    click(1); // 7
    expect(component.value()).toBe(7);
    expect(el.querySelectorAll('.step-btn')[1].hasAttribute('disabled')).toBe(true);
    click(1); // no-op - przycisk zablokowany
    expect(component.value()).toBe(7);
  });

  it('"-" (index 0) zmniejsza wartość aż do min, potem się blokuje', () => {
    click(0); // 4
    click(0); // 3
    click(0); // 2
    click(0); // 1
    expect(component.value()).toBe(1);
    expect(el.querySelectorAll('.step-btn')[0].hasAttribute('disabled')).toBe(true);
    click(0); // no-op
    expect(component.value()).toBe(1);
  });

  it('disabled=true blokuje oba przyciski niezależnie od min/max', () => {
    fixture.componentRef.setInput('disabled', true);
    fixture.detectChanges();
    const buttons = el.querySelectorAll('.step-btn');
    expect(buttons[0].hasAttribute('disabled')).toBe(true);
    expect(buttons[1].hasAttribute('disabled')).toBe(true);
  });

  it('każde kliknięcie +/- emituje `touch` (brak natywnego blur na przyciskach)', () => {
    const touchSpy = vi.fn();
    component.touch.subscribe(touchSpy);
    click(1);
    expect(touchSpy).toHaveBeenCalledTimes(1);
    click(0);
    expect(touchSpy).toHaveBeenCalledTimes(2);
  });

  it('`errors` (input z zewnątrz) renderuje się WEWNĄTRZ komponentu', () => {
    fixture.componentRef.setInput('errors', [{ kind: 'max', message: 'Ilość nie może przekraczać 99' }]);
    fixture.detectChanges();
    expect(el.textContent).toContain('Ilość nie może przekraczać 99');
  });

  it('`touched` (input z zewnątrz) dokłada klasę stylującą', () => {
    expect(el.querySelector('.stepper')?.classList.contains('is-touched')).toBe(false);
    fixture.componentRef.setInput('touched', true);
    fixture.detectChanges();
    expect(el.querySelector('.stepper')?.classList.contains('is-touched')).toBe(true);
  });

  it('focus() fokusuje przycisk "+" i liczy wywołania', () => {
    const incBtn = el.querySelectorAll('.step-btn')[1] as HTMLButtonElement;
    expect(document.activeElement).not.toBe(incBtn);
    component.focus();
    expect(document.activeElement).toBe(incBtn);
    expect(component['focusCallCount']()).toBe(1);
  });

  it('reset() jest faktycznie wywoływalny (dowód przez licznik)', () => {
    expect(component['resetCallCount']()).toBe(0);
    component.reset();
    expect(component['resetCallCount']()).toBe(1);
  });
});
