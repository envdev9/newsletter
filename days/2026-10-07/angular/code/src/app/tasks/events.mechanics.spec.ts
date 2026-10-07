import { Component, inject } from '@angular/core';
import { TestBed } from '@angular/core/testing';
import { patchState, signalStore, withState } from '@ngrx/signals';
import {
  Dispatcher,
  Events,
  event,
  on,
  provideDispatcher,
  withEventHandlers,
  withReducer,
} from '@ngrx/signals/events';
import { config as rxjsConfig, map, switchMap, tap, throwError } from 'rxjs';

const ping = event('[Test] ping');
const pong = event('[Test] pong');
const boom = event('[Test] boom');

describe('Mechanika @ngrx/signals/events (pomiary na gołych store)', () => {
  const unhandled: unknown[] = [];

  beforeEach(() => {
    vi.useFakeTimers();
    unhandled.length = 0;
    rxjsConfig.onUnhandledError = (e) => unhandled.push(e);
  });
  afterEach(() => {
    rxjsConfig.onUnhandledError = null;
    vi.useRealTimers();
  });

  it('kolejność: reduktory dostają zdarzenie PRZED efektami (efekt widzi już nowy stan)', () => {
    const seen: number[] = [];
    const S = signalStore(
      { providedIn: 'root' },
      withState({ count: 0 }),
      withReducer(on(ping, (_, s) => ({ count: s.count + 1 }))),
      withEventHandlers((store, events = inject(Events)) => ({
        h$: events.on(ping).pipe(tap(() => seen.push(store.count()))),
      })),
    );
    TestBed.inject(S);
    TestBed.inject(Dispatcher).dispatch(ping());
    expect(seen).toEqual([1]); // efekt odpalił się też synchronicznie, już po reduktorze
  });

  it('kolejność zagnieżdżona: zdarzenie zwrócone przez efekt czeka, aż reszta handlerów dostanie bieżące (queueScheduler)', () => {
    const order: string[] = [];
    const S = signalStore(
      { providedIn: 'root' },
      withEventHandlers((_, events = inject(Events)) => ({
        h1$: events.on(ping).pipe(
          tap(() => order.push('h1 widzi ping')),
          map(() => pong()), // zwrócone zdarzenie jest dispatchowane
        ),
        h2$: events.on(ping).pipe(tap(() => order.push('h2 widzi ping'))),
        h3$: events.on(pong).pipe(tap(() => order.push('h3 widzi pong'))),
      })),
    );
    TestBed.inject(S);
    TestBed.inject(Dispatcher).dispatch(ping());
    expect(order).toEqual(['h1 widzi ping', 'h2 widzi ping', 'h3 widzi pong']);
  });

  it('strażnik pętli: efekt, który zwraca to samo zdarzenie z events.on(), NIE wywołuje się w kółko', () => {
    let calls = 0;
    const S = signalStore(
      { providedIn: 'root' },
      withEventHandlers((_, events = inject(Events)) => ({
        h$: events.on(ping).pipe(tap(() => calls++)), // emituje ping dalej, ale nie jest ponownie dispatchowany
      })),
    );
    TestBed.inject(S);
    TestBed.inject(Dispatcher).dispatch(ping());
    expect(calls).toBe(1);
  });

  it('HACZYK: efekt bez catchError umiera na zawsze po pierwszym błędzie (i błąd leci do onUnhandledError)', async () => {
    let started = 0;
    const S = signalStore(
      { providedIn: 'root' },
      withEventHandlers((_, events = inject(Events)) => ({
        h$: events.on(boom).pipe(
          switchMap(() => {
            started++;
            return throwError(() => new Error('padło'));
          }),
        ),
      })),
    );
    TestBed.inject(S);
    const d = TestBed.inject(Dispatcher);

    d.dispatch(boom());
    await vi.advanceTimersByTimeAsync(0);
    d.dispatch(boom());
    d.dispatch(boom());
    await vi.advanceTimersByTimeAsync(0);

    expect(started).toBe(1); // kolejne boom() są ignorowane
    expect(unhandled.map((e) => (e as Error).message)).toEqual(['padło']);
  });

  it('HACZYK: wyjątek w reduktorze zabija reduktory tego store, ale NIE jego efekty (osobne subskrypcje)', async () => {
    let handlerCalls = 0;
    const S = signalStore(
      { providedIn: 'root' },
      withState({ n: 0 }),
      withReducer(
        on(boom, () => {
          throw new Error('reduktor padł');
        }),
        on(ping, (_, s) => ({ n: s.n + 1 })),
      ),
      withEventHandlers((_, events = inject(Events)) => ({
        h$: events.on(ping, boom).pipe(tap(() => handlerCalls++)),
      })),
    );
    const store = TestBed.inject(S);
    const d = TestBed.inject(Dispatcher);

    d.dispatch(ping());
    expect(store.n()).toBe(1);

    d.dispatch(boom());
    await vi.advanceTimersByTimeAsync(0);
    d.dispatch(ping());
    await vi.advanceTimersByTimeAsync(0);

    expect(store.n()).toBe(1); // reduktor martwy: drugi ping nie zwiększył n
    expect(handlerCalls).toBe(3); // efekt żyje: ping, boom, ping
    expect(unhandled.map((e) => (e as Error).message)).toEqual(['reduktor padł']);
  });

  it('po zniszczeniu store (takeUntilDestroyed) efekt nie reaguje', () => {
    let calls = 0;
    const Local = signalStore(
      withEventHandlers((_, events = inject(Events)) => ({
        h$: events.on(ping).pipe(tap(() => calls++)),
      })),
    );
    @Component({ selector: 'app-host', template: '', providers: [Local] })
    class Host {
      readonly store = inject(Local);
    }
    const fixture = TestBed.createComponent(Host);
    const d = TestBed.inject(Dispatcher);

    d.dispatch(ping());
    expect(calls).toBe(1);
    fixture.destroy();
    d.dispatch(ping());
    expect(calls).toBe(1);
  });

  it('zasięg: Dispatcher z provideDispatcher() jest lokalny; scope parent/global wypycha zdarzenie wyżej, a lokalni słuchacze widzą zdarzenia globalne', () => {
    @Component({ selector: 'app-scoped', template: '', providers: [provideDispatcher()] })
    class Scoped {
      readonly dispatcher = inject(Dispatcher);
      readonly events = inject(Events);
    }
    const globalSeen: string[] = [];
    const localSeen: string[] = [];
    TestBed.inject(Events).on(ping, pong).subscribe((e) => globalSeen.push('global:' + e.type));

    const c = TestBed.createComponent(Scoped).componentInstance;
    c.events.on(ping, pong).subscribe((e) => localSeen.push('local:' + e.type));

    c.dispatcher.dispatch(ping()); // domyślnie: tylko lokalnie
    expect(globalSeen).toEqual([]);
    expect(localSeen).toEqual(['local:[Test] ping']);

    c.dispatcher.dispatch(pong(), { scope: 'parent' }); // wyżej
    expect(globalSeen).toEqual(['global:[Test] pong']);

    TestBed.inject(Dispatcher).dispatch(ping()); // z globalnego: lokalny słuchacz też to widzi
    expect(globalSeen).toEqual(['global:[Test] pong', 'global:[Test] ping']);
    expect(localSeen).toContain('local:[Test] pong'); // pong poszedł w górę, ale wraca do lokalnych przez merge(parent.events$)
    expect(localSeen.filter((x) => x === 'local:[Test] ping').length).toBe(2);
  });

  it('patchState w efekcie (ręcznie) też działa - ale to omija reduktor; stan zmienia się bez zdarzenia', () => {
    const S = signalStore(
      { providedIn: 'root' },
      withState({ n: 0 }),
      withEventHandlers((store, events = inject(Events)) => ({
        h$: events.on(ping).pipe(tap(() => patchState(store, { n: 99 }))),
      })),
    );
    const s = TestBed.inject(S);
    TestBed.inject(Dispatcher).dispatch(ping());
    expect(s.n()).toBe(99);
  });
});
