import { ComponentFixture, TestBed } from '@angular/core/testing';
import { beforeEach, describe, expect, it, vi } from 'vitest';
import { PriceInput } from './price-input';

describe('PriceInput (własny FormValueControl<number> z transformedValue(), bez Signal Forms)', () => {
  let fixture: ComponentFixture<PriceInput>;
  let component: PriceInput;
  let el: HTMLElement;
  let input: HTMLInputElement;

  function typeRaw(raw: string): void {
    input.value = raw;
    input.dispatchEvent(new Event('input'));
    fixture.detectChanges();
  }

  beforeEach(() => {
    TestBed.configureTestingModule({});
    fixture = TestBed.createComponent(PriceInput);
    component = fixture.componentInstance;
    fixture.componentRef.setInput('value', 12.5);
    el = fixture.nativeElement;
    document.body.appendChild(el);
    fixture.detectChanges();
    input = el.querySelector('.price-native') as HTMLInputElement;
  });

  it('renderuje wartość początkową sformatowaną po polsku (przecinek, 2 miejsca)', () => {
    expect(input.value).toBe('12,50');
  });

  it('poprawny tekst z przecinkiem aktualizuje model na liczbę', () => {
    typeRaw('7,25');
    expect(component.value()).toBe(7.25);
  });

  it('błędny tekst NIE psuje modelu - zgłasza parseError zamiast wyjątku', () => {
    typeRaw('abc');
    expect(component.value()).toBe(12.5); // model bez zmian
    const parseErrors = component['rawValue'].parseErrors();
    expect(parseErrors.length).toBe(1);
    expect(parseErrors[0].kind).toBe('price-parse');
    expect(input.value).toBe('abc'); // to co user wpisał zostaje widoczne, nie jest nadpisywane
  });

  it('ujemna cena to osobny rodzaj błędu parsowania ("price-negative")', () => {
    typeRaw('-5');
    expect(component.value()).toBe(12.5);
    expect(component['rawValue'].parseErrors()[0].kind).toBe('price-negative');
  });

  it('pusty tekst to błąd "price-required"', () => {
    typeRaw('');
    expect(component['rawValue'].parseErrors()[0].kind).toBe('price-required');
  });

  it('`errors` (input z zewnątrz - symulacja Signal Forms) renderuje się WEWNĄTRZ komponentu', () => {
    fixture.componentRef.setInput('errors', [{ kind: 'min', message: 'Cena musi być większa od zera' }]);
    fixture.detectChanges();
    expect(el.textContent).toContain('Cena musi być większa od zera');
    expect(el.querySelector('.price-field')?.classList.contains('has-error')).toBe(true);
  });

  it('`touched` (input z zewnątrz) dokłada klasę stylującą obramowanie', () => {
    expect(el.querySelector('.price-field')?.classList.contains('is-touched')).toBe(false);
    fixture.componentRef.setInput('touched', true);
    fixture.detectChanges();
    expect(el.querySelector('.price-field')?.classList.contains('is-touched')).toBe(true);
  });

  it('`blur` emituje `touch` (wyjście) - tak Signal Forms dowiaduje się, że pole dotknięte', () => {
    const touchSpy = vi.fn();
    component.touch.subscribe(touchSpy);
    input.dispatchEvent(new Event('blur'));
    expect(touchSpy).toHaveBeenCalledTimes(1);
  });

  it('focus() fokusuje natywny <input> w środku i liczy wywołania', () => {
    expect(document.activeElement).not.toBe(input);
    component.focus();
    expect(document.activeElement).toBe(input);
    expect(component['focusCallCount']()).toBe(1);
  });

  it('reset() jest faktycznie wywoływalny (dowód przez licznik - Signal Forms woła go z zewnątrz)', () => {
    expect(component['resetCallCount']()).toBe(0);
    component.reset();
    expect(component['resetCallCount']()).toBe(1);
  });
});
