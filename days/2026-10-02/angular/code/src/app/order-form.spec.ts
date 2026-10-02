import { ComponentFixture, TestBed } from '@angular/core/testing';
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';
import { OrderForm } from './order-form';

describe('OrderForm (transformedValue() + pełny FormUiControl na własnych kontrolkach)', () => {
  let fixture: ComponentFixture<OrderForm>;
  let component: OrderForm;
  let el: HTMLElement;

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

  function priceInput(rowIndex: number): HTMLInputElement {
    return rows()[rowIndex].querySelector('.price-native') as HTMLInputElement;
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
    document.body.appendChild(el);
    fixture.detectChanges();
  });

  afterEach(() => {
    vi.useRealTimers();
  });

  it('na starcie: cena 0,00 ma błąd schematu ("większa od zera"), submit zablokowany', async () => {
    await settle();
    expect(priceInput(0).value).toBe('0,00');
    expect(rows()[0].textContent).toContain('Cena musi być większa od zera');
    expect(el.querySelector('button[type="submit"]')?.hasAttribute('disabled')).toBe(true);
  });

  it('błędny tekst ceny ("abc") pokazuje błąd PARSOWANIA obok błędu SCHEMATU jednocześnie', async () => {
    await settle();
    setText(priceInput(0), 'abc');
    await settle();
    // Oba źródła błędów na tym samym polu, naraz: parser (transformedValue) + schema (min()).
    expect(rows()[0].textContent).toContain('nie jest poprawną ceną');
    expect(rows()[0].textContent).toContain('Cena musi być większa od zera');
  });

  it('poprawna cena z przecinkiem aktualizuje model i czyści oba błędy, wartość wiersza się liczy', async () => {
    await settle();
    setText(priceInput(0), '15,5');
    await settle();
    expect(rows()[0].textContent).not.toContain('Cena musi być większa od zera');
    expect(rows()[0].textContent).not.toContain('nie jest poprawną ceną');
    // quantity startuje od 1 -> wartość wiersza = 1 x 15,50 = 15,50
    expect(rows()[0].querySelector('.line-total')?.textContent?.trim()).toBe('15,50');
    expect(el.querySelector('.order-total')?.textContent).toContain('15,50');
  });

  it('zmiana ceny z zewnątrz (np. po submit/reset) odświeża wyświetlany tekst na sformatowany', async () => {
    await settle();
    (component as unknown as { orderForm: any }).orderForm.items[0].unitPrice().value.set(7);
    await settle();
    expect(priceInput(0).value).toBe('7,00');
  });

  it('"Fokus na cenę" wywołuje focusBoundControl() -> fokus trafia do NASZEGO <input> w PriceInput', async () => {
    await settle();
    expect(document.activeElement).not.toBe(priceInput(0));
    (rows()[0].querySelector('.focus-price') as HTMLButtonElement).click();
    await settle();
    expect(document.activeElement).toBe(priceInput(0));
  });

  it('"Resetuj wiersz" cofa błędny, niezcommitowany tekst ceny do sformatowanej wartości modelu', async () => {
    await settle();
    setText(priceInput(0), 'coś złego'); // błąd parsowania, model NIE aktualizowany (zostaje 0)
    await settle();
    expect(priceInput(0).value).toBe('coś złego');
    expect(rows()[0].textContent).toContain('nie jest poprawną ceną');

    (rows()[0].querySelector('.reset-row') as HTMLButtonElement).click();
    await settle();

    // transformedValue() samo cofa wyświetlany tekst do format(model) i czyści błąd parsowania -
    // PriceInput NIE musiał nic do tego dopisywać ręcznie w swoim reset().
    expect(priceInput(0).value).toBe('0,00');
    expect(rows()[0].textContent).not.toContain('nie jest poprawną ceną');
  });

  it('"+ dodaj pozycję" dodaje kolejny wiersz z ceną startową 0,00', async () => {
    (el.querySelector('.add-item') as HTMLButtonElement).click();
    await settle();
    expect(rows().length).toBe(2);
    expect(priceInput(1).value).toBe('0,00');
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

  it('poprawne zamówienie: submit kończy się sukcesem po odpowiedzi fake-backendu (300ms)', async () => {
    setText(el.querySelector('#customerName')!, 'Jan Kowalski');
    setText(rows()[0].querySelector('input[type="text"]')!, 'Kabel USB-C');
    setText(priceInput(0), '9,99');
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
    setText(priceInput(0), '9,99');
    await settle();

    submitForm();
    await settle();
    submitForm();
    await settle();

    await vi.advanceTimersByTimeAsync(300);
    await settle();

    expect(el.textContent).toContain('Zamówienie przyjęte (1× wywołano backend)');
    expect(component['submitCallCount']()).toBe(1);
  });
});
