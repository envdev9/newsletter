import { HttpErrorResponse, provideHttpClient } from '@angular/common/http';
import { HttpTestingController, provideHttpClientTesting } from '@angular/common/http/testing';
import { ErrorHandler, inject } from '@angular/core';
import { TestBed } from '@angular/core/testing';
import { Actions, createEffect, ofType, provideEffects } from '@ngrx/effects';
import { mapResponse } from '@ngrx/operators';
import { Store } from '@ngrx/store';
import { provideStore } from '@ngrx/store';
import { catchError, map, of, switchMap } from 'rxjs';
import { OrdersActions, OrdersApi, ordersReducer, searchOrders } from './orders.store';

const measure = (name: string, data: unknown) => console.log(`MEASURE ${name}: ${JSON.stringify(data)}`);

type EffectFn = ReturnType<typeof createEffect>;

/** Wariant 1: mapResponse na zewnątrz switchMap (zły: po 1. błędzie strumień zewnętrzny się kończy). */
const mapResponseOutside = createEffect(
  (actions$ = inject(Actions), api = inject(OrdersApi)) =>
    actions$.pipe(
      ofType(OrdersActions.search),
      switchMap(({ query }) => api.search(query)),
      mapResponse({
        next: (orders) => OrdersActions.searchSuccess({ orders }),
        error: (e: HttpErrorResponse) => OrdersActions.searchFailure({ message: `HTTP ${e.status}` }),
      }),
    ),
  { functional: true },
);

/** Wariant 2: w ogóle bez obsługi błędu (błąd leci do NgRx, ten wznawia efekt i woła ErrorHandler). */
const noErrorHandling = createEffect(
  (actions$ = inject(Actions), api = inject(OrdersApi)) =>
    actions$.pipe(
      ofType(OrdersActions.search),
      switchMap(({ query }) => api.search(query).pipe(map((orders) => OrdersActions.searchSuccess({ orders })))),
    ),
  { functional: true },
);

/** Wariant 3: ręczny map + catchError wewnątrz - to, co mapResponse skraca do jednego operatora. */
const manualInside = createEffect(
  (actions$ = inject(Actions), api = inject(OrdersApi)) =>
    actions$.pipe(
      ofType(OrdersActions.search),
      switchMap(({ query }) =>
        api.search(query).pipe(
          map((orders) => OrdersActions.searchSuccess({ orders })),
          catchError((e: HttpErrorResponse) => of(OrdersActions.searchFailure({ message: `HTTP ${e.status}` }))),
        ),
      ),
    ),
  { functional: true },
);

/** Wariant 4: mapper `next` rzuca wyjątek. */
const nextThrows = createEffect(
  (actions$ = inject(Actions), api = inject(OrdersApi)) =>
    actions$.pipe(
      ofType(OrdersActions.search),
      switchMap(({ query }) =>
        api.search(query).pipe(
          mapResponse({
            next: (orders): ReturnType<typeof OrdersActions.searchSuccess> => {
              if (orders.length === 0) throw new Error('mapper wybuchł');
              return OrdersActions.searchSuccess({ orders });
            },
            error: (e: unknown) =>
              OrdersActions.searchFailure({ message: e instanceof HttpErrorResponse ? `HTTP ${e.status}` : `JS: ${(e as Error).message}` }),
          }),
        ),
      ),
    ),
  { functional: true },
);

/** Wariant 5: sam callback `error` rzuca wyjątek. */
const errorThrows = createEffect(
  (actions$ = inject(Actions), api = inject(OrdersApi)) =>
    actions$.pipe(
      ofType(OrdersActions.search),
      switchMap(({ query }) =>
        api.search(query).pipe(
          mapResponse({
            next: (orders) => OrdersActions.searchSuccess({ orders }),
            error: (): ReturnType<typeof OrdersActions.searchFailure> => {
              throw new Error('callback error wybuchł');
            },
          }),
        ),
      ),
    ),
  { functional: true },
);

function setup(effect: EffectFn) {
  const handled: string[] = [];
  TestBed.configureTestingModule({
    providers: [
      provideHttpClient(),
      provideHttpClientTesting(),
      provideStore({ orders: ordersReducer }),
      provideEffects({ effect }),
      { provide: ErrorHandler, useValue: { handleError: (e: unknown) => handled.push(String((e as Error).message ?? e)) } },
    ],
  });
  const http = TestBed.inject(HttpTestingController);
  const store = TestBed.inject(Store);
  const seen: string[] = [];
  TestBed.inject(Actions).subscribe((a) => seen.push(a.type));
  const state = () => {
    let s: unknown;
    store.subscribe((v) => (s = v)).unsubscribe();
    return (s as { orders: { loading: boolean; orders: unknown[]; error: string | null } }).orders;
  };
  /** Wysyła `search`; zwraca zapytania HTTP, które efekt faktycznie wyemitował (0 = efekt nie żyje). */
  const search = (query: string) => {
    store.dispatch(OrdersActions.search({ query }));
    return http.match((r) => r.url === '/api/orders');
  };
  return { http, store, seen, handled, state, search };
}

describe('mapResponse() w funkcyjnym efekcie @ngrx/effects', () => {
  afterEach(() => TestBed.inject(HttpTestingController).verify());

  it('sukces: HTTP -> akcja searchSuccess -> reducer', () => {
    const h = setup(searchOrders);
    const [req] = h.search('abc');
    expect(req.request.params.get('q')).toBe('abc');
    expect(h.state().loading).toBe(true);
    req.flush([{ id: 1, title: 'A' }]);
    measure('success', { actions: h.seen, state: h.state(), errorHandler: h.handled });
    expect(h.seen).toEqual(['[Orders] search', '[Orders] search success']);
    expect(h.state()).toEqual({ loading: false, orders: [{ id: 1, title: 'A' }], error: null });
  });

  it('błąd 500 -> searchFailure, efekt żyje i obsługuje kolejne zapytanie, ErrorHandler nietknięty', () => {
    const h = setup(searchOrders);
    h.search('x')[0].flush('boom', { status: 500, statusText: 'Server Error' });
    expect(h.state().error).toBe('HTTP 500');
    const [second] = h.search('y');
    expect(second).toBeDefined();
    second.flush([{ id: 2, title: 'B' }]);
    measure('error-then-ok', { actions: h.seen, state: h.state(), errorHandler: h.handled });
    expect(h.seen).toEqual([
      '[Orders] search',
      '[Orders] search failure',
      '[Orders] search',
      '[Orders] search success',
    ]);
    expect(h.handled).toEqual([]);
    expect(h.state().error).toBeNull();
  });

  it('switchMap anuluje poprzednie żądanie, mapResponse nie emituje nic za anulowane', () => {
    const h = setup(searchOrders);
    const [first] = h.search('a');
    const [second] = h.search('ab');
    measure('switchMap-cancel', { firstCancelled: first.cancelled, secondCancelled: second.cancelled });
    expect(first.cancelled).toBe(true);
    second.flush([]);
    expect(h.seen).toEqual(['[Orders] search', '[Orders] search', '[Orders] search success']);
  });

  it('ręczny map + catchError wewnątrz daje IDENTYCZNY przebieg jak mapResponse', () => {
    const a = setup(searchOrders);
    a.search('x')[0].flush('boom', { status: 500, statusText: 'Server Error' });
    a.search('y')[0].flush([]);
    const withMapResponse = { actions: [...a.seen], state: a.state() };
    TestBed.resetTestingModule();

    const b = setup(manualInside);
    b.search('x')[0].flush('boom', { status: 500, statusText: 'Server Error' });
    b.search('y')[0].flush([]);
    const manual = { actions: [...b.seen], state: b.state() };
    measure('manual-equals-mapResponse', { same: JSON.stringify(withMapResponse) === JSON.stringify(manual) });
    expect(manual).toEqual(withMapResponse);
  });

  it('PUŁAPKA: mapResponse NA ZEWNĄTRZ switchMap - po 1. błędzie efekt kończy się po cichu', () => {
    const h = setup(mapResponseOutside);
    h.search('x')[0].flush('boom', { status: 500, statusText: 'Server Error' });
    const afterFirst = h.state();
    const second = h.search('y');
    measure('outside', { afterFirst, actions: h.seen, secondRequests: second.length, errorHandler: h.handled });
    expect(afterFirst.error).toBe('HTTP 500'); // pierwszy błąd został obsłużony ...
    expect(second.length).toBe(0); // ... ale drugie wyszukiwanie nie wysyła już żadnego żądania
    expect(h.handled).toEqual([]); // i nikt się o tym nie dowie: ErrorHandler cichy (strumień ZAKOŃCZONY, nie "z błędem")
  });

  it('bez obsługi błędu: NgRx wznawia efekt i woła ErrorHandler, ale reducer zostaje w loading=true', () => {
    const h = setup(noErrorHandling);
    h.search('x')[0].flush('boom', { status: 500, statusText: 'Server Error' });
    const stuck = h.state();
    const second = h.search('y');
    measure('no-handling', { stuck, handled: h.handled.length, secondRequests: second.length, actions: h.seen });
    expect(stuck.loading).toBe(true);
    expect(stuck.error).toBeNull();
    expect(h.handled.length).toBe(1);
    expect(second.length).toBe(1); // wznowiony
    second[0].flush([]);
  });

  it('bez obsługi błędu: wznowień jest 10 - 11. błąd zabija efekt na dobre', () => {
    const h = setup(noErrorHandling);
    const handledAfter: number[] = [];
    let alive = 0;
    for (let i = 1; i <= 13; i++) {
      const reqs = h.search(`q${i}`);
      if (reqs.length === 0) break;
      alive = i;
      reqs[0].flush('boom', { status: 500, statusText: 'Server Error' });
      handledAfter.push(h.handled.length);
    }
    measure('retry-limit', { lastQueryThatSentRequest: alive, handledAfter });
    expect(alive).toBe(11); // 11. zapytanie jeszcze wysłane (10 wznowień + oryginał), 12. już nie
    expect(handledAfter[10]).toBe(10); // 11. błąd nie przechodzi już przez ErrorHandler
  });

  it('wyjątek w mapperze `next` trafia do callbacku `error` jako zwykły Error (nie HttpErrorResponse)', () => {
    const h = setup(nextThrows);
    h.search('x')[0].flush([]);
    measure('next-throws', { state: h.state(), actions: h.seen, errorHandler: h.handled });
    expect(h.state().error).toBe('JS: mapper wybuchł');
  });

  it('wyjątek w callbacku `error` ucieka na zewnątrz: ErrorHandler + wznowienie efektu', () => {
    const h = setup(errorThrows);
    h.search('x')[0].flush('boom', { status: 500, statusText: 'Server Error' });
    const second = h.search('y');
    measure('error-throws', { handled: h.handled, secondRequests: second.length, state: h.state() });
    expect(h.handled).toEqual(['callback error wybuchł']);
    expect(second.length).toBe(1);
    expect(h.state().loading).toBe(true);
    second[0].flush([]);
  });
});
