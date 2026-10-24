import { Component, inject } from '@angular/core';
import { Store } from '@ngrx/store';
import { OrdersActions, OrdersState } from './orders/orders.store';

@Component({
  selector: 'app-root',
  template: `
    <h1>Angular: własny EFFECTS_ERROR_HANDLER w NgRx Effects</h1>
    <input #q placeholder="szukaj" (keyup.enter)="search(q.value)" />
    <button type="button" (click)="search(q.value)">Szukaj</button>
    <p>loading={{ state().loading }}, wyników={{ state().orders.length }}, błąd={{ state().error ?? 'brak' }}</p>
  `,
})
export class App {
  private readonly store = inject(Store<{ orders: OrdersState }>);
  protected readonly state = this.store.selectSignal((s: { orders: OrdersState }) => s.orders);

  protected search(query: string): void {
    this.store.dispatch(OrdersActions.search({ query }));
  }
}
