import { provideHttpClient } from '@angular/common/http';
import { HttpTestingController, TestRequest, provideHttpClientTesting } from '@angular/common/http/testing';
import { Component, signal } from '@angular/core';
import { ComponentFixture, TestBed } from '@angular/core/testing';
import { FormField, SchemaOrSchemaFn, debounce, form, schema, submit } from '@angular/forms/signals';
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';
import {
  DebouncerCall,
  HttpDebounceCall,
  ProjectModel,
  blurSchema,
  customDebouncerSchema,
  emptyProject,
  httpDebounceFnSchema,
  requestDebounceSchema,
  uiDebounceSchema,
} from './project.schema';

/** Host z prawdziwymi <input> - zapis z UI idzie przez `controlValue` (to tam działa reguła `debounce()`). */
function makeHost(schemaFn: SchemaOrSchemaFn<ProjectModel>) {
  @Component({
    selector: 'test-host',
    imports: [FormField],
    template: `
      <input id="name" type="text" [formField]="f.name" />
      <input id="offline" type="checkbox" [formField]="f.offline" />
    `,
  })
  class Host {
    readonly model = signal<ProjectModel>(emptyProject());
    readonly f = form(this.model, schemaFn);
  }
  return Host;
}

describe('debounce() na polu vs debounce w validateHttp', () => {
  let http: HttpTestingController;

  beforeEach(() => {
    vi.useFakeTimers();
    TestBed.configureTestingModule({ providers: [provideHttpClient(), provideHttpClientTesting()] });
    http = TestBed.inject(HttpTestingController);
  });

  afterEach(() => {
    vi.useRealTimers();
  });

  function mount(schemaFn: SchemaOrSchemaFn<ProjectModel>) {
    const fixture: ComponentFixture<InstanceType<ReturnType<typeof makeHost>>> = TestBed.createComponent(
      makeHost(schemaFn),
    );
    fixture.detectChanges();
    const host = fixture.componentInstance;
    host.f.name().errors(); // czytamy pole przed pierwszą zmianą (patrz pułapka z #13)
    const input = fixture.nativeElement.querySelector('#name') as HTMLInputElement;
    return {
      fixture,
      host,
      input,
      type: (text: string) => {
        input.value = text;
        input.dispatchEvent(new Event('input'));
        fixture.detectChanges();
      },
      blur: () => {
        input.dispatchEvent(new Event('blur'));
        fixture.detectChanges();
      },
    };
  }

  async function settle(ms = 0): Promise<void> {
    await vi.advanceTimersByTimeAsync(ms);
    TestBed.tick();
  }

  const all = (): TestRequest[] => http.match(() => true);
  const urls = (reqs: TestRequest[]): string[] => reqs.map((r) => r.request.urlWithParams);

  it("debounce(pole, 'blur'): model i HTTP stoją w miejscu do utraty fokusu, ale dirty() jest już true", async () => {
    const m = mount(blurSchema);
    m.type('pra');
    m.type('pras');
    m.type('prasow');
    await settle(5000);
    expect(m.host.model().name).toBe('');
    expect(m.host.f.name().value()).toBe('');
    expect(m.host.f.name().dirty()).toBe(true);
    expect(m.host.f.name().touched()).toBe(false);
    expect(all()).toHaveLength(0);

    m.blur();
    await settle();
    expect(m.host.model().name).toBe('prasow');
    expect(m.host.f.name().touched()).toBe(true);
    expect(urls(all())).toEqual(['/api/projects/exists?name=prasow']);
  });

  it('debounce(pole, 300): 4 wpisy co 100 ms => model dostaje TYLKO ostatnią wartość, 1 request', async () => {
    const m = mount(uiDebounceSchema);
    for (const v of ['pra', 'pras', 'prase', 'prasow']) {
      m.type(v);
      await settle(100);
      expect(m.host.model().name).toBe('');
    }
    await settle(300);
    expect(m.host.model().name).toBe('prasow');
    expect(urls(all())).toEqual(['/api/projects/exists?name=prasow']);
  });

  it('dla porównania: debounce tylko na requeście - model zmienia się przy KAŻDYM znaku, HTTP czeka', async () => {
    const m = mount(requestDebounceSchema);
    const seen: string[] = [];
    for (const v of ['pra', 'pras', 'prase', 'prasow']) {
      m.type(v);
      seen.push(m.host.model().name);
      await settle(100);
    }
    expect(seen).toEqual(['pra', 'pras', 'prase', 'prasow']);
    expect(all()).toHaveLength(0);
    await settle(300);
    expect(urls(all())).toEqual(['/api/projects/exists?name=prasow']);
  });

  it('zapis programowy (value.set) OMIJA debounce pola - model zmienia się natychmiast', async () => {
    const m = mount(blurSchema);
    m.host.f.name().value.set('prasowka');
    expect(m.host.model().name).toBe('prasowka');
    await settle();
    expect(urls(all())).toEqual(['/api/projects/exists?name=prasowka']);
  });

  it('programowy zapis w trakcie oczekującego wpisu z UI kasuje ten wpis (blur nic nie dopisze)', async () => {
    const m = mount(blurSchema);
    m.type('abc');
    expect(m.host.model().name).toBe('');
    m.host.f.name().value.set('zzz');
    TestBed.tick();
    m.blur();
    await settle();
    expect(m.host.model().name).toBe('zzz');
  });

  it('reguła debounce na ROOT (korzeń formularza) obejmuje pola potomne', async () => {
    const rootSchema = schema<ProjectModel>((p) => {
      debounce(p, 'blur');
    });
    const m = mount(rootSchema);
    m.type('abc');
    await settle(2000);
    expect(m.host.model().name).toBe('');
    m.blur();
    expect(m.host.model().name).toBe('abc');
  });

  it('własny Debouncer: ctx.value() to wartość Z MODELU (opóźniona o jeden wpis), void = zapis od razu', async () => {
    const calls: DebouncerCall[] = [];
    const m = mount(customDebouncerSchema(calls));

    m.type('abcd'); // model pusty => ctx.value().length < 2 => void => zapis natychmiast
    expect(m.host.model().name).toBe('abcd');
    expect(calls.map((c) => c.modelValue)).toEqual(['']);

    m.type('abcde'); // model 'abcd' => czeka 300 ms
    expect(m.host.model().name).toBe('abcd');
    await settle(100);
    m.type('abcdef'); // kolejny wpis ABORTUJE poprzedni debouncer
    expect(calls[1].aborted).toBe(true);
    expect(m.host.model().name).toBe('abcd');
    await settle(300);
    expect(m.host.model().name).toBe('abcdef');
    expect(calls.map((c) => c.modelValue)).toEqual(['', 'abcd', 'abcd']);
  });

  it('PUŁAPKA: submit() w trakcie oczekującego debounce waliduje STARY model (akcja nie rusza), a timer i tak dopisze wpis później', async () => {
    const m = mount(uiDebounceSchema);
    m.type('prasowka');
    expect(m.host.model().name).toBe('');
    const action = vi.fn(async () => undefined);
    await submit(m.host.f, action);
    expect(action).not.toHaveBeenCalled(); // 'required' na starym, pustym modelu
    expect(m.host.f.name().errors().map((e) => e.kind)).toEqual(['required']);
    expect(m.host.f.name().touched()).toBe(true);

    await settle(300); // debounce doleciał dopiero teraz
    expect(m.host.model().name).toBe('prasowka');
  });

  it('blur przed submitem (jak realny klik w przycisk) domyka wpis - model aktualny, a submit idzie', async () => {
    const m = mount(blurSchema);
    m.type('nowy-projekt');
    m.blur();
    await settle();
    http.expectOne('/api/projects/exists?name=nowy-projekt').flush({ taken: false });
    await settle();
    const action = vi.fn(async () => undefined);
    await submit(m.host.f, action);
    expect(action).toHaveBeenCalledTimes(1);
  });

  describe('validateHttp: request => undefined', () => {
    it('offline: zero requestów, pending=false, valid=true', async () => {
      const m = mount(blurSchema);
      m.host.f.offline().value.set(true);
      m.host.f.name().value.set('prasowka');
      await settle(1000);
      expect(all()).toHaveLength(0);
      expect(m.host.f.name().pending()).toBe(false);
      expect(m.host.f.name().valid()).toBe(true);
    });

    it('przełączenie na offline w trakcie requestu: pending znika od razu, request NIE jest anulowany, spóźniona odpowiedź jest ignorowana', async () => {
      const m = mount(blurSchema);
      m.host.f.name().value.set('prasowka');
      await settle();
      const req = http.expectOne('/api/projects/exists?name=prasowka');
      expect(m.host.f.name().pending()).toBe(true);

      m.host.f.offline().value.set(true);
      await settle();
      expect(m.host.f.name().pending()).toBe(false);
      expect(m.host.f.name().valid()).toBe(true);
      expect(req.cancelled).toBe(false); // zmierzone: inaczej niż przy zmianie wartości (tam cancelled=true)

      req.flush({ taken: true, suggestion: 'prasowka-2' });
      await settle();
      expect(m.host.f.name().errors()).toEqual([]);
      expect(m.host.f.name().valid()).toBe(true);
    });

    it('powrót do online ponownie wysyła request', async () => {
      const m = mount(blurSchema);
      m.host.f.offline().value.set(true);
      m.host.f.name().value.set('prasowka');
      await settle(500);
      expect(all()).toHaveLength(0);
      m.host.f.offline().value.set(false);
      await settle();
      expect(urls(all())).toEqual(['/api/projects/exists?name=prasowka']);
    });
  });

  describe('validateHttp: debounce jako funkcja', () => {
    it('leading + trailing: pierwszy wpis po przerwie leci od razu, seria - po 300 ms; snapshot nigdy nie jest "idle"', async () => {
      const calls: HttpDebounceCall[] = [];
      const m = mount(httpDebounceFnSchema(calls));

      m.host.f.name().value.set('abc'); // pierwszy wpis: leading => void => od razu
      await settle();
      expect(urls(all())).toEqual(['/api/projects/exists?name=abc']);

      await settle(100);
      m.host.f.name().value.set('abcd'); // w serii: czeka 300 ms
      await settle(200);
      expect(all()).toHaveLength(0);
      m.host.f.name().value.set('abcde'); // kolejny wpis w oknie debounce
      await settle(300);
      expect(urls(all())).toEqual(['/api/projects/exists?name=abcde']);

      await settle(2000); // przerwa > 1 s => znów leading
      m.host.f.name().value.set('abcdef');
      await settle();
      expect(urls(all())).toEqual(['/api/projects/exists?name=abcdef']);

      expect(calls.map((c) => c.status)).toEqual(['resolved', 'resolved', 'loading', 'resolved']);
      expect(calls[0].request).toEqual({ url: '/api/projects/exists', params: { name: 'abc' } });
    });
  });
});
