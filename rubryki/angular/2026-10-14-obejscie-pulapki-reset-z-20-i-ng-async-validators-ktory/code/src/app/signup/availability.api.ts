import { Injectable } from '@angular/core';

/**
 * Udawany "serwer": sprawdza, czy kod promocyjny jest zajęty. Zajęty jest tylko kod "TAKEN".
 * Odpowiada po 200 ms (setTimeout - w testach fake timery) i zapisuje każde zapytanie,
 * żeby testy mogły policzyć, ile razy walidator naprawdę "poszedł do serwera".
 */
@Injectable({ providedIn: 'root' })
export class AvailabilityApi {
  readonly requests: string[] = [];

  check(code: string, abort?: AbortSignal): Promise<boolean> {
    this.requests.push(code);
    return new Promise<boolean>((resolve, reject) => {
      const id = setTimeout(() => resolve(code === 'TAKEN'), 200);
      abort?.addEventListener(
        'abort',
        () => {
          clearTimeout(id);
          reject(new DOMException('aborted', 'AbortError'));
        },
        { once: true },
      );
    });
  }
}
