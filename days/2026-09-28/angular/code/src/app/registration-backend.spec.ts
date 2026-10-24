import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';
import { registerUser } from './registration-backend';

describe('registerUser (fake backend rejestracji)', () => {
  beforeEach(() => {
    vi.useFakeTimers();
  });

  afterEach(() => {
    vi.useRealTimers();
  });

  it('zwraca ok dla nowego adresu e-mail', async () => {
    const promise = registerUser({ username: 'ktos', email: 'nowy@example.com', password: 'haslo123' });
    await vi.advanceTimersByTimeAsync(200);
    await expect(promise).resolves.toEqual({ kind: 'ok' });
  });

  it('zwraca email-taken dla zarejestrowanego adresu (case-insensitive)', async () => {
    const promise = registerUser({ username: 'ktos', email: 'Taken@example.com', password: 'haslo123' });
    await vi.advanceTimersByTimeAsync(200);
    await expect(promise).resolves.toEqual({
      kind: 'email-taken',
      message: 'Adres Taken@example.com jest już zarejestrowany',
    });
  });
});
