import { provideHttpClient } from '@angular/common/http';
import { HttpTestingController, provideHttpClientTesting } from '@angular/common/http/testing';
import { ComponentFixture, TestBed } from '@angular/core/testing';
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';
import { ProductBrowser } from './product-browser';

const P = (id: number) => ({ id, name: `Produkt ${id}`, category: 'x', price: id * 10 });
const D = (id: number) => ({ ...P(id), description: `Opis ${id}`, stock: 3 });

describe('ProductBrowser (linkedSignal + httpResource)', () => {
  let fixture: ComponentFixture<ProductBrowser>;
  let http: HttpTestingController;
  let el: HTMLElement;

  // Uwaga: NIE wolno tu używać fixture.whenStable(), gdy żądanie httpResource jest w locie -
  // resource rejestruje "pending task", więc whenStable czekałoby na odpowiedź (timeout testu).
  async function settle(): Promise<void> {
    fixture.detectChanges();
    await vi.advanceTimersByTimeAsync(0);
    fixture.detectChanges();
  }

  async function search(term: string, results: unknown[]): Promise<void> {
    const input = el.querySelector('input') as HTMLInputElement;
    input.value = term;
    input.dispatchEvent(new Event('input'));
    await vi.advanceTimersByTimeAsync(300);
    http.expectOne(`/api/products?q=${term}`).flush(results);
    await settle();
  }

  beforeEach(() => {
    vi.useFakeTimers();
    TestBed.configureTestingModule({ providers: [provideHttpClient(), provideHttpClientTesting()] });
    http = TestBed.inject(HttpTestingController);
    fixture = TestBed.createComponent(ProductBrowser);
    el = fixture.nativeElement;
    fixture.detectChanges();
  });

  afterEach(() => {
    http.verify();
    vi.useRealTimers();
  });

  it('bez wyboru resource jest idle i nie wysyła żądania', () => {
    expect(el.textContent).toContain('Nic nie wybrano.');
    http.expectNone((r) => r.url.startsWith('/api/products/'));
  });

  it('po wyszukaniu linkedSignal wybiera pierwszy produkt, a httpResource pobiera jego szczegóły', async () => {
    await search('a', [P(1), P(2)]);
    expect(el.textContent).toContain('Pobieram szczegóły');
    http.expectOne('/api/products/1').flush(D(1));
    await settle();
    expect(el.textContent).toContain('Opis 1');
  });

  it('zachowuje zaznaczenie, gdy produkt nadal jest na liście; resetuje, gdy zniknął', async () => {
    await search('a', [P(1), P(2)]);
    http.expectOne('/api/products/1').flush(D(1));
    await settle();

    // Ręczny wybór (set na linkedSignal) -> nowe żądanie o szczegóły.
    (el.querySelectorAll('li button')[1] as HTMLButtonElement).click();
    await settle();
    http.expectOne('/api/products/2').flush(D(2));
    await settle();
    expect(el.textContent).toContain('Opis 2');

    // Nowa lista nadal zawiera id=2 -> zaznaczenie zostaje, brak nowego żądania o szczegóły.
    await search('ab', [P(2), P(3)]);
    http.expectNone((r) => r.url.startsWith('/api/products/'));

    // Nowa lista bez id=2 -> reset do pierwszego (3) -> resource sam wysyła nowe żądanie.
    await search('abc', [P(3)]);
    http.expectOne('/api/products/3').flush(D(3));
    await settle();
    expect(el.textContent).toContain('Opis 3');
  });
});
