import { provideHttpClient } from '@angular/common/http';
import { HttpTestingController, provideHttpClientTesting } from '@angular/common/http/testing';
import { EnvironmentProviders, ErrorHandler, Provider, inject } from '@angular/core';
import { TestBed } from '@angular/core/testing';
import { Actions, EFFECTS_ERROR_HANDLER, FunctionalEffect, createEffect, ofType, provideEffects } from '@ngrx/effects';
import { Action, Store, provideStore } from '@ngrx/store';
import { Observable, config, tap } from 'rxjs';
import { createErrorPolicy } from './effects-error-policy';
import { OrdersActions, leakyNoGuard, leakySearch, ordersReducer, pinger, safeSearch } from './orders.store';

const measure = (name: string, data: unknown) => console.log(`MEASURE ${name}: ${JSON.stringify(data)}`);
const BOOM = { status: 500, statusText: 'Server Error' };

type Effects = Record<string, FunctionalEffect>;

/**
 * Błąd bez obsługi w subskrypcji rxjs trafia do `config.onUnhandledError` (domyślnie: rzut w setTimeout,
 * czyli w przeglądarce do window.onerror). Tu go przechwytujemy, żeby Vitest nie uznał go za awarię przebiegu.
 */
const nextMacrotask = () => new Promise<void>((resolve) => setTimeout(resolve, 0));

function captureUnhandledRxjsErrors(): unknown[] {
  const captured: unknown[] = [];
  config.onUnhandledError = (e) => captured.push(e);
  return captured;
}

/** Efekt "tylko skutek uboczny" (dispatch:false), który rzuca przy `search`, i to BEZ strażnika. */
const silentNoGuard = createEffect(
  (actions$ = inject(Actions)) =>
    actions$.pipe(
      ofType(OrdersActions.search),
      tap(() => {
        throw new Error('skutek uboczny padl');
      }),
    ),
  { functional: true, dispatch: false, useEffectsErrorHandler: false },
);

function setup(effects: Effects, extra: (Provider | EnvironmentProviders)[] = []) {
  const handled: string[] = [];
  TestBed.configureTestingModule({
    providers: [
      provideHttpClient(),
      provideHttpClientTesting(),
      provideStore({ orders: ordersReducer }),
      provideEffects(effects),
      { provide: ErrorHandler, useValue: { handleError: (e: unknown) => handled.push(String((e as Error).message ?? e).slice(0, 40)) } },
      ...extra,
    ],
  });
  const http = TestBed.inject(HttpTestingController);
  const store = TestBed.inject(Store);
  const seen: string[] = [];
  TestBed.inject(Actions).subscribe((a) => seen.push(a.type));
  /** Wysyła `search`; zwraca żądania HTTP, które efekt faktycznie wyemitował (0 = nikt nie słucha). */
  const search = (query: string) => {
    store.dispatch(OrdersActions.search({ query }));
    return http.match((r) => r.url === '/api/orders');
  };
  const ping = () => {
    const before = seen.filter((t) => t === '[Orders] pong').length;
    store.dispatch(OrdersActions.ping());
    return seen.filter((t) => t === '[Orders] pong').length - before;
  };
  return { http, store, seen, handled, search, ping };
}

describe('EFFECTS_ERROR_HANDLER w @ngrx/effects', () => {
  afterEach(() => {
    config.onUnhandledError = null;
    vi.useRealTimers();
    TestBed.inject(HttpTestingController).verify();
  });

  it('domyślny strażnik: resubskrypcja ZERUJE stan w efekcie (scan), ErrorHandler dostaje błąd', () => {
    const h = setup({ leakySearch });
    const first = h.search('x');
    expect(first[0].request.params.get('q')).toBe('x#1');
    first[0].flush('boom', BOOM);
    const second = h.search('y');
    const third = h.search('z');
    measure('state-reset', {
      first: first[0].request.params.get('q'),
      afterError: second[0].request.params.get('q'),
      next: third[0].request.params.get('q'),
      handled: h.handled.length,
    });
    // gdyby efekt nie został zasubskrybowany od nowa, drugie zapytanie miałoby numer 2
    expect(second[0].request.params.get('q')).toBe('y#1');
    expect(third[0].request.params.get('q')).toBe('z#2');
    expect(second[0].cancelled).toBe(true); // switchMap anulował "y" po wysłaniu "z"
    third[0].flush([]);
  });

  it('domyślny strażnik: 10 błędów zgłoszonych, 11. znika po cichu, efekt martwy', () => {
    const h = setup({ leakySearch });
    let lastWithRequest = 0;
    const handledAfter: number[] = [];
    for (let i = 1; i <= 13; i++) {
      const reqs = h.search(`q${i}`);
      if (reqs.length === 0) break;
      lastWithRequest = i;
      reqs[0].flush('boom', BOOM);
      handledAfter.push(h.handled.length);
    }
    measure('default-limit', { lastWithRequest, handledAfter });
    expect(lastWithRequest).toBe(11);
    expect(handledAfter[10]).toBe(10); // 11. błąd: brak wpisu w ErrorHandler
  });

  it('własna polityka (maxRetries 3): KAŻDY błąd zgłoszony, onDied wołane raz, potem efekt martwy', () => {
    const died: unknown[] = [];
    const policy = createErrorPolicy({ maxRetries: 3, baseDelayMs: 0, onDied: (e) => died.push(e) });
    const h = setup({ leakySearch }, [{ provide: EFFECTS_ERROR_HANDLER, useValue: policy }]);
    let lastWithRequest = 0;
    const handledAfter: number[] = [];
    for (let i = 1; i <= 8; i++) {
      const reqs = h.search(`q${i}`);
      if (reqs.length === 0) break;
      lastWithRequest = i;
      reqs[0].flush('boom', BOOM);
      handledAfter.push(h.handled.length);
    }
    measure('custom-limit', { lastWithRequest, handledAfter, died: died.length });
    expect(lastWithRequest).toBe(4); // oryginał + 3 ponowienia
    expect(handledAfter).toEqual([1, 2, 3, 4]); // wszystkie 4 błędy zgłoszone
    expect(died.length).toBe(1);
  });

  it('backoff: w oknie oczekiwania efekt NIE nasłuchuje - akcje z okna przepadają (bez replay)', () => {
    vi.useFakeTimers();
    const policy = createErrorPolicy({ maxRetries: 3, baseDelayMs: 1000, onDied: () => {} });
    const h = setup({ leakySearch }, [{ provide: EFFECTS_ERROR_HANDLER, useValue: policy }]);
    h.search('x')[0].flush('boom', BOOM);
    const inWindow = h.search('w-okno');
    vi.advanceTimersByTime(999);
    const justBefore = h.search('tuz-przed');
    vi.advanceTimersByTime(1);
    const afterWindow = h.search('po-oknie');
    measure('backoff-window', {
      requestsInWindow: inWindow.length,
      justBefore: justBefore.length,
      afterWindow: afterWindow.length,
      qAfter: afterWindow[0]?.request.params.get('q'),
      handled: h.handled.length,
    });
    expect(inWindow.length).toBe(0);
    expect(justBefore.length).toBe(0);
    expect(afterWindow.length).toBe(1);
    afterWindow[0].flush([]);
  });

  it('backoff rośnie wykładniczo: 1 s, potem 2 s', () => {
    vi.useFakeTimers();
    const policy = createErrorPolicy({ maxRetries: 3, baseDelayMs: 1000, onDied: () => {} });
    const h = setup({ leakySearch }, [{ provide: EFFECTS_ERROR_HANDLER, useValue: policy }]);
    h.search('x')[0].flush('boom', BOOM);
    vi.advanceTimersByTime(1000);
    h.search('y')[0].flush('boom', BOOM); // 2. błąd -> okno 2000 ms
    vi.advanceTimersByTime(1999);
    const early = h.search('za-wczesnie').length;
    vi.advanceTimersByTime(1);
    const ok = h.search('ok');
    measure('backoff-exponential', { early, ok: ok.length });
    expect(early).toBe(0);
    expect(ok.length).toBe(1);
    ok[0].flush([]);
  });

  it('useEffectsErrorHandler: false - błąd NIE trafia do ErrorHandler, efekt umiera po pierwszym', () => {
    const h = setup({ leakyNoGuard });
    h.search('x')[0].flush('boom', BOOM);
    const second = h.search('y');
    measure('no-guard', { handled: h.handled.length, secondRequests: second.length });
    expect(h.handled.length).toBe(0);
    expect(second.length).toBe(0);
  });

  it('strażnik działa PER EFEKT: efekt-sąsiad z włączonym strażnikiem nie ucierpi', () => {
    const h = setup({ leakySearch, pinger });
    h.search('x')[0].flush('boom', BOOM);
    const pongs = h.ping();
    measure('neighbour-guarded', { pongsAfterNeighbourFailure: pongs, handled: h.handled.length });
    expect(pongs).toBe(1);
  });

  it('efekt dispatchujący, bez strażnika: sąsiad z tego samego provideEffects() PRZEŻYWA (błąd jest materializowany)', () => {
    const h = setup({ leakyNoGuard, pinger });
    const pongsBefore = h.ping();
    h.search('x')[0].flush('boom', BOOM);
    const pongsAfter = h.ping();
    measure('neighbour-dispatching', { pongsBefore, pongsAfter, handled: h.handled.length });
    expect(pongsBefore).toBe(1);
    expect(pongsAfter).toBe(1);
  });

  it('PUŁAPKA: efekt dispatch:false bez strażnika - błąd NIE jest materializowany i zabija sąsiadów', async () => {
    const unhandled = captureUnhandledRxjsErrors();
    const h = setup({ silentNoGuard, pinger });
    const pongsBefore = h.ping();
    h.store.dispatch(OrdersActions.search({ query: 'x' })); // silentNoGuard rzuca przy 'search'
    const pongsAfter = h.ping();
    await nextMacrotask(); // rxjs raportuje "unhandled" przez setTimeout(0)
    measure('neighbour-dispatch-false', {
      pongsBefore,
      pongsAfter,
      errorHandler: h.handled.length,
      unhandledByRxjs: unhandled.map((e) => (e as Error).message),
    });
    expect(pongsBefore).toBe(1);
    expect(pongsAfter).toBe(0);
    expect(h.handled.length).toBe(0); // ErrorHandler Angulara nie dostał nic; błąd poszedł do globalnego "unhandled" rxjs
    expect(unhandled.length).toBe(1);
  });

  it('...i zasięg szkody: osobny provideEffects() zarejestrowany później też przestaje działać', async () => {
    const unhandled = captureUnhandledRxjsErrors();
    const h = setup({ silentNoGuard }, [provideEffects({ pinger })]);
    const pongsBefore = h.ping();
    h.store.dispatch(OrdersActions.search({ query: 'x' }));
    const pongsAfter = h.ping();
    await nextMacrotask();
    measure('neighbour-separate-provide', { pongsBefore, pongsAfter, unhandled: unhandled.length });
    expect(pongsBefore).toBe(1);
    expect(pongsAfter).toBe(0);
  });

  it('efekt z dispatch:false też przechodzi przez strażnika (resubskrypcja po błędzie)', () => {
    let subscriptions = 0;
    const logger = createEffect(
      (actions$ = inject(Actions)) =>
        new Observable<Action>((sub) => {
          subscriptions++;
          const s = actions$.subscribe((a) => {
            if (a.type === '[Orders] ping') sub.error(new Error('logger padl'));
          });
          return () => s.unsubscribe();
        }),
      { functional: true, dispatch: false },
    );
    const h = setup({ logger });
    h.ping();
    measure('dispatch-false', { subscriptions, handled: h.handled });
    expect(subscriptions).toBe(2);
    expect(h.handled).toEqual(['logger padl']);
  });

  it('safeSearch (mapResponse wewnątrz switchMap): błąd -> akcja, strażnik w ogóle nie pracuje', () => {
    const h = setup({ safeSearch });
    h.search('x')[0].flush('boom', BOOM);
    h.search('y')[0].flush([]);
    measure('safe', { actions: h.seen, handled: h.handled.length });
    expect(h.handled.length).toBe(0);
    expect(h.seen).toEqual(['[Orders] search', '[Orders] search failure', '[Orders] search', '[Orders] search success']);
  });

});

describe('createErrorPolicy jako czysta funkcja', () => {
  it('liczy subskrypcje źródła bez TestBed', () => {
    let subs = 0;
    const handledErrors: unknown[] = [];
    const died: unknown[] = [];
    const source$ = new Observable<never>((s) => {
      subs++;
      s.error(new Error(`blad ${subs}`));
    });
    const policy = createErrorPolicy({ maxRetries: 2, baseDelayMs: 0, onDied: (e) => died.push(e) });
    let completed = false;
    policy(source$, { handleError: (e: unknown) => handledErrors.push((e as Error).message) } as ErrorHandler).subscribe({
      complete: () => (completed = true),
    });
    measure('pure-policy', { subs, handledErrors, died: died.length, completed });
    expect(subs).toBe(3);
    expect(handledErrors).toEqual(['blad 1', 'blad 2', 'blad 3']);
    expect(completed).toBe(true);
  });
});
