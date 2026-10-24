import { Injectable } from '@angular/core';
import { Observable, throwError, timer } from 'rxjs';
import { map, mergeMap } from 'rxjs/operators';
import { Task } from './tasks.events';

/** Fałszywe API w pamięci: 200 ms opóźnienia; `failNext` wymusza błąd następnego wywołania. */
@Injectable({ providedIn: 'root' })
export class TasksApi {
  failNext = false;
  calls = 0;

  getAll(): Observable<Task[]> {
    this.calls++;
    return timer(200).pipe(
      mergeMap(() => {
        if (this.failNext) {
          this.failNext = false;
          return throwError(() => new Error('HTTP 500'));
        }
        return [0];
      }),
      map(() => [
        { id: 1, title: 'Przeczytać prasówkę', done: false },
        { id: 2, title: 'Odpalić testy', done: true },
      ]),
    );
  }
}
