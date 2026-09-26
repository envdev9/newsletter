import { HttpErrorResponse, HttpInterceptorFn, HttpResponse } from '@angular/common/http';
import { delay, of, throwError } from 'rxjs';
import { OrderResult, Product, ProductDetails } from './product.model';

const DETAILS: ProductDetails[] = [
  { id: 1, name: 'Klawiatura mechaniczna', category: 'peryferia', price: 349, stock: 12, description: 'Przełączniki brązowe, układ ISO.' },
  { id: 2, name: 'Klawiatura membranowa', category: 'peryferia', price: 79, stock: 40, description: 'Cicha, biurowa.' },
  { id: 3, name: 'Monitor 27 cali', category: 'ekrany', price: 1299, stock: 0, description: 'IPS, 144 Hz. Chwilowo niedostępny.' },
  { id: 4, name: 'Monitor 32 cale', category: 'ekrany', price: 1899, stock: 5, description: 'VA, zakrzywiony.' },
  { id: 5, name: 'Mysz bezprzewodowa', category: 'peryferia', price: 129, stock: 25, description: 'Sensor 4000 DPI.' },
];

/**
 * Lokalny "backend w pamięci" - funkcyjny interceptor HttpClient (odpowiednik
 * DelegatingHandler / HttpMessageHandler z .NET używanego w testach). Żadnej sieci.
 * Zapytanie q=boom zwraca 500, żeby dało się zobaczyć stan błędu.
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
    const list: Product[] = DETAILS.filter((p) => p.name.toLowerCase().includes(q)).map(
      ({ id, name, category, price }) => ({ id, name, category, price }),
    );
    return of(new HttpResponse({ status: 200, body: list })).pipe(delay(200));
  }

  const single = /^\/api\/products\/(\d+)$/.exec(url.pathname);
  if (req.method === 'GET' && single) {
    const found = DETAILS.find((p) => p.id === Number(single[1]));
    return found
      ? of(new HttpResponse({ status: 200, body: found })).pipe(delay(200))
      : throwError(() => new HttpErrorResponse({ status: 404, url: req.url }));
  }

  if (req.method === 'POST' && url.pathname === '/api/orders') {
    const body: OrderResult = { orderId: `ORD-${Math.floor(Math.random() * 9000 + 1000)}` };
    return of(new HttpResponse({ status: 201, body })).pipe(delay(800));
  }

  return throwError(() => new HttpErrorResponse({ status: 404, url: req.url }));
};
