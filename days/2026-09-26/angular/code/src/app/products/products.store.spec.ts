import { provideHttpClient } from '@angular/common/http';
import { HttpTestingController, provideHttpClientTesting } from '@angular/common/http/testing';
import { TestBed } from '@angular/core/testing';
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';
import { ProductsStore } from './products.store';

const KEYBOARD = { id: 1, name: 'Klawiatura', category: 'peryferia', price: 100 };

describe('ProductsStore', () => {
  let store: InstanceType<typeof ProductsStore>;
  let http: HttpTestingController;

  beforeEach(() => {
    vi.useFakeTimers();
    TestBed.configureTestingModule({ providers: [provideHttpClient(), provideHttpClientTesting()] });
    store = TestBed.inject(ProductsStore);
    http = TestBed.inject(HttpTestingController);
  });

  afterEach(() => {
    http.verify();
    vi.useRealTimers();
  });

  it('debounce: seria szybkich wywołań kończy się JEDNYM żądaniem z ostatnią frazą', () => {
    store.search('k');
    store.search('kl');
    store.search('kla');
    vi.advanceTimersByTime(299);
    http.expectNone('/api/products?q=kla'); // jeszcze cisza nie trwa 300 ms
    vi.advanceTimersByTime(1);
    const req = http.expectOne('/api/products?q=kla');
    expect(store.loading()).toBe(true);
    req.flush([KEYBOARD]);
    expect(store.products()).toEqual([KEYBOARD]);
    expect(store.count()).toBe(1);
    expect(store.loading()).toBe(false);
  });

  it('distinctUntilChanged: ta sama fraza po odpowiedzi nie wysyła drugiego żądania', () => {
    store.search('mysz');
    vi.advanceTimersByTime(300);
    http.expectOne('/api/products?q=mysz').flush([]);
    store.search(' mysz '); // po trim() to ta sama fraza
    vi.advanceTimersByTime(300);
    http.expectNone('/api/products?q=mysz');
  });

  it('switchMap: nowe żądanie ANULUJE poprzednie i liczy się tylko ostatnia odpowiedź', () => {
    store.search('a');
    vi.advanceTimersByTime(300);
    const first = http.expectOne('/api/products?q=a');
    store.search('ab');
    vi.advanceTimersByTime(300);
    const second = http.expectOne('/api/products?q=ab');
    expect(first.cancelled).toBe(true);
    expect(second.cancelled).toBe(false);
    second.flush([KEYBOARD]);
    expect(store.products()).toEqual([KEYBOARD]);
  });

  it('catchError wewnątrz switchMap: błąd ustawia stan error, a strumień dalej żyje', () => {
    store.search('boom');
    vi.advanceTimersByTime(300);
    http.expectOne('/api/products?q=boom').flush('x', { status: 500, statusText: 'Server Error' });
    expect(store.error()).toBe('Nie udało się pobrać produktów');
    expect(store.loading()).toBe(false);

    store.search('ok'); // strumień nie umarł po błędzie
    vi.advanceTimersByTime(300);
    http.expectOne('/api/products?q=ok').flush([KEYBOARD]);
    expect(store.error()).toBeNull();
    expect(store.products()).toEqual([KEYBOARD]);
  });

  it('exhaustMap: kolejne kliknięcia w trakcie zamówienia są ignorowane', () => {
    store.placeOrder(1);
    store.placeOrder(1);
    store.placeOrder(1);
    const req = http.expectOne('/api/orders'); // expectOne rzuci, gdyby było więcej niż jedno
    expect(store.ordering()).toBe(true);
    req.flush({ orderId: 'ORD-1' });
    expect(store.ordering()).toBe(false);
    expect(store.lastOrderId()).toBe('ORD-1');

    store.placeOrder(1); // po zakończeniu można znów
    http.expectOne('/api/orders').flush({ orderId: 'ORD-2' });
    expect(store.lastOrderId()).toBe('ORD-2');
  });
});
