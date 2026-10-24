import { ComponentFixture, TestBed } from '@angular/core/testing';
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';
import { OrderForm } from './order-form';

describe('OrderForm (applyEach + reużywalna schema + własny FormValueControl)', () => {
  let fixture: ComponentFixture<OrderForm>;
  let component: OrderForm;
  let el: HTMLElement;

  // Ten sam wzorzec "settle" co w poprzednich wydaniach (rejestracja pending tasków resource()/
  // formularza) - fixture.detectChanges() + odpalenie kolejki mikrotasków + ponowny detectChanges.
  async function settle(): Promise<void> {
    fixture.detectChanges();
    await vi.advanceTimersByTimeAsync(0);
    fixture.detectChanges();
  }

  function rows(): NodeListOf<HTMLTableRowElement> {
    return el.querySelectorAll('.item-row');
  }

  function setText(input: Element, value: string): void {
    (input as HTMLInputElement).value = value;
    input.dispatchEvent(new Event('input'));
  }

  function stepperButtons(rowIndex: number): NodeListOf<HTMLButtonElement> {
    return rows()[rowIndex].querySelectorAll('.step-btn');
  }

  function submitForm(): void {
    el.querySelector('form')!.dispatchEvent(new Event('submit', { cancelable: true }));
  }

  beforeEach(() => {
    vi.useFakeTimers();
    TestBed.configureTestingModule({});
    fixture = TestBed.createComponent(OrderForm);
    component = fixture.componentInstance;
    el = fixture.nativeElement;
    fixture.detectChanges();
  });

  afterEach(() => {
    vi.useRealTimers();
  });

  it('na starcie: jedna pozycja, submit zablokowany, wymagane pola zgłaszają błąd', async () => {
    await settle();
    expect(rows().length).toBe(1);
    expect(el.querySelector('button[type="submit"]')?.hasAttribute('disabled')).toBe(true);
    expect(el.textContent).toContain('Nazwa klienta jest wymagana');
    expect(el.textContent).toContain('Nazwa produktu jest wymagana');
  });

  it('"+ dodaj pozycję" dodaje kolejny wiersz z własnym stepperem od wartości 1', async () => {
    (el.querySelector('.add-item') as HTMLButtonElement).click();
    await settle();
    expect(rows().length).toBe(2);
    expect(rows()[1].querySelector('.qty-value')?.textContent?.trim()).toBe('1');
  });

  it('"Usuń" usuwa wiersz, ale nie pozwala zejść poniżej jednej pozycji', async () => {
    (el.querySelector('.add-item') as HTMLButtonElement).click();
    await settle();
    expect(rows().length).toBe(2);

    (rows()[1].querySelector('.remove-item') as HTMLButtonElement).click();
    await settle();
    expect(rows().length).toBe(1);
    expect(rows()[0].querySelector('.remove-item')?.hasAttribute('disabled')).toBe(true);
  });

  it('reużywalna lineItemSchema waliduje każdy wiersz NIEZALEŻNIE (applyEach)', async () => {
    (el.querySelector('.add-item') as HTMLButtonElement).click();
    await settle();

    setText(rows()[0].querySelector('input[type="text"]')!, 'Kabel USB-C');
    await settle();

    // Wiersz 0 ma nazwę - błąd znika. Wiersz 1 nadal pusty - błąd zostaje.
    expect(rows()[0].textContent).not.toContain('Nazwa produktu jest wymagana');
    expect(rows()[1].textContent).toContain('Nazwa produktu jest wymagana');
  });

  it('quantity stepper: "+"/"-" realnie edytują ilość przez własny FormValueControl', async () => {
    await settle();
    expect(rows()[0].querySelector('.qty-value')?.textContent?.trim()).toBe('1');

    stepperButtons(0)[1].click(); // +
    fixture.detectChanges();
    stepperButtons(0)[1].click(); // +
    fixture.detectChanges();
    await settle();

    expect(rows()[0].querySelector('.qty-value')?.textContent?.trim()).toBe('3');
  });

  it('min/max steppera pochodzą automatycznie z walidatorów min()/max() schemy (bez ręcznego wiązania)', async () => {
    await settle();
    // quantity startuje od 1, a schema ma min(1) - przycisk "-" jest zablokowany OD RAZU,
    // mimo że w order-form.ts nikt nie ustawia [min] ręcznie na <app-quantity-stepper>.
    expect(stepperButtons(0)[0].hasAttribute('disabled')).toBe(true);
    expect(stepperButtons(0)[1].hasAttribute('disabled')).toBe(false);

    // Analogicznie górna granica: schema ma max(99) - ustawiamy ilość blisko granicy przez
    // FieldState.value.set (ten sam mechanizm, którego używa [formField] pod spodem).
    (component as unknown as { orderForm: any }).orderForm.items[0].quantity().value.set(99);
    await settle();
    expect(stepperButtons(0)[1].hasAttribute('disabled')).toBe(true);
    expect(rows()[0].textContent).not.toContain('Ilość nie może przekraczać 99');

    (component as unknown as { orderForm: any }).orderForm.items[0].quantity().value.set(100);
    await settle();
    expect(rows()[0].textContent).toContain('Ilość nie może przekraczać 99');
  });

  it('poprawne zamówienie: submit kończy się sukcesem po odpowiedzi fake-backendu (300ms)', async () => {
    setText(el.querySelector('#customerName')!, 'Jan Kowalski');
    setText(rows()[0].querySelector('input[type="text"]')!, 'Kabel USB-C');
    await settle();

    expect(el.querySelector('button[type="submit"]')?.hasAttribute('disabled')).toBe(false);
    submitForm();
    await settle();
    expect(el.textContent).toContain('Wysyłanie…');

    await vi.advanceTimersByTimeAsync(300);
    await settle();
    expect(el.textContent).toContain('Zamówienie przyjęte (1× wywołano backend)');
  });

  it('współbieżny submit: drugie kliknięcie w trakcie wysyłki NIE wywołuje backendu ponownie', async () => {
    setText(el.querySelector('#customerName')!, 'Jan Kowalski');
    setText(rows()[0].querySelector('input[type="text"]')!, 'Kabel USB-C');
    await settle();

    submitForm(); // pierwszy submit rusza (300ms w toku)
    await settle();
    submitForm(); // drugi submit - musi zostać odrzucony NATYCHMIAST przez Signal Forms
    await settle();

    await vi.advanceTimersByTimeAsync(300);
    await settle();

    expect(el.textContent).toContain('Zamówienie przyjęte (1× wywołano backend)');
    expect(component['submitCallCount']()).toBe(1);
  });
});
