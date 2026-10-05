import { HttpErrorResponse, HttpInterceptorFn, HttpResponse } from '@angular/common/http';
import { delay, of, throwError } from 'rxjs';
import { Product } from './product.model';

const CATALOG: Product[] = [
  { id: 1, name: 'Klawiatura mechaniczna', category: 'peryferia', price: 349 },
  { id: 2, name: 'Klawiatura membranowa', category: 'peryferia', price: 79 },
  { id: 3, name: 'Monitor 27 cali', category: 'ekrany', price: 1299 },
  { id: 4, name: 'Monitor 32 cale', category: 'ekrany', price: 1899 },
  { id: 5, name: 'Mysz bezprzewodowa', category: 'peryferia', price: 129 },
];

/**
 * Lokalny "backend w pamięci" - używany tylko przy realnym `ng serve`
 * (testy jednostkowe idą przez HttpTestingController i NIE przechodzą przez ten
 * interceptor - patrz `*.store.spec.ts`). Fraza "boom" symuluje błąd 500 serwera.
 */
export const mockApiInterceptor: HttpInterceptorFn = (req, next) => {
  if (!req.url.startsWith('/api/')) {
    return next(req);
  }
  const url = new URL(req.url, 'http://localhost');

  if (req.method === 'GET' && url.pathname === '/api/products') {
    const q = (url.searchParams.get('q') ?? '').toLowerCase();
    if (q === 'boom') {
      return throwError(() => new HttpErrorResponse({ status: 500, url: req.url })).pipe(delay(200));
    }
    const list = CATALOG.filter((p) => p.name.toLowerCase().includes(q));
    return of(new HttpResponse({ status: 200, body: list })).pipe(delay(200));
  }

  return throwError(() => new HttpErrorResponse({ status: 404, url: req.url }));
};
