import { inject } from '@angular/core';
import { patchState, signalStore, withMethods, withState } from '@ngrx/signals';
import { rxMethod } from '@ngrx/signals/rxjs-interop';
import { catchError, debounceTime, distinctUntilChanged, map, of, pipe, switchMap, tap } from 'rxjs';
import { Product } from './product.model';
import { ProductsApi } from './products.api';

interface State {
  query: string;
  products: Product[];
  loading: boolean;
  error: string | null;
}

const initialState: State = { query: '', products: [], loading: false, error: null };

/**
 * ANTY-PRZYKŁAD #1 - "naturalna" refaktoryzacja, która wygląda niewinnie: `tap` (sukces)
 * i `catchError` zostały wyciągnięte PO `switchMap`, na płaski, jeden poziom pipe'a - tak,
 * jak często się pisze kod, gdy nie myśli się o tym, że `switchMap` tworzy WEWNĘTRZNY
 * strumień per żądanie. Efekt: `catchError` łapie błąd na strumieniu ZEWNĘTRZNYM (całym
 * pipe'ie rxMethod), zwraca `of(null)`, które KOMPLETUJE cały zewnętrzny strumień - a razem
 * z nim umiera jedyna, długożyjąca subskrypcja `rxMethod`. Po jednym błędzie `search()` nie
 * robi NIC (dowód w `search-broken-outer-catch.store.spec.ts`).
 */
export const SearchBrokenOuterCatchStore = signalStore(
  { providedIn: 'root' },
  withState(initialState),
  withMethods((store, api = inject(ProductsApi)) => ({
    search: rxMethod<string>(
      pipe(
        map((q: string) => q.trim()),
        debounceTime(300),
        distinctUntilChanged(),
        tap((query) => patchState(store, { query, loading: true, error: null })),
        switchMap((query) => api.search(query)),
        // BUG: to są operatory na strumieniu OUTER, nie na strumieniu, który switchMap
        // wyprodukował dla JEDNEGO żądania.
        tap((products) => patchState(store, { products, loading: false })),
        catchError(() => {
          patchState(store, { loading: false, error: 'Nie udało się pobrać produktów', products: [] });
          return of(null);
        }),
      ),
    ),
  })),
);
