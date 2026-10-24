import { TestBed } from '@angular/core/testing';
import { Dispatcher } from '@ngrx/signals/events';
import { ActivityLogStore } from './activity-log.store';
import { TasksApi } from './tasks.api';
import { tasksApiEvents, tasksPageEvents } from './tasks.events';
import { TasksStore } from './tasks.store';

describe('TasksStore + ActivityLogStore (zdarzenia -> reduktory -> efekty)', () => {
  beforeEach(() => vi.useFakeTimers());
  afterEach(() => vi.useRealTimers());

  it('reduktor działa SYNCHRONICZNIE: stan zmienia się zaraz po dispatch()', () => {
    const store = TestBed.inject(TasksStore);
    TestBed.inject(Dispatcher).dispatch(tasksPageEvents.added('Kupić chleb'));
    expect(store.tasks()).toEqual([{ id: 1, title: 'Kupić chleb', done: false }]);
  });

  it('dwa store reagują na to samo zdarzenie, nie znając się nawzajem', async () => {
    const tasks = TestBed.inject(TasksStore);
    const log = TestBed.inject(ActivityLogStore);
    const dispatcher = TestBed.inject(Dispatcher);

    dispatcher.dispatch(tasksPageEvents.opened());
    expect(tasks.loading()).toBe(true);

    await vi.advanceTimersByTimeAsync(200);
    expect(tasks.loading()).toBe(false);
    expect(tasks.tasks().length).toBe(2);
    expect(tasks.doneCount()).toBe(1);
    expect(log.log()).toEqual(['[Tasks Page] opened', '[Tasks API] loadedSuccess']);
  });

  it('błąd API -> loadedFailure; catchError WEWNĄTRZ switchMap: kolejne opened znów działa', async () => {
    const tasks = TestBed.inject(TasksStore);
    const api = TestBed.inject(TasksApi);
    const dispatcher = TestBed.inject(Dispatcher);

    api.failNext = true;
    dispatcher.dispatch(tasksPageEvents.opened());
    await vi.advanceTimersByTimeAsync(200);
    expect(tasks.error()).toBe('HTTP 500');
    expect(tasks.loading()).toBe(false);

    dispatcher.dispatch(tasksPageEvents.opened());
    await vi.advanceTimersByTimeAsync(200);
    expect(tasks.error()).toBeNull();
    expect(tasks.tasks().length).toBe(2);
    expect(api.calls).toBe(2);
  });

  it('switchMap w efekcie: drugie opened anuluje pierwsze (jedno loadedSuccess)', async () => {
    const log = TestBed.inject(ActivityLogStore);
    TestBed.inject(TasksStore);
    const dispatcher = TestBed.inject(Dispatcher);

    dispatcher.dispatch(tasksPageEvents.opened());
    await vi.advanceTimersByTimeAsync(100);
    dispatcher.dispatch(tasksPageEvents.opened());
    await vi.advanceTimersByTimeAsync(300);

    expect(log.log().filter((t) => t === tasksApiEvents.loadedSuccess.type).length).toBe(1);
    expect(TestBed.inject(TasksApi).calls).toBe(2);
  });

  it('HACZYK: store jest leniwy - zdarzenia sprzed pierwszego inject() przepadają (brak replay)', () => {
    const dispatcher = TestBed.inject(Dispatcher);
    dispatcher.dispatch(tasksPageEvents.added('przed utworzeniem store'));

    const tasks = TestBed.inject(TasksStore);
    const log = TestBed.inject(ActivityLogStore);
    expect(tasks.tasks()).toEqual([]);
    expect(log.log()).toEqual([]);

    dispatcher.dispatch(tasksPageEvents.added('po utworzeniu'));
    expect(tasks.tasks().length).toBe(1);
    expect(log.log().length).toBe(1);
  });
});
