import { ErrorHandler } from '@angular/core';
import { EffectsErrorHandler } from '@ngrx/effects';
import { Action } from '@ngrx/store';
import { EMPTY, Observable, catchError, switchMap, timer } from 'rxjs';

export interface ErrorPolicyOptions {
  /** Ile razy wolno ponowić subskrypcję efektu po błędzie (domyślny strażnik NgRx: 10). */
  maxRetries: number;
  /** Bazowe opóźnienie przed ponowieniem; kolejne próby: base * 2^n. 0 = ponów synchronicznie. */
  baseDelayMs: number;
  /** Wołane RAZ, gdy limit wyczerpany i efekt kończy się na dobre (domyślny strażnik NgRx milczy). */
  onDied: (error: unknown) => void;
}

/**
 * Własny EFFECTS_ERROR_HANDLER. Różnice względem `defaultEffectsErrorHandler`:
 *  - KAŻDY błąd trafia do ErrorHandler (domyślny: 10 z 11 - ostatni znika po cichu),
 *  - po wyczerpaniu limitu jest jawny sygnał `onDied`,
 *  - opcjonalny backoff (okno, w którym efekt NIE nasłuchuje - akcje z tego okna przepadają).
 */
export function createErrorPolicy(options: ErrorPolicyOptions): EffectsErrorHandler {
  return function handler<T extends Action>(source$: Observable<T>, errorHandler: ErrorHandler, attempt = 0): Observable<T> {
    return source$.pipe(
      catchError((error) => {
        errorHandler.handleError(error);
        if (attempt >= options.maxRetries) {
          options.onDied(error);
          return EMPTY;
        }
        if (options.baseDelayMs === 0) return handler(source$, errorHandler, attempt + 1);
        return timer(options.baseDelayMs * 2 ** attempt).pipe(switchMap(() => handler(source$, errorHandler, attempt + 1)));
      }),
    );
  };
}
