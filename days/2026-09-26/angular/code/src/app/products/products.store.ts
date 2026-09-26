import { computed, inject } from '@angular/core';
import { patchState, signalStore, withComputed, withMethods, withState } from '@ngrx/signals';
import { rxMethod } from '@ngrx/signals/rxjs-interop';
import { catchError, debounceTime, distinctUntilChanged, exhaustMap, map, of, pipe, switchMap, tap } from 'rxjs';
import { Product } from './product.model';
import { ProductsApi } from './products.api';

interface ProductsState {
  query: string;
  products: Product[];
  loading: boolean;
  error: string | null;
  ordering: boolean;
  lastOrderId: string | null;
}

const initialState: ProductsState = {
  query: '',
  products: [],
  loading: false,
  error: null,
  ordering: false,
  lastOrderId: null,
};

export const ProductsStore = signalStore(
  { providedIn: 'root' },
  withState(initialState),
  withComputed(({ products, error, loading }) => ({
    count: computed(() => products().length),
    isEmpty: computed(() => !loading() && !error() && products().length === 0),
  })),
  withMethods((store, api = inject(ProductsApi)) => ({
    /**
     * rxMethod = "wstrzyknij strumień RxJS w metodę store'a". Wywołanie search('kl')
     * to po prostu next('kl') na wewnętrznym Subject-cie; można też podać signal -
     * wtedy metoda odpala się przy każdej jego zmianie.
     */
    search: rxMethod<string>(
      pipe(
        map((q) => q.trim()),
        debounceTime(300), // poczekaj na ciszę - nie strzelaj przy każdym klawiszu
        distinctUntilChanged(), // ten sam tekst co ostatnio? nie powtarzaj żądania
        tap((query) => patchState(store, { query, loading: true, error: null })),
        // switchMap: nowe zapytanie ANULUJE poprzednie (HttpClient przerywa XHR przy unsubscribe).
        switchMap((query) =>
          api.search(query).pipe(
            tap((products) => patchState(store, { products, loading: false })),
            // catchError WEWNĄTRZ switchMap - błąd zabija tylko to żądanie, nie cały strumień.
            catchError(() => {
              patchState(store, { products: [], loading: false, error: 'Nie udało się pobrać produktów' });
              return of(null);
            }),
          ),
        ),
      ),
    ),

    /**
     * exhaustMap: dopóki zamówienie leci, kolejne kliknięcia są IGNOROWANE
     * (odpowiednik "if (_inFlight) return;" - ochrona przed podwójnym POST-em).
     */
    placeOrder: rxMethod<number>(
      pipe(
        exhaustMap((productId) => {
          patchState(store, { ordering: true, error: null });
          return api.placeOrder(productId).pipe(
            tap(({ orderId }) => patchState(store, { ordering: false, lastOrderId: orderId })),
            catchError(() => {
              patchState(store, { ordering: false, error: 'Zamówienie nie powiodło się' });
              return of(null);
            }),
          );
        }),
      ),
    ),
  })),
);
