import { HttpErrorResponse, HttpInterceptorFn, HttpResponse } from '@angular/common/http';
import { delay, of, throwError } from 'rxjs';

const TAKEN = new Set(['prasowka', 'angular', 'ala & ola']);

/**
 * Backend w pamięci - tylko dla realnego `ng serve` (testy używają HttpTestingController).
 * Nazwa "boom" symuluje błąd 500.
 */
export const mockApiInterceptor: HttpInterceptorFn = (req, next) => {
  if (!req.url.startsWith('/api/')) {
    return next(req);
  }
  const url = new URL(req.urlWithParams, 'http://localhost');
  if (req.method === 'GET' && url.pathname === '/api/projects/exists') {
    const name = (url.searchParams.get('name') ?? '').trim().toLowerCase();
    if (name === 'boom') {
      return throwError(() => new HttpErrorResponse({ status: 500, url: req.url })).pipe(delay(200));
    }
    const taken = TAKEN.has(name);
    const body = taken ? { taken, suggestion: `${name}-2` } : { taken };
    return of(new HttpResponse({ status: 200, body })).pipe(delay(200));
  }
  return throwError(() => new HttpErrorResponse({ status: 404, url: req.url }));
};
