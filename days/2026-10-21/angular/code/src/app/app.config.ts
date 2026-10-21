import { provideHttpClient } from '@angular/common/http';
import { ApplicationConfig, provideBrowserGlobalErrorListeners } from '@angular/core';
import { EFFECTS_ERROR_HANDLER, provideEffects } from '@ngrx/effects';
import { provideStore } from '@ngrx/store';
import { createErrorPolicy } from './orders/effects-error-policy';
import { leakySearch, ordersReducer, pinger } from './orders/orders.store';

export const appConfig: ApplicationConfig = {
  providers: [
    provideBrowserGlobalErrorListeners(),
    provideHttpClient(),
    provideStore({ orders: ordersReducer }),
    provideEffects({ leakySearch, pinger }),
    {
      provide: EFFECTS_ERROR_HANDLER,
      useValue: createErrorPolicy({
        maxRetries: 3,
        baseDelayMs: 0,
        onDied: (e) => console.error('Efekt zakończył pracę po wyczerpaniu prób:', e),
      }),
    },
  ],
};
