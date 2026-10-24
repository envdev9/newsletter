import { TestBed } from '@angular/core/testing';
import { App } from './app';

describe('App', () => {
  it('tworzy się i osadza formularz rejestracji', async () => {
    await TestBed.configureTestingModule({ imports: [App] }).compileComponents();
    const fixture = TestBed.createComponent(App);
    fixture.detectChanges();
    const el = fixture.nativeElement as HTMLElement;
    expect(el.querySelector('h1')?.textContent).toContain('reset()');
    expect(el.querySelector('app-signup-form app-code-input input')).toBeTruthy();
    expect(el.querySelector('#naive')).toBeTruthy();
    expect(el.querySelector('#safe')).toBeTruthy();
  });
});
