import {
  Debouncer,
  SchemaPathTree,
  debounce,
  minLength,
  required,
  schema,
  validateHttp,
} from '@angular/forms/signals';

export interface ProjectModel {
  name: string;
  /** "Pracuję offline" - request zwraca `undefined`, więc walidacja HTTP w ogóle nie rusza. */
  offline: boolean;
}

/** Kształt odpowiedzi endpointu `GET /api/projects/exists?name=...`. */
export interface ExistsResponse {
  taken: boolean;
  suggestion?: string;
}

export const emptyProject = (): ProjectModel => ({ name: '', offline: false });

const sleep = (ms: number): Promise<void> => new Promise((resolve) => setTimeout(resolve, ms));

/** Wspólna część: reguły sync + validateHttp. `request` zwraca `undefined` gdy offline. */
function httpPart(p: SchemaPathTree<ProjectModel>, httpDebounce?: number) {
  required(p.name, { message: 'Nazwa jest wymagana' });
  minLength(p.name, 3, { message: 'Nazwa musi mieć co najmniej 3 znaki' });

  validateHttp<string, ExistsResponse>(p.name, {
    request: (ctx) =>
      ctx.valueOf(p.offline) ? undefined : { url: '/api/projects/exists', params: { name: ctx.value() } },
    ...(httpDebounce !== undefined ? { debounce: httpDebounce } : {}),
    onSuccess: (res) =>
      res.taken ? { kind: 'taken', message: `Nazwa jest zajęta - spróbuj "${res.suggestion}"` } : undefined,
    onError: () => ({ kind: 'check-failed', message: 'Nie udało się sprawdzić unikalności nazwy' }),
  });
}

/**
 * SCHEMAT APLIKACJI: `debounce(p.name, 'blur')` opóźnia ZAPIS z UI do modelu do utraty fokusu,
 * więc validateHttp nie potrzebuje własnego `debounce` - model po prostu się nie zmienia w trakcie pisania.
 */
export const blurSchema = schema<ProjectModel>((p) => {
  debounce(p.name, 'blur');
  httpPart(p);
});

/** `debounce(pole, 300)` - opóźnienie zapisu z UI; validateHttp bez własnego debounce. */
export const uiDebounceSchema = schema<ProjectModel>((p) => {
  debounce(p.name, 300);
  httpPart(p);
});

/** Dla porównania: debounce TYLKO na requeście (jak w #13) - UI zapisuje do modelu natychmiast. */
export const requestDebounceSchema = schema<ProjectModel>((p) => {
  httpPart(p, 300);
});

/** Zapis dla testów: co dostała funkcja `debounce` z `validateHttp` (nie mylić z regułą `debounce()`). */
export interface HttpDebounceCall {
  status: string;
  request: unknown;
}

/**
 * `debounce` w `validateHttp` jako FUNKCJA `(request, lastSnapshot) => Promise | void`
 * ("leading + trailing"): jeśli od poprzedniego startu minęła ponad sekunda, request leci OD RAZU
 * (`void`), w trakcie serii wpisów - z 300 ms zwłoki. Czas trzymamy w domknięciu, bo snapshot
 * nie ma statusu 'idle' - startuje jako 'resolved'.
 */
export const httpDebounceFnSchema = (calls: HttpDebounceCall[]) => {
  let lastStart = -Infinity;
  return schema<ProjectModel>((p) => {
    required(p.name, { message: 'Nazwa jest wymagana' });
    minLength(p.name, 3, { message: 'Nazwa musi mieć co najmniej 3 znaki' });
    validateHttp<string, ExistsResponse>(p.name, {
      request: (ctx) => ({ url: '/api/projects/exists', params: { name: ctx.value() } }),
      debounce: (request, last) => {
        calls.push({ status: last.status, request });
        const now = Date.now();
        const leading = now - lastStart > 1000;
        lastStart = now;
        return leading ? undefined : sleep(300);
      },
      onSuccess: (res) => (res.taken ? { kind: 'taken', message: 'zajęta' } : undefined),
      onError: () => ({ kind: 'check-failed', message: 'błąd sprawdzania' }),
    });
  });
};

/** Zapis dla testów: co zobaczył własny `Debouncer` przy każdym wywołaniu. */
export interface DebouncerCall {
  /** `ctx.value()` - wartość w MODELU w chwili wywołania (nie to, co użytkownik właśnie wpisał). */
  modelValue: string;
  aborted: boolean;
}

/**
 * Własny `Debouncer<string>`: czeka 300 ms, ale krótkie nazwy (< 3 znaki) zapisuje od razu
 * (zwraca `void` = brak opóźnienia), żeby komunikat `minLength` pojawiał się bez zwłoki.
 */
export function customDebouncer(calls: DebouncerCall[]): Debouncer<string> {
  return (ctx, abortSignal) => {
    const call: DebouncerCall = { modelValue: ctx.value(), aborted: false };
    calls.push(call);
    abortSignal.addEventListener('abort', () => (call.aborted = true), { once: true });
    // Uwaga: to nie jest wartość wpisana przez użytkownika, tylko ostatnia zatwierdzona w modelu.
    return ctx.value().length < 2 ? undefined : sleep(300);
  };
}

export const customDebouncerSchema = (calls: DebouncerCall[]) =>
  schema<ProjectModel>((p) => {
    debounce(p.name, customDebouncer(calls));
    httpPart(p);
  });
