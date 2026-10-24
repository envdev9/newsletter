import { provideHttpClient, withInterceptors } from '@angular/common/http';
import { ApplicationConfig, provideBrowserGlobalErrorListeners } from '@angular/core';
import { mockApiInterceptor } from './products/mock-api.interceptor';

export const appConfig: ApplicationConfig = {
  providers: [
    provideBrowserGlobalErrorListeners(),
    // Zamiast prawdziwego backendu - interceptor z danymi w pamięci.
    provideHttpClient(withInterceptors([mockApiInterceptor])),
  ],
};
