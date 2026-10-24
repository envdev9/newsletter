import { type } from '@ngrx/signals';
import { eventGroup } from '@ngrx/signals/events';

export interface Task {
  id: number;
  title: string;
  done: boolean;
}

/** Zdarzenia z UI - "co się stało", a nie "co zrobić". */
export const tasksPageEvents = eventGroup({
  source: 'Tasks Page',
  events: {
    opened: type<void>(),
    added: type<string>(),
    toggled: type<number>(),
  },
});

/** Zdarzenia z "API" (wynik efektu ubocznego). */
export const tasksApiEvents = eventGroup({
  source: 'Tasks API',
  events: {
    loadedSuccess: type<Task[]>(),
    loadedFailure: type<string>(),
  },
});
