import { Component, inject } from '@angular/core';
import { Store } from '@ngrx/store';
import { OrdersActions, OrdersState } from './orders/orders.store';
import { ProfileForm } from './profile/profile-form';

@Component({
  selector: 'app-root',
  imports: [ProfileForm],
  template: `
    <h1>Angular: mapResponse() w efektach + CVA obok Signal Forms</h1>
    <section>
      <h2>Zamówienia (NgRx Effects + mapResponse)</h2>
      <input #q placeholder="szukaj" (keyup.enter)="search(q.value)" />
      <button type="button" (click)="search(q.value)">Szukaj</button>
      <p>loading={{ state().loading }}, wyników={{ state().orders.length }}, błąd={{ state().error ?? 'brak' }}</p>
    </section>
    <section>
      <h2>Profil (compatForm: FormControl + CVA)</h2>
      <app-profile-form />
    </section>
  `,
})
export class App {
  private readonly store = inject(Store<{ orders: OrdersState }>);
  protected readonly state = this.store.selectSignal((s: { orders: OrdersState }) => s.orders);

  protected search(query: string): void {
    this.store.dispatch(OrdersActions.search({ query }));
  }
}
