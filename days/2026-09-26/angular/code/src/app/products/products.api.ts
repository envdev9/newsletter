import { HttpClient, HttpParams } from '@angular/common/http';
import { Injectable, inject } from '@angular/core';
import { Observable } from 'rxjs';
import { OrderResult, Product } from './product.model';

/** Cienki klient HTTP - odpowiednik typowanego HttpClient / Refit w .NET. */
@Injectable({ providedIn: 'root' })
export class ProductsApi {
  private readonly http = inject(HttpClient);

  search(query: string): Observable<Product[]> {
    return this.http.get<Product[]>('/api/products', { params: new HttpParams().set('q', query) });
  }

  placeOrder(productId: number): Observable<OrderResult> {
    return this.http.post<OrderResult>('/api/orders', { productId });
  }
}
