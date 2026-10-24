import { provideHttpClient } from '@angular/common/http';
import { HttpTestingController, provideHttpClientTesting } from '@angular/common/http/testing';
import { TestBed } from '@angular/core/testing';
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';
import { SearchBrokenOuterTapResponseStore } from './search-broken-outer-tap-response.store';

const MOUSE = { id: 5, name: 'Mysz bezprzewodowa', category: 'peryferia', price: 129 };

describe('SearchBrokenOuterTapResponseStore (anty-przykład #2)', () => {
  let store: InstanceType<typeof SearchBrokenOuterTapResponseStore>;
  let http: HttpTestingController;

  beforeEach(() => {
    vi.useFakeTimers();
    TestBed.configureTestingModule({ providers: [provideHttpClient(), provideHttpClientTesting()] });
    store = TestBed.inject(SearchBrokenOuterTapResponseStore);
    http = TestBed.inject(HttpTestingController);
  });

  afterEach(() => {
    http.verify();
    vi.useRealTimers();
  });

  it('tapResponse() źle umieszczony (PO switchMap) ma TEN SAM błąd co ręczny catchError PO switchMap', () => {
    store.search('boom');
    vi.advanceTimersByTime(300);
    http.expectOne('/api/products?q=boom').flush('x', { status: 500, statusText: 'Server Error' });
    expect(store.error()).toBe('Nie udało się pobrać produktów');

    store.search('mysz');
    vi.advanceTimersByTime(300);
    // DOWÓD na tezę artykułu: tapResponse() NIE jest "magicznie bezpieczny" niezależnie
    // od miejsca w pipe. To wciąż `tap` + `catchError` w środku (patrz ngrx-operators.mjs) -
    // umieszczony na złym poziomie psuje się identycznie jak gołe `catchError`.
    http.expectNone('/api/products?q=mysz');
    expect(store.products()).toEqual([]);
  });

  it('bez błędu (kontrola) ten sam kod działa normalnie', () => {
    store.search('mysz');
    vi.advanceTimersByTime(300);
    http.expectOne('/api/products?q=mysz').flush([MOUSE]);
    expect(store.products()).toEqual([MOUSE]);
  });
});
