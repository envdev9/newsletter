import { TestBed } from '@angular/core/testing';
import { App } from './app';

describe('App', () => {
  beforeEach(async () => {
    await TestBed.configureTestingModule({
      imports: [App],
    }).compileComponents();
  });

  it('tworzy się i osadza formularz zamówienia', () => {
    const fixture = TestBed.createComponent(App);
    fixture.detectChanges();
    const compiled = fixture.nativeElement as HTMLElement;
    expect(compiled.querySelector('h1')?.textContent).toContain('transformedValue');
    expect(compiled.querySelector('app-order-form')).toBeTruthy();
    expect(compiled.querySelector('form')).toBeTruthy();
  });
});
