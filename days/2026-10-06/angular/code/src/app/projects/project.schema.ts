import { minLength, required, schema, validateHttp } from '@angular/forms/signals';

export interface ProjectModel {
  name: string;
  /** "Pracuję offline" - wyłącza sprawdzanie unikalności (demo opcji `when`). */
  offline: boolean;
}

/** Kształt odpowiedzi endpointu `GET /api/projects/exists?name=...`. */
export interface ExistsResponse {
  taken: boolean;
  suggestion?: string;
}

export const emptyProject = (): ProjectModel => ({ name: '', offline: false });

/**
 * WERSJA POPRAWNA: `validateHttp` z `HttpResourceRequest` (url + params), debounce i `when`.
 * Sync reguły (`required`/`minLength`) działają PRZED requestem - bez nich HTTP w ogóle nie rusza.
 */
export const projectSchema = schema<ProjectModel>((p) => {
  required(p.name, { message: 'Nazwa jest wymagana' });
  minLength(p.name, 3, { message: 'Nazwa musi mieć co najmniej 3 znaki' });

  validateHttp<string, ExistsResponse>(p.name, {
    request: (ctx) => ({ url: '/api/projects/exists', params: { name: ctx.value() } }),
    debounce: 300,
    when: ({ valueOf }) => !valueOf(p.offline),
    onSuccess: (res) =>
      res.taken ? { kind: 'taken', message: `Nazwa jest zajęta - spróbuj "${res.suggestion}"` } : undefined,
    onError: () => ({ kind: 'check-failed', message: 'Nie udało się sprawdzić unikalności nazwy' }),
  });
});

/**
 * WERSJA NAIWNA (tylko do porównania w testach): URL sklejany ręcznie, brak debounce.
 */
export const naiveProjectSchema = schema<ProjectModel>((p) => {
  required(p.name, { message: 'Nazwa jest wymagana' });
  minLength(p.name, 3, { message: 'Nazwa musi mieć co najmniej 3 znaki' });

  validateHttp<string, ExistsResponse>(p.name, {
    request: (ctx) => '/api/projects/exists?name=' + ctx.value(),
    onSuccess: (res) => (res.taken ? { kind: 'taken', message: 'zajęta' } : undefined),
    onError: () => ({ kind: 'check-failed', message: 'błąd sprawdzania' }),
  });
});
