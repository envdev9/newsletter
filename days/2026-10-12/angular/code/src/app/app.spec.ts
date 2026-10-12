import { TestBed } from '@angular/core/testing';
import { App } from './app';

describe('App', () => {
  it('tworzy się i osadza formularz SKU', async () => {
    await TestBed.configureTestingModule({ imports: [App] }).compileComponents();
    const fixture = TestBed.createComponent(App);
    fixture.detectChanges();
    const el = fixture.nativeElement as HTMLElement;
    expect(el.querySelector('h1')?.textContent).toContain('debounce');
    expect(el.querySelector('app-sku-form app-sku-input input')).toBeTruthy();
  });
});
