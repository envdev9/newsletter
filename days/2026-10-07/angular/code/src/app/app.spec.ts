import { TestBed } from '@angular/core/testing';
import { App } from './app';

describe('App', () => {
  it('tworzy się i osadza stronę zadań', () => {
    const fixture = TestBed.createComponent(App);
    fixture.detectChanges();
    const compiled = fixture.nativeElement as HTMLElement;
    expect(compiled.querySelector('h1')?.textContent).toContain('Events');
    expect(compiled.querySelector('app-tasks-page #load')).toBeTruthy();
  });
});
