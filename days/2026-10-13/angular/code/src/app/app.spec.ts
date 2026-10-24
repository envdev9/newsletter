import { TestBed } from '@angular/core/testing';
import { App } from './app';

describe('App', () => {
  it('tworzy się i osadza formularz ustawień', async () => {
    await TestBed.configureTestingModule({ imports: [App] }).compileComponents();
    const fixture = TestBed.createComponent(App);
    fixture.detectChanges();
    const el = fixture.nativeElement as HTMLElement;
    expect(el.querySelector('h1')?.textContent).toContain('FormCheckboxControl');
    expect(el.querySelector('app-settings-form app-consent-toggle button')).toBeTruthy();
    expect(el.querySelector('app-settings-form app-star-rating button')).toBeTruthy();
  });
});
