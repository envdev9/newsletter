/**
 * Udawany endpoint rejestracji. 200 ms opóźnienia, jeden zajęty e-mail na sztywno -
 * wystarczy, by pokazać jak błąd z "serwera" trafia z powrotem na konkretne pole formularza.
 */

const REGISTERED_EMAILS = new Set(['taken@example.com']);

export interface RegistrationData {
  readonly username: string;
  readonly email: string;
  readonly password: string;
}

export type RegisterOutcome = { readonly kind: 'ok' } | { readonly kind: 'email-taken'; readonly message: string };

export function registerUser(data: RegistrationData): Promise<RegisterOutcome> {
  return new Promise<RegisterOutcome>((resolve) => {
    setTimeout(() => {
      if (REGISTERED_EMAILS.has(data.email.toLowerCase())) {
        resolve({ kind: 'email-taken', message: `Adres ${data.email} jest już zarejestrowany` });
      } else {
        resolve({ kind: 'ok' });
      }
    }, 200);
  });
}
