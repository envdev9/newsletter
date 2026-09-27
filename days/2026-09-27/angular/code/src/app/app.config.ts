import { ApplicationConfig, provideBrowserGlobalErrorListeners } from '@angular/core';
import { provideRouter, withComponentInputBinding } from '@angular/router';
import { routes } from './app.routes';

export const appConfig: ApplicationConfig = {
  providers: [
    provideBrowserGlobalErrorListeners(),
    // withComponentInputBinding: parametry ścieżki, query params i dane z resolverów
    // trafiają wprost do input()-ów komponentu trasy.
    provideRouter(routes, withComponentInputBinding()),
  ],
};
