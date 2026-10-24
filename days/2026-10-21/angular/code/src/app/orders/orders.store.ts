import { HttpClient, HttpErrorResponse } from '@angular/common/http';
import { Injectable, inject } from '@angular/core';
import { Actions, createEffect, ofType } from '@ngrx/effects';
import { mapResponse } from '@ngrx/operators';
import { createActionGroup, createReducer, emptyProps, on, props } from '@ngrx/store';
import { Observable, map, scan, switchMap } from 'rxjs';

export interface Order {
  id: number;
  title: string;
}

export const OrdersActions = createActionGroup({
  source: 'Orders',
  events: {
    search: props<{ query: string }>(),
    'search success': props<{ orders: Order[] }>(),
    'search failure': props<{ message: string }>(),
    ping: emptyProps(),
    pong: emptyProps(),
  },
});

@Injectable({ providedIn: 'root' })
export class OrdersApi {
  private readonly http = inject(HttpClient);

  search(query: string): Observable<Order[]> {
    return this.http.get<Order[]>('/api/orders', { params: { q: query } });
  }
}

export interface OrdersState {
  loading: boolean;
  orders: Order[];
  error: string | null;
}

const initial: OrdersState = { loading: false, orders: [], error: null };

export const ordersReducer = createReducer(
  initial,
  on(OrdersActions.search, (s): OrdersState => ({ ...s, loading: true, error: null })),
  on(OrdersActions.searchSuccess, (s, { orders }): OrdersState => ({ ...s, loading: false, orders })),
  on(OrdersActions.searchFailure, (s, { message }): OrdersState => ({ ...s, loading: false, error: message })),
);

/** Efekt "bezpieczny": błąd HTTP zamieniany na akcję WEWNĄTRZ switchMap (to z #27) - nie wymaga siatki NgRx. */
export const safeSearch = createEffect(
  (actions$ = inject(Actions), api = inject(OrdersApi)) =>
    actions$.pipe(
      ofType(OrdersActions.search),
      switchMap(({ query }) =>
        api.search(query).pipe(
          mapResponse({
            next: (orders) => OrdersActions.searchSuccess({ orders }),
            error: (e: HttpErrorResponse) => OrdersActions.searchFailure({ message: `HTTP ${e.status}` }),
          }),
        ),
      ),
    ),
  { functional: true },
);

/**
 * Efekt "dziurawy": błąd HTTP NIE jest obsłużony, wycieka do strażnika NgRx (EFFECTS_ERROR_HANDLER).
 * `scan` liczy wywołania - dzięki niemu widać, że resubskrypcja zeruje stan wewnątrz efektu.
 * Numer wywołania trafia do parametru `q` (np. "x#1"), więc test widzi go w URL-u żądania.
 */
export const leakySearch = createEffect(
  (actions$ = inject(Actions), api = inject(OrdersApi)) =>
    actions$.pipe(
      ofType(OrdersActions.search),
      scan((n, a) => ({ n: n.n + 1, query: a.query }), { n: 0, query: '' }),
      switchMap(({ n, query }) =>
        api.search(`${query}#${n}`).pipe(map((orders) => OrdersActions.searchSuccess({ orders }))),
      ),
    ),
  { functional: true },
);

/** Efekt-sąsiad: odpowiada `pong` na `ping`. Służy do sprawdzenia, czy awaria innego efektu go nie zabija. */
export const pinger = createEffect(
  (actions$ = inject(Actions)) =>
    actions$.pipe(
      ofType(OrdersActions.ping),
      map(() => OrdersActions.pong()),
    ),
  { functional: true },
);

/** To samo co leakySearch, ale z WYŁĄCZONYM strażnikiem: `useEffectsErrorHandler: false`. */
export const leakyNoGuard = createEffect(
  (actions$ = inject(Actions), api = inject(OrdersApi)) =>
    actions$.pipe(
      ofType(OrdersActions.search),
      switchMap(({ query }) => api.search(query).pipe(map((orders) => OrdersActions.searchSuccess({ orders })))),
    ),
  { functional: true, useEffectsErrorHandler: false },
);
