import { ComponentFixture, TestBed } from '@angular/core/testing';
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';
import { RegistrationForm } from './registration-form';

describe('RegistrationForm (Signal Forms + resource() z własnym loaderem)', () => {
  let fixture: ComponentFixture<RegistrationForm>;
  let el: HTMLElement;

  // Ten sam wzorzec co w wydaniu #3 (httpResource): resource() rejestruje pending task,
  // więc zamiast fixture.whenStable() ręcznie odpalamy fake timery + detectChanges.
  async function settle(): Promise<void> {
    fixture.detectChanges();
    await vi.advanceTimersByTimeAsync(0);
    fixture.detectChanges();
  }

  function setValue(selector: string, value: string): void {
    const input = el.querySelector(selector) as HTMLInputElement;
    input.value = value;
    input.dispatchEvent(new Event('input'));
  }

  function submitForm(): void {
    el.querySelector('form')!.dispatchEvent(new Event('submit', { cancelable: true }));
  }

  beforeEach(() => {
    vi.useFakeTimers();
    TestBed.configureTestingModule({});
    fixture = TestBed.createComponent(RegistrationForm);
    el = fixture.nativeElement;
    fixture.detectChanges();
  });

  afterEach(() => {
    vi.useRealTimers();
  });

  it('na starcie wszystkie pola są wymagane, przycisk zablokowany', async () => {
    await settle();
    expect(el.querySelector('button')?.hasAttribute('disabled')).toBe(true);
    expect(el.textContent).toContain('Login jest wymagany');
    expect(el.textContent).toContain('Adres e-mail jest wymagany');
    expect(el.textContent).toContain('Hasło jest wymagane');
  });

  it('za krótki login łapie się na minLength i NIE odpala sprawdzania dostępności', async () => {
    setValue('#username', 'ab');
    await settle();
    expect(el.textContent).toContain('co najmniej 3 znaki');
    await vi.advanceTimersByTimeAsync(1000);
    await settle();
    expect(el.textContent).not.toContain('Sprawdzam dostępność');
  });

  it('zajęty login: po debounce (300ms) i odpowiedzi "serwera" (300ms) pokazuje błąd', async () => {
    setValue('#username', 'admin');
    await settle();

    await vi.advanceTimersByTimeAsync(300); // debounce validateAsync
    await settle();
    expect(el.textContent).toContain('Sprawdzam dostępność');

    await vi.advanceTimersByTimeAsync(300); // opóźnienie fake-backendu
    await settle();
    expect(el.textContent).toContain('Login "admin" jest zajęty');
  });

  it('wolny login przechodzi asynchroniczną walidację dostępności', async () => {
    setValue('#username', 'swiezyLogin');
    await settle();
    await vi.advanceTimersByTimeAsync(300); // debounce validateAsync
    await settle();
    await vi.advanceTimersByTimeAsync(300); // opóźnienie fake-backendu
    await settle();
    expect(el.textContent).not.toContain('jest zajęty');
    expect(el.textContent).not.toContain('Sprawdzam dostępność');
  });

  it('waliduje format e-maila i minimalną długość hasła', async () => {
    setValue('#email', 'zle');
    setValue('#password', 'krotkie');
    await settle();
    expect(el.textContent).toContain('nie wygląda na adres e-mail');
    expect(el.textContent).toContain('co najmniej 8 znaków');
  });

  it('hasło bez cyfry łapie się na pattern', async () => {
    setValue('#password', 'zaDlugieHaslo');
    await settle();
    expect(el.textContent).toContain('przynajmniej jedną cyfrę');
  });

  it('poprawny formularz: submit kończy się sukcesem po odpowiedzi fake-backendu', async () => {
    setValue('#username', 'swiezyLogin');
    setValue('#email', 'nowy@example.com');
    setValue('#password', 'haslo123');
    await settle();
    await vi.advanceTimersByTimeAsync(300); // debounce validateAsync
    await settle();
    await vi.advanceTimersByTimeAsync(300); // sprawdzenie loginu w fake-backendzie
    await settle();

    expect(el.querySelector('button')?.hasAttribute('disabled')).toBe(false);
    submitForm();
    await settle();
    await vi.advanceTimersByTimeAsync(200); // fake-backend rejestracji
    await settle();
    expect(el.textContent).toContain('Konto utworzone.');
  });

  it('zajęty e-mail: błąd "z serwera" wraca na pole e-mail (fieldTree w odpowiedzi submit)', async () => {
    setValue('#username', 'swiezyLogin');
    setValue('#email', 'taken@example.com');
    setValue('#password', 'haslo123');
    await settle();
    await vi.advanceTimersByTimeAsync(300);
    await settle();
    await vi.advanceTimersByTimeAsync(300);
    await settle();

    submitForm();
    await settle();
    await vi.advanceTimersByTimeAsync(200);
    await settle();
    expect(el.textContent).toContain('jest już zarejestrowany');
    expect(el.textContent).toContain('Nie udało się utworzyć konta');
  });
});
