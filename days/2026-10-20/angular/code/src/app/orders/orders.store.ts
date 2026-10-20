import { HttpClient, HttpErrorResponse } from '@angular/common/http';
import { Injectable, inject } from '@angular/core';
import { Actions, createEffect, ofType } from '@ngrx/effects';
import { mapResponse } from '@ngrx/operators';
import { createActionGroup, createReducer, on, props } from '@ngrx/store';
import { Observable, switchMap } from 'rxjs';

export interface Order {
  id: number;
  title: string;
}

/** "Zdarzenia" w świecie NgRx: nazwany, typowany komunikat. Odpowiednik rekordu-zdarzenia w CQRS. */
export const OrdersActions = createActionGroup({
  source: 'Orders',
  events: {
    search: props<{ query: string }>(),
    'search success': props<{ orders: Order[] }>(),
    'search failure': props<{ message: string }>(),
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

/**
 * Efekt "po bożemu": mapResponse WEWNĄTRZ switchMap, przy wywołaniu HTTP.
 * Zamienia odpowiedź na akcję sukcesu, a błąd - na akcję porażki, więc strumień zewnętrzny nigdy nie widzi błędu.
 */
export const searchOrders = createEffect(
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
