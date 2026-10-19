import { Injectable, InjectionToken, PLATFORM_ID, TransferState, inject, makeStateKey } from '@angular/core';
import { isPlatformServer } from '@angular/common';

/** Czy wynik sprawdzenia kuponu ma jechać z serwera do przeglądarki w TransferState. */
export const USE_TRANSFER_STATE = new InjectionToken<boolean>('USE_TRANSFER_STATE', {
  providedIn: 'root',
  factory: () => true,
});

/** Opóźnienie "serwera" kuponów w ms (w testach mierzymy, że SSR na nie czeka). */
export const AVAILABILITY_LATENCY_MS = new InjectionToken<number>('AVAILABILITY_LATENCY_MS', {
  providedIn: 'root',
  factory: () => 200,
});

/**
 * Udawany backend: kod "TAKEN" jest zajęty. Zapisuje każde PRAWDZIWE zapytanie w `requests`
 * (trafienie w TransferState zapytaniem nie jest) - dzięki temu testy liczą, ile razy
 * walidacja poszła "na backend" osobno na serwerze i osobno w przeglądarce.
 */
@Injectable({ providedIn: 'root' })
export class AvailabilityApi {
  readonly requests: string[] = [];
  readonly cacheHits: string[] = [];

  private readonly transfer = inject(TransferState);
  private readonly useTransfer = inject(USE_TRANSFER_STATE);
  private readonly latency = inject(AVAILABILITY_LATENCY_MS);
  private readonly onServer = isPlatformServer(inject(PLATFORM_ID));

  async check(code: string, signal: AbortSignal): Promise<boolean> {
    const key = makeStateKey<boolean>(`coupon-taken:${code}`);
    if (this.useTransfer && !this.onServer && this.transfer.hasKey(key)) {
      this.cacheHits.push(code);
      return this.transfer.get(key, false);
    }
    this.requests.push(code);
    await new Promise<void>((resolve, reject) => {
      const timer = setTimeout(resolve, this.latency);
      signal.addEventListener('abort', () => {
        clearTimeout(timer);
        reject(signal.reason);
      });
    });
    const taken = code === 'TAKEN';
    if (this.useTransfer && this.onServer) {
      this.transfer.set(key, taken);
    }
    return taken;
  }
}
