import { provideHttpClient } from '@angular/common/http';
import { HttpTestingController, provideHttpClientTesting } from '@angular/common/http/testing';
import { TestBed } from '@angular/core/testing';
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';
import { SearchBrokenOuterCatchStore } from './search-broken-outer-catch.store';

const MOUSE = { id: 5, name: 'Mysz bezprzewodowa', category: 'peryferia', price: 129 };

describe('SearchBrokenOuterCatchStore (anty-przykład #1)', () => {
  let store: InstanceType<typeof SearchBrokenOuterCatchStore>;
  let http: HttpTestingController;

  beforeEach(() => {
    vi.useFakeTimers();
    TestBed.configureTestingModule({ providers: [provideHttpClient(), provideHttpClientTesting()] });
    store = TestBed.inject(SearchBrokenOuterCatchStore);
    http = TestBed.inject(HttpTestingController);
  });

  afterEach(() => {
    http.verify();
    vi.useRealTimers();
  });

  it('po BŁĘDZIE cały strumień rxMethod umiera - kolejne search() nie wysyłają NIC', () => {
    store.search('boom');
    vi.advanceTimersByTime(300);
    http.expectOne('/api/products?q=boom').flush('x', { status: 500, statusText: 'Server Error' });
    expect(store.error()).toBe('Nie udało się pobrać produktów');

    // Kolejne, zupełnie poprawne wyszukiwanie - PO błędzie. Zewnętrzny catchError()
    // zamienił cały pipe rxMethod na `of(null)`, ten się skompletował, a jedyna
    // subskrypcja rxMethod umarła wraz z nim.
    store.search('mysz');
    vi.advanceTimersByTime(300);
    http.expectNone('/api/products?q=mysz'); // DOWÓD: żadne żądanie nie wyszło

    expect(store.products()).toEqual([]);
    expect(store.loading()).toBe(false);
  });

  it('bez błędu (kontrola) ten sam kod działa normalnie', () => {
    store.search('mysz');
    vi.advanceTimersByTime(300);
    http.expectOne('/api/products?q=mysz').flush([MOUSE]);
    expect(store.products()).toEqual([MOUSE]);
  });
});
