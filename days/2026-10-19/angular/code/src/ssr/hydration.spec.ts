import { ApplicationRef, destroyPlatform } from '@angular/core';
import { bootstrapApplication } from '@angular/platform-browser';
import { App } from '../app/app';
import { appConfig } from '../app/app.config';
import { AVAILABILITY_LATENCY_MS, AvailabilityApi } from '../app/checkout/availability.api';
import { loadFixture } from './fixtures';

const measure = (name: string, value: unknown) => console.log(`MEASURE ${name}: ${JSON.stringify(value)}`);
const sleep = (ms: number) => new Promise((r) => setTimeout(r, ms));

/** Wkleja HTML z serwera do jsdom tak, jak zrobiłaby to przeglądarka po odebraniu odpowiedzi. */
function loadServerHtml(html: string): void {
  const parsed = new DOMParser().parseFromString(html, 'text/html');
  document.body.innerHTML = parsed.body.innerHTML;
}

const text = (sel: string) => document.querySelector(sel)?.textContent ?? null;
const errors = () => Array.from(document.querySelectorAll('p.error')).map((p) => p.textContent);

describe('hydracja formularza HTML-em z prawdziwego SSR (jsdom)', () => {
  let appRef: ApplicationRef | undefined;
  let logSpy: { mock: { calls: unknown[][] }; mockRestore(): void };

  beforeEach(() => {
    destroyPlatform(); // TestBed zainicjował platformę testową - chcemy zwykłą platformę przeglądarkową
    logSpy = vi.spyOn(console, 'log');
  });

  afterEach(() => {
    appRef?.destroy();
    appRef = undefined;
    destroyPlatform();
    logSpy.mockRestore();
    document.body.innerHTML = '';
  });

  const boot = async () => {
    appRef = await bootstrapApplication(App, {
      providers: [...appConfig.providers, { provide: AVAILABILITY_LATENCY_MS, useValue: 10 }],
    });
    return appRef;
  };

  it('hydracja ponownie używa węzłów DOM z serwera', async () => {
    loadServerHtml(loadFixture('taken'));
    const before = document.querySelector('#code');
    const app = await boot();
    await app.whenStable();
    const same = document.querySelector('#code') === before;
    measure('dom-reuse-with-hydration', { sameNode: same });
    expect(same).toBe(true);
  });

  it('kontrola: bez znacznika ngh (HTML nie z SSR) węzły są tworzone od nowa', async () => {
    // Kontrola przez pominięcie `provideClientHydration()` nie zadziałała w jednym procesie testowym:
    // aplikacja bez hydracji, odpalona po hydratowanej, rzuciła NG0500 (stan hydracji wygląda na
    // globalny w procesie - to wniosek z objawu, nie z kodu). Stąd kontrola przez usunięcie
    // znaczników SSR: Angular loguje NG0505 i renderuje od zera.
    loadServerHtml(loadFixture('taken'));
    document.querySelector('app-root')!.removeAttribute('ngh');
    document.getElementById('ng-state')!.remove();
    const before = document.querySelector('#code');
    const app = await boot();
    await app.whenStable();
    const same = document.querySelector('#code') === before;
    measure('dom-reuse-without-ngh', { sameNode: same });
    expect(same).toBe(false);
  });

  it('Angular zgłasza zhydratowane komponenty i żadnego pominiętego', async () => {
    loadServerHtml(loadFixture('taken'));
    const app = await boot();
    await app.whenStable();
    const hydrationLog = logSpy.mock.calls.map((c) => String(c[0])).find((m) => m.includes('hydrated'));
    measure('hydration-log', hydrationLog?.split(' Learn more')[0] ?? null);
    expect(hydrationLog).toMatch(/Angular hydrated \d+ component\(s\) and \d+ node\(s\), 0 component\(s\) were skipped/);
  });

  it('z TransferState klient nie powtarza zapytania, a błąd jest widoczny od razu', async () => {
    loadServerHtml(loadFixture('taken'));
    const app = await boot();
    const api = app.injector.get(AvailabilityApi);
    const afterBootstrap = { errors: errors(), mode: text('#mode') };
    await app.whenStable();
    await sleep(50);
    measure('transfer-state-on', {
      afterBootstrap,
      afterStable: { errors: errors(), mode: text('#mode'), pending: !!document.querySelector('#pending') },
      clientRequests: api.requests,
      cacheHits: api.cacheHits,
    });
    expect(afterBootstrap.errors).toEqual(['Kod jest zajęty']);
    expect(text('#mode')).toBe('JS aktywny');
    expect(api.requests).toEqual([]);
    expect(api.cacheHits).toEqual(['TAKEN']);
    expect(errors()).toEqual(['Kod jest zajęty']);
  });

  it('bez TransferState ta sama walidacja idzie na backend drugi raz', async () => {
    loadServerHtml(loadFixture('taken-nocache'));
    const app = await boot();
    const api = app.injector.get(AvailabilityApi);
    await app.whenStable();
    await sleep(50);
    measure('transfer-state-off', { clientRequests: api.requests, cacheHits: api.cacheHits, errors: errors() });
    expect(api.requests).toEqual(['TAKEN']);
    expect(errors()).toEqual(['Kod jest zajęty']);
  });

  it('po hydracji formularz żyje: wpis FREE po debounce zdejmuje błąd i robi 1 zapytanie', async () => {
    loadServerHtml(loadFixture('taken'));
    const app = await boot();
    const api = app.injector.get(AvailabilityApi);
    await app.whenStable();
    const input = document.querySelector<HTMLInputElement>('#code')!;
    input.value = 'FREE';
    input.dispatchEvent(new Event('input', { bubbles: true }));
    await sleep(450); // debounce 300 ms + "serwer" 10 ms
    await app.whenStable();
    measure('after-hydration-typing', { errors: errors(), clientRequests: api.requests, value: input.value });
    expect(errors()).toEqual([]);
    expect(api.requests).toEqual(['FREE']);
  });

  it('PUŁAPKA: tekst wpisany przed hydracją jest nadpisywany wartością z modelu', async () => {
    loadServerHtml(loadFixture('free'));
    const input = document.querySelector<HTMLInputElement>('#name')!;
    input.value = 'Zofia'; // użytkownik zaczął pisać, zanim załadował się JS
    const app = await boot();
    await app.whenStable();
    await sleep(50);
    measure('typed-before-hydration', { domValueAfter: input.value, sameNode: document.querySelector('#name') === input });
    expect(document.querySelector('#name')).toBe(input);
    expect(input.value).toBe('Anna');
  });

  it('PUŁAPKA: atrybut name pola zmienia się po hydracji (licznik formularzy jest per proces)', async () => {
    const html = loadFixture('taken');
    const serverName = /id="code" name="([^"]*)"/.exec(html)![1];
    loadServerHtml(html);
    await boot();
    const afterName = document.querySelector<HTMLInputElement>('#code')!.getAttribute('name');
    measure('name-attr', { server: serverName, afterHydration: afterName });
    expect(serverName).toMatch(/^ng\.form\d+\.code$/);
    expect(afterName).toMatch(/^ng\.form\d+\.code$/);
  });
});
