import { provideHttpClient } from '@angular/common/http';
import { HttpTestingController, provideHttpClientTesting } from '@angular/common/http/testing';
import { TestBed } from '@angular/core/testing';
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';
import { SearchStore } from './search.store';

const KEYBOARD = { id: 1, name: 'Klawiatura mechaniczna', category: 'peryferia', price: 349 };
const MOUSE = { id: 5, name: 'Mysz bezprzewodowa', category: 'peryferia', price: 129 };

describe('SearchStore (tapResponse WEWNĄTRZ switchMap - wersja idiomatyczna)', () => {
  let store: InstanceType<typeof SearchStore>;
  let http: HttpTestingController;

  beforeEach(() => {
    vi.useFakeTimers();
    TestBed.configureTestingModule({ providers: [provideHttpClient(), provideHttpClientTesting()] });
    store = TestBed.inject(SearchStore);
    http = TestBed.inject(HttpTestingController);
  });

  afterEach(() => {
    http.verify();
    vi.useRealTimers();
  });

  it('debounce + sukces: loading wraca na false, pendingCount na 0', () => {
    store.search('kla');
    expect(store.loading()).toBe(false); // jeszcze cisza nie trwa 300ms
    vi.advanceTimersByTime(300);
    expect(store.loading()).toBe(true);
    expect(store.pendingCount()).toBe(1);
    http.expectOne('/api/products?q=kla').flush([KEYBOARD]);
    expect(store.products()).toEqual([KEYBOARD]);
    expect(store.loading()).toBe(false);
    expect(store.pendingCount()).toBe(0);
  });

  it('błąd WEWNĄTRZ switchMap: stan error, ale strumień ŻYJE - kolejne search() działają', () => {
    store.search('boom');
    vi.advanceTimersByTime(300);
    http.expectOne('/api/products?q=boom').flush('x', { status: 500, statusText: 'Server Error' });
    expect(store.error()).toBe('Nie udało się pobrać produktów');
    expect(store.loading()).toBe(false);
    expect(store.pendingCount()).toBe(0); // finalize zdjął licznik nawet po błędzie

    store.search('mysz'); // strumień NIE umarł - w przeciwieństwie do obu anty-przykładów
    vi.advanceTimersByTime(300);
    http.expectOne('/api/products?q=mysz').flush([MOUSE]);
    expect(store.error()).toBeNull();
    expect(store.products()).toEqual([MOUSE]);
  });

  it('finalize odpala się TAKŻE dla żądania ANULOWANEGO przez switchMap (ani next, ani error by tego nie zrobiły)', () => {
    store.search('a');
    vi.advanceTimersByTime(300);
    const first = http.expectOne('/api/products?q=a');
    expect(store.pendingCount()).toBe(1);

    store.search('ab'); // nowe zapytanie ANULUJE poprzednie (switchMap)
    vi.advanceTimersByTime(300);
    const second = http.expectOne('/api/products?q=ab');
    expect(first.cancelled).toBe(true); // 'a' zostało anulowane, nie dostanie ani next, ani error
    expect(store.pendingCount()).toBe(1); // DOWÓD: finalize dla 'a' JUŻ odpalił (1, nie 2)

    second.flush([KEYBOARD]);
    expect(store.products()).toEqual([KEYBOARD]);
    expect(store.pendingCount()).toBe(0); // finalize dla 'ab' też odpalił
  });

  it('isEmpty: true tylko gdy brak wyników, bez błędu i bez trwającego ładowania', () => {
    expect(store.isEmpty()).toBe(true); // stan początkowy
    store.search('xyz');
    vi.advanceTimersByTime(300);
    expect(store.isEmpty()).toBe(false); // loading=true, jeszcze nie
    http.expectOne('/api/products?q=xyz').flush([]);
    expect(store.isEmpty()).toBe(true); // 0 wyników, brak błędu, nie ładuje
  });
});
