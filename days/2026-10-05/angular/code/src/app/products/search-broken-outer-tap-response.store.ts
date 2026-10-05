import { inject } from '@angular/core';
import { tapResponse } from '@ngrx/operators';
import { patchState, signalStore, withMethods, withState } from '@ngrx/signals';
import { rxMethod } from '@ngrx/signals/rxjs-interop';
import { debounceTime, distinctUntilChanged, map, pipe, switchMap, tap } from 'rxjs';
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
 * ANTY-PRZYKŁAD #2 - popularne błędne wyobrażenie: "tapResponse() samo z siebie chroni
 * przed śmiercią strumienia, więc mogę go wsadzić gdziekolwiek". NIE - `tapResponse` to
 * zwykły operator (`tap` + `catchError` w środku, patrz artykuł), więc obowiązują go te
 * same reguły co `catchError`: musi siedzieć WEWNĄTRZ strumienia, który tworzy `switchMap`
 * dla jednego żądania, a nie na zewnętrznym pipe'ie. Tu jest wyciągnięty PO `switchMap` -
 * i rxMethod umiera po pierwszym błędzie DOKŁADNIE tak samo, jak w anty-przykładzie #1
 * (dowód w `search-broken-outer-tap-response.store.spec.ts`).
 */
export const SearchBrokenOuterTapResponseStore = signalStore(
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
        // BUG: tapResponse() tutaj NIE jest "wewnątrz switchMap" - operuje na strumieniu
        // OUTER, dokładnie jak błędny catchError w anty-przykładzie #1.
        tapResponse({
          next: (products: Product[]) => patchState(store, { products, loading: false }),
          error: () => patchState(store, { loading: false, error: 'Nie udało się pobrać produktów', products: [] }),
        }),
      ),
    ),
  })),
);
