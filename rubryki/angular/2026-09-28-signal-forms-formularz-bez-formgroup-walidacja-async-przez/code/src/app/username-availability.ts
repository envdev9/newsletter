/**
 * Udawany endpoint `/api/users/check-username`. Symuluje realne API:
 * - 300 ms opóźnienia (jak prawdziwe zapytanie sieciowe),
 * - respektuje `AbortSignal` - gdy poprzednie zapytanie zostanie przerwane (bo użytkownik
 *   wpisał kolejny znak), timer jest czyszczony i promise odrzucany zamiast "wisieć" w tle.
 *
 * To jest dokładnie kształt funkcji, jakiej oczekuje `loader` w `resource()`.
 */

const TAKEN_USERNAMES = new Set(['admin', 'root', 'angular']);

export interface UsernameCheckResult {
  readonly username: string;
  readonly available: boolean;
}

export function checkUsernameAvailability(
  username: string,
  abortSignal: AbortSignal,
): Promise<UsernameCheckResult> {
  return new Promise<UsernameCheckResult>((resolve, reject) => {
    if (abortSignal.aborted) {
      reject(abortSignal.reason ?? new DOMException('Aborted', 'AbortError'));
      return;
    }

    const timer = setTimeout(() => {
      resolve({ username, available: !TAKEN_USERNAMES.has(username.toLowerCase()) });
    }, 300);

    abortSignal.addEventListener(
      'abort',
      () => {
        clearTimeout(timer);
        reject(abortSignal.reason ?? new DOMException('Aborted', 'AbortError'));
      },
      { once: true },
    );
  });
}
