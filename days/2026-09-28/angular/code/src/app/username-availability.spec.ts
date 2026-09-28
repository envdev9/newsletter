import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';
import { checkUsernameAvailability } from './username-availability';

describe('checkUsernameAvailability (fake backend za resource() loaderem)', () => {
  beforeEach(() => {
    vi.useFakeTimers();
  });

  afterEach(() => {
    vi.useRealTimers();
  });

  it('zwraca available: true dla nieznanego loginu po 300 ms', async () => {
    const controller = new AbortController();
    const promise = checkUsernameAvailability('nowyUser', controller.signal);
    await vi.advanceTimersByTimeAsync(300);
    await expect(promise).resolves.toEqual({ username: 'nowyUser', available: true });
  });

  it('zwraca available: false dla zajętego loginu (case-insensitive)', async () => {
    const controller = new AbortController();
    const promise = checkUsernameAvailability('Admin', controller.signal);
    await vi.advanceTimersByTimeAsync(300);
    await expect(promise).resolves.toEqual({ username: 'Admin', available: false });
  });

  it('odrzuca natychmiast, gdy sygnał jest już przerwany', async () => {
    const controller = new AbortController();
    controller.abort();
    // Uwaga: AbortController w jsdom/Node tworzy `reason` jako DOMException z INNEGO realmu niż
    // globalny `DOMException` w tym pliku testowym, więc `toBeInstanceOf(DOMException)` zawodzi
    // (cross-realm instanceof) - sprawdzamy nazwę błędu, tak jak robi to prawdziwy kod obsługujący fetch.
    await expect(checkUsernameAvailability('ktokolwiek', controller.signal)).rejects.toMatchObject({
      name: 'AbortError',
    });
  });

  it('odrzuca i czyści timer, gdy przerwanie przychodzi w trakcie oczekiwania', async () => {
    const controller = new AbortController();
    const promise = checkUsernameAvailability('ktokolwiek', controller.signal);
    await vi.advanceTimersByTimeAsync(100);
    controller.abort();
    await expect(promise).rejects.toMatchObject({ name: 'AbortError' });
    // Timer wyczyszczony - dalszy upływ czasu nic już nie rozstrzyga (brak "unhandled rejection").
    await vi.advanceTimersByTimeAsync(1000);
  });
});
