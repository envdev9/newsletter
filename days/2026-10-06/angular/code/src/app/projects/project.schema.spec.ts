import { provideHttpClient } from '@angular/common/http';
import { HttpTestingController, TestRequest, provideHttpClientTesting } from '@angular/common/http/testing';
import { signal } from '@angular/core';
import { TestBed } from '@angular/core/testing';
import { SchemaOrSchemaFn, form } from '@angular/forms/signals';
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';
import { ProjectModel, emptyProject, naiveProjectSchema, projectSchema } from './project.schema';

describe('validateHttp (schema projectSchema, bez DOM - tylko drzewo pól + HttpTestingController)', () => {
  let http: HttpTestingController;

  beforeEach(() => {
    vi.useFakeTimers();
    TestBed.configureTestingModule({ providers: [provideHttpClient(), provideHttpClientTesting()] });
    http = TestBed.inject(HttpTestingController);
  });

  afterEach(() => {
    vi.useRealTimers();
  });

  /**
   * `readFirst` odtwarza szablon: pole jest CZYTANE zanim użytkownik cokolwiek wpisze
   * (metadane walidatora są leniwe - patrz test "pierwsza wartość NIE jest debounce'owana").
   */
  function setup(schemaFn: SchemaOrSchemaFn<ProjectModel> = projectSchema, readFirst = true) {
    const model = signal<ProjectModel>(emptyProject());
    const f = TestBed.runInInjectionContext(() => form(model, schemaFn));
    if (readFirst) {
      f.name().errors();
    }
    return { model, f };
  }

  async function settle(ms = 0): Promise<void> {
    await vi.advanceTimersByTimeAsync(ms);
    TestBed.tick();
  }

  const all = (): TestRequest[] => http.match(() => true);
  const kinds = (f: ReturnType<typeof setup>['f']): string[] => f.name().errors().map((e) => e.kind);

  it('walidatory sync blokują HTTP: za krótka nazwa = zero requestów i brak pending', async () => {
    const { f } = setup();
    f.name().value.set('ab');
    await settle(1000);
    expect(all()).toHaveLength(0);
    expect(f.name().pending()).toBe(false);
    expect(kinds(f)).toEqual(['minLength']);
  });

  it('debounce: 4 szybkie zmiany => 1 request (naiwna wersja bez debounce: 4, z czego 3 anulowane)', async () => {
    const good = setup(projectSchema);
    for (const v of ['pra', 'pras', 'prase', 'prasow']) {
      good.f.name().value.set(v);
      await settle(100);
    }
    await settle(400);
    const goodReqs = all();
    expect(goodReqs.map((r) => r.request.urlWithParams)).toEqual(['/api/projects/exists?name=prasow']);
    expect(goodReqs.filter((r) => r.cancelled)).toHaveLength(0);

    const naive = setup(naiveProjectSchema);
    for (const v of ['pra', 'pras', 'prase', 'prasow']) {
      naive.f.name().value.set(v);
      await settle(100);
    }
    await settle(400);
    const naiveReqs = all();
    expect(naiveReqs).toHaveLength(4);
    expect(naiveReqs.filter((r) => r.cancelled)).toHaveLength(3);
  });

  it('pending() jest true już w oknie debounce, ZANIM poleci pierwszy request', async () => {
    const { f } = setup();
    f.name().value.set('pra');
    await settle(100);
    expect(all()).toHaveLength(0);
    expect(f.name().pending()).toBe(true);
    expect(f.name().valid()).toBe(false);
  });

  it('PUŁAPKA: pierwsza wartość NIE jest debounce\'owana, jeśli pole nie było wcześniej czytane', async () => {
    const { f } = setup(projectSchema, false); // brak f.name().errors() przed set()
    f.name().value.set('pra');
    await settle(0);
    expect(all().map((r) => r.request.urlWithParams)).toEqual(['/api/projects/exists?name=pra']);
    expect(f.name().pending()).toBe(true);
  });

  it('zajęta nazwa: onSuccess mapuje odpowiedź na błąd z sugestią', async () => {
    const { f } = setup();
    f.name().value.set('prasowka');
    await settle(300);
    http.expectOne('/api/projects/exists?name=prasowka').flush({ taken: true, suggestion: 'prasowka-2' });
    await settle();
    expect(kinds(f)).toEqual(['taken']);
    expect(f.name().errors()[0].message).toContain('prasowka-2');
    expect(f.name().valid()).toBe(false);
    expect(f.name().pending()).toBe(false);
  });

  it('wolna nazwa: pole staje się valid', async () => {
    const { f } = setup();
    f.name().value.set('nowy-projekt');
    await settle(300);
    http.expectOne('/api/projects/exists?name=nowy-projekt').flush({ taken: false });
    await settle();
    expect(f.name().errors()).toEqual([]);
    expect(f.name().valid()).toBe(true);
  });

  it('błąd HTTP 500: onError mapuje na check-failed, a następna zmiana wartości naprawia stan', async () => {
    const { f } = setup();
    f.name().value.set('boom');
    await settle(300);
    http.expectOne('/api/projects/exists?name=boom').flush('x', { status: 500, statusText: 'Server Error' });
    await settle();
    expect(kinds(f)).toEqual(['check-failed']);

    f.name().value.set('inna');
    await settle(300);
    http.expectOne('/api/projects/exists?name=inna').flush({ taken: false });
    await settle();
    expect(f.name().valid()).toBe(true);
  });

  it('when: offline=true wyłącza sprawdzanie (zero requestów), offline=false je włącza', async () => {
    const { f } = setup();
    f.offline().value.set(true);
    f.name().value.set('prasowka');
    await settle(1000);
    expect(all()).toHaveLength(0);
    expect(f.name().valid()).toBe(true);

    f.offline().value.set(false);
    await settle(300);
    http.expectOne('/api/projects/exists?name=prasowka').flush({ taken: true, suggestion: 'prasowka-2' });
    await settle();
    expect(kinds(f)).toEqual(['taken']);
  });

  it('request jako {url, params} koduje znaki specjalne; ręczne sklejanie stringa - nie', async () => {
    const good = setup(projectSchema);
    good.f.name().value.set('Ala & Ola');
    await settle(300);
    expect(all().map((r) => r.request.urlWithParams)).toEqual(['/api/projects/exists?name=Ala%20%26%20Ola']);

    const naive = setup(naiveProjectSchema);
    naive.f.name().value.set('Ala & Ola');
    await settle(300);
    expect(all().map((r) => r.request.urlWithParams)).toEqual(['/api/projects/exists?name=Ala & Ola']);
  });

  it('zmiana wartości w trakcie requestu anuluje stary request - spóźniona odpowiedź nie nadpisze wyniku', async () => {
    const { f } = setup();
    f.name().value.set('prasowka');
    await settle(300);
    const first = http.expectOne('/api/projects/exists?name=prasowka');

    f.name().value.set('wolna-nazwa');
    await settle(300);
    const second = http.expectOne('/api/projects/exists?name=wolna-nazwa');
    expect(first.cancelled).toBe(true);

    second.flush({ taken: false });
    await settle();
    expect(f.name().valid()).toBe(true);
  });
});
