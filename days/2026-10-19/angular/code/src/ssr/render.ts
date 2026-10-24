import { ApplicationRef, Provider } from '@angular/core';
import { BootstrapContext, bootstrapApplication } from '@angular/platform-browser';
import { provideServerRendering, renderApplication } from '@angular/platform-server';
import { App } from '../app/app';
import { appConfig } from '../app/app.config';
import { AvailabilityApi } from '../app/checkout/availability.api';

// Tokeny do sterowania renderem ze skryptu Node (scripts/ssr-check.mjs).
export { AVAILABILITY_LATENCY_MS, USE_TRANSFER_STATE } from '../app/checkout/availability.api';
export { DRAFT } from '../app/checkout/checkout.schema';

export const SHELL = '<!doctype html><html lang="pl"><head><meta charset="utf-8"><base href="/"></head><body><app-root></app-root></body></html>';

export interface Rendered {
  html: string;
  /** Zapytania, które na serwerze poszły "na backend" w czasie renderowania. */
  serverRequests: string[];
  elapsedMs: number;
}

/** Renderuje aplikację do stringa w czystym Node - bez Express, bez `@angular/ssr`. */
export async function render(extra: Provider[] = [], document: string = SHELL): Promise<Rendered> {
  let api!: AvailabilityApi; // referencja na obiekt przeżywa zniszczenie injectora po renderze
  const bootstrap = async (context: BootstrapContext): Promise<ApplicationRef> => {
    const appRef = await bootstrapApplication(
      App,
      { providers: [...appConfig.providers, provideServerRendering(), ...extra] },
      context,
    );
    api = appRef.injector.get(AvailabilityApi);
    return appRef;
  };
  const started = performance.now();
  const html = await renderApplication(bootstrap, { document, url: '/' });
  const elapsedMs = Math.round(performance.now() - started);
  return { html, serverRequests: [...api.requests], elapsedMs };
}
