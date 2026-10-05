import { computed, inject } from '@angular/core';
import { tapResponse } from '@ngrx/operators';
import { patchState, signalStore, withComputed, withMethods, withState } from '@ngrx/signals';
import { rxMethod } from '@ngrx/signals/rxjs-interop';
import { debounceTime, distinctUntilChanged, map, pipe, switchMap, tap } from 'rxjs';
import { Product } from './product.model';
import { ProductsApi } from './products.api';

interface State {
  query: string;
  products: Product[];
  loading: boolean;
  error: string | null;
  /** Rośnie przy KAŻDYM starcie żądania, spada w `finalize` - patrz artykuł sekcja 3. */
  pendingCount: number;
}

const initialState: State = { query: '', products: [], loading: false, error: null, pendingCount: 0 };

/**
 * Wersja IDIOMATYCZNA - `tapResponse` tam, gdzie naprawdę trzeba: WEWNĄTRZ `switchMap`,
 * czyli na strumieniu jednego żądania. Trzy różnice względem ręcznego `tap` + `catchError`
 * (patrz artykuł):
 *  1. `error` jest WYMAGANY przez typy `TapResponseObserver<T, E>` - nie da się o nim
 *     zapomnieć tak, jak można zapomnieć dorzucić `catchError` do gołego `tap`.
 *  2. Błąd zawsze kończy się jako `EMPTY` (ciche `complete`), nigdy nie przecieka dalej -
 *     to jest WEWNĘTRZNA implementacja `tapResponse`, nie coś, co trzeba pisać ręcznie.
 *  3. `finalize` odpala się w KAŻDEJ sytuacji - sukces, błąd, ALE TEŻ gdy `switchMap`
 *     anuluje to żądanie, bo przyszło nowsze. Ani `next`, ani `error` nie odpalą się dla
 *     anulowanego żądania - `finalize` tak. Stąd `pendingCount` w stanie: to jedyny sposób
 *     udowodnienia w teście, że coś odpaliło się dla ANULOWANEGO żądania.
 */
export const SearchStore = signalStore(
  { providedIn: 'root' },
  withState(initialState),
  withComputed(({ products, loading, error }) => ({
    isEmpty: computed(() => !loading() && !error() && products().length === 0),
  })),
  withMethods((store, api = inject(ProductsApi)) => ({
    search: rxMethod<string>(
      pipe(
        map((q: string) => q.trim()),
        debounceTime(300),
        distinctUntilChanged(),
        tap((query) =>
          patchState(store, (s) => ({ query, loading: true, error: null, pendingCount: s.pendingCount + 1 })),
        ),
        switchMap((query) =>
          api.search(query).pipe(
            tapResponse({
              next: (products) => patchState(store, { products }),
              error: () => patchState(store, { error: 'Nie udało się pobrać produktów', products: [] }),
              // Odpala się ZAWSZE - sukces, błąd, ANULOWANIE przez nowsze szukanie.
              finalize: () => patchState(store, (s) => ({ loading: false, pendingCount: s.pendingCount - 1 })),
            }),
          ),
        ),
      ),
    ),
  })),
);
