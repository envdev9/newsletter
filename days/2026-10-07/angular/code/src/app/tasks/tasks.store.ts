import { computed, inject } from '@angular/core';
import { signalStore, withComputed, withState } from '@ngrx/signals';
import { Events, on, withEventHandlers, withReducer } from '@ngrx/signals/events';
import { catchError, map, of, switchMap } from 'rxjs';
import { TasksApi } from './tasks.api';
import { Task, tasksApiEvents, tasksPageEvents } from './tasks.events';

interface TasksState {
  tasks: Task[];
  loading: boolean;
  error: string | null;
}

export const TasksStore = signalStore(
  { providedIn: 'root' },
  withState<TasksState>({ tasks: [], loading: false, error: null }),
  withComputed(({ tasks }) => ({
    doneCount: computed(() => tasks().filter((t) => t.done).length),
  })),
  // Reduktory: czysta funkcja (zdarzenie, stan) -> patch. Bez wstrzykiwania, bez I/O.
  withReducer(
    on(tasksPageEvents.opened, () => ({ loading: true, error: null })),
    on(tasksApiEvents.loadedSuccess, ({ payload }) => ({ tasks: payload, loading: false })),
    on(tasksApiEvents.loadedFailure, ({ payload }) => ({ error: payload, loading: false })),
    on(tasksPageEvents.added, ({ payload }, state) => ({
      tasks: [...state.tasks, { id: state.tasks.length + 1, title: payload, done: false }],
    })),
    on(tasksPageEvents.toggled, ({ payload }, state) => ({
      tasks: state.tasks.map((t) => (t.id === payload ? { ...t, done: !t.done } : t)),
    })),
  ),
  // Efekty uboczne: strumień zdarzeń -> I/O -> nowe zdarzenia. catchError WEWNĄTRZ switchMap.
  withEventHandlers((_, events = inject(Events), api = inject(TasksApi)) => ({
    load$: events.on(tasksPageEvents.opened).pipe(
      switchMap(() =>
        api.getAll().pipe(
          map((tasks) => tasksApiEvents.loadedSuccess(tasks)),
          catchError((e: Error) => of(tasksApiEvents.loadedFailure(e.message))),
        ),
      ),
    ),
  })),
);
