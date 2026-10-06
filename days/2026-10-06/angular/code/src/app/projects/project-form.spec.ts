import { provideHttpClient } from '@angular/common/http';
import { HttpTestingController, provideHttpClientTesting } from '@angular/common/http/testing';
import { ComponentFixture, TestBed } from '@angular/core/testing';
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';
import { ProjectForm } from './project-form';

describe('ProjectForm (validateHttp w szablonie)', () => {
  let fixture: ComponentFixture<ProjectForm>;
  let el: HTMLElement;
  let http: HttpTestingController;

  async function settle(ms = 0): Promise<void> {
    fixture.detectChanges();
    await vi.advanceTimersByTimeAsync(ms);
    fixture.detectChanges();
  }

  function type(value: string): void {
    const input = el.querySelector('#name') as HTMLInputElement;
    input.value = value;
    input.dispatchEvent(new Event('input'));
  }

  beforeEach(() => {
    vi.useFakeTimers();
    TestBed.configureTestingModule({ providers: [provideHttpClient(), provideHttpClientTesting()] });
    fixture = TestBed.createComponent(ProjectForm);
    el = fixture.nativeElement;
    http = TestBed.inject(HttpTestingController);
    fixture.detectChanges();
  });

  afterEach(() => {
    vi.useRealTimers();
  });

  it('pokazuje "Sprawdzam..." w oknie debounce, potem błąd zajętej nazwy', async () => {
    type('prasowka');
    await settle(100);
    expect(el.textContent).toContain('Sprawdzam unikalność');
    expect(http.match(() => true)).toHaveLength(0);

    await settle(200);
    http.expectOne('/api/projects/exists?name=prasowka').flush({ taken: true, suggestion: 'prasowka-2' });
    await settle();
    expect(el.textContent).not.toContain('Sprawdzam unikalność');
    expect(el.textContent).toContain('Nazwa jest zajęta - spróbuj "prasowka-2"');
  });

  it('wolna nazwa: komunikat "Nazwa wolna."', async () => {
    type('nowy-projekt');
    await settle(300);
    http.expectOne('/api/projects/exists?name=nowy-projekt').flush({ taken: false });
    await settle();
    expect(el.textContent).toContain('Nazwa wolna.');
  });
});
