import { computed } from '@angular/core';
import { patchState, signalStore, withComputed, withMethods, withState } from '@ngrx/signals';

export interface CartLine {
  id: string;
  name: string;
  unitPrice: number;
  quantity: number;
}

interface CartState {
  lines: CartLine[];
}

const initialState: CartState = {
  lines: [
    { id: 'sub', name: 'Newsletter Pro (subskrypcja)', unitPrice: 19.99, quantity: 1 },
    { id: 'mug', name: "Kubek \"console.log('debug')\"", unitPrice: 39.0, quantity: 1 },
  ],
};

// signalStore() z @ngrx/signals - to, co budujemy NA FUNDAMENCIE signal()/computed()
// z poprzednich przykładów, nie zamiast nich. Zamiast rozsianych po serwisie osobnych
// signal()-i, dostajesz jeden spójny, wstrzykiwalny obiekt stanu:
//   - withState()    - startowy stan (każde pole staje się osobnym, odczytywalnym signal()-em)
//   - withComputed() - "selektory" - to są zwykłe computed() z pierwszego przykładu,
//                       tylko zdefiniowane w jednym miejscu razem ze stanem
//                       (parametr to obiekt sygnałów stanu, np. `lines` = signal)
//   - withMethods()  - akcje zmieniające stan przez patchState() (odpowiednik immutowalnego
//                       "with" znanego z C# recordów - nie mutujesz obiektu, tworzysz nowy)
//
// WAŻNE: to NIE jest klasyczny @ngrx/store (Redux - akcje, reducery, efekty, dispatch).
// @ngrx/signals to CAŁKOWICIE INNA, dużo lżejsza biblioteka - "sklejacz" ceremonii
// dookoła signal()-i, bez architektury Redux. Jeśli znasz NgRx Store z akcjami
// i reducerami - zapomnij o tym, signalStore ma zupełnie inny, dużo prostszy model.
export const CartStore = signalStore(
  { providedIn: 'root' },
  withState(initialState),
  withComputed(({ lines }) => ({
    itemCount: computed(() => lines().reduce((sum, line) => sum + line.quantity, 0)),
    total: computed(() => lines().reduce((sum, line) => sum + line.quantity * line.unitPrice, 0)),
  })),
  withMethods((store) => ({
    setQuantity(id: string, quantity: number): void {
      patchState(store, (state) => ({
        lines: state.lines.map((line) => (line.id === id ? { ...line, quantity } : line)),
      }));
    },
    removeLine(id: string): void {
      patchState(store, (state) => ({
        lines: state.lines.filter((line) => line.id !== id),
      }));
    },
  })),
);
