# web (Angular) - local rules

- Standalone components only, `ChangeDetectionStrategy.OnPush`, state in signals.
- HTTP through `httpResource`/services in `core/`; components never call `HttpClient` directly.
- Tests: Vitest; one `*.spec.ts` beside each component.
