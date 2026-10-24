import { Location } from '@angular/common';
import { TestBed } from '@angular/core/testing';
import { provideRouter, Router, withComponentInputBinding } from '@angular/router';
import { RouterTestingHarness } from '@angular/router/testing';
import { describe, expect, it } from 'vitest';
import { ArticleDetail } from './article-detail';
import { routes } from './app.routes';

describe('router: resolver + withComponentInputBinding + @defer', () => {
  async function harness(): Promise<RouterTestingHarness> {
    TestBed.configureTestingModule({
      providers: [provideRouter(routes, withComponentInputBinding())],
    });
    return RouterTestingHarness.create();
  }

  it('wiąże param ścieżki i dane resolvera z input()-ami komponentu', async () => {
    const h = await harness();
    const cmp = await h.navigateByUrl('/articles/2', ArticleDetail);
    expect(cmp.id()).toBe('2'); // param ścieżki to ZAWSZE string
    expect(cmp.article().title).toBe('Signal store'); // z resolvera
    expect(cmp.tab()).toBeUndefined(); // brak query paramu
    expect(h.routeNativeElement?.textContent).toContain('Signal store');
  });

  it('nie renderuje komentarzy bez ?tab=comments', async () => {
    const h = await harness();
    await h.navigateByUrl('/articles/1', ArticleDetail);
    expect(h.routeNativeElement?.textContent).toContain('Pokaż komentarze');
    expect(h.routeNativeElement?.querySelector('.comments')).toBeNull();
  });

  it('query param ?tab=comments przełącza @defer i ładuje komponent komentarzy', async () => {
    const h = await harness();
    const cmp = await h.navigateByUrl('/articles/1?tab=comments', ArticleDetail);
    expect(cmp.tab()).toBe('comments');
    await new Promise((r) => setTimeout(r, 300)); // chunk @defer + opóźnienie serwisu (50 ms)
    h.detectChanges();
    const items = h.routeNativeElement?.querySelectorAll('.comments li') ?? [];
    expect(Array.from(items).map((li) => li.textContent)).toEqual([
      'Komentarz A do #1',
      'Komentarz B do #1',
    ]);
  });

  it('zmiana samego query paramu aktualizuje input tego samego komponentu (bez ponownego tworzenia)', async () => {
    const h = await harness();
    const cmp = await h.navigateByUrl('/articles/1', ArticleDetail);
    await TestBed.inject(Router).navigateByUrl('/articles/1?tab=comments');
    expect(cmp.tab()).toBe('comments');
    expect(h.routeDebugElement?.componentInstance).toBe(cmp);
  });

  it('resolver przekierowuje nieistniejący artykuł na /not-found (RedirectCommand)', async () => {
    const h = await harness();
    await h.navigateByUrl('/articles/999');
    expect(TestBed.inject(Location).path()).toBe('/not-found');
    expect(h.routeNativeElement?.textContent).toContain('404');
  });

  it('resolver przekierowuje też nieliczbowy id', async () => {
    const h = await harness();
    await h.navigateByUrl('/articles/abc');
    expect(TestBed.inject(Location).path()).toBe('/not-found');
  });
});
