import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';
import { placeOrder } from './order-backend';

describe('placeOrder (fake-backend)', () => {
  beforeEach(() => {
    vi.useFakeTimers();
  });

  afterEach(() => {
    vi.useRealTimers();
  });

  it('zwraca sukces z rosnącym numerem zamówienia po 300ms', async () => {
    const resultPromise = placeOrder({ customerName: 'Jan', items: [{ productName: 'Kabel USB-C', quantity: 2 }] });
    await vi.advanceTimersByTimeAsync(300);
    const result = await resultPromise;
    expect(result.kind).toBe('ok');
    expect(result.orderId).toMatch(/^ORD-\d+$/);
  });

  it('nie rozwiązuje promise przed upływem 300ms', async () => {
    let resolved = false;
    placeOrder({ customerName: 'Jan', items: [] }).then(() => {
      resolved = true;
    });
    await vi.advanceTimersByTimeAsync(299);
    expect(resolved).toBe(false);
    await vi.advanceTimersByTimeAsync(1);
    expect(resolved).toBe(true);
  });
});
