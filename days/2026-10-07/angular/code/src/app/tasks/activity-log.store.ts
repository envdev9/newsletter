import { signalStore, withState } from '@ngrx/signals';
import { Events, withEventHandlers } from '@ngrx/signals/events';
import { inject } from '@angular/core';
import { tap } from 'rxjs';
import { patchState } from '@ngrx/signals';

/**
 * Drugi store, który NIE importuje TasksStore - zna tylko zdarzenia.
 * Loguje typy wszystkich zdarzeń (events.on() bez argumentów = wszystko).
 */
export const ActivityLogStore = signalStore(
  { providedIn: 'root' },
  withState<{ log: string[] }>({ log: [] }),
  withEventHandlers((store, events = inject(Events)) => ({
    record$: events.on().pipe(
      tap(({ type }) => patchState(store, (s) => ({ log: [...s.log, type] }))),
    ),
  })),
);
