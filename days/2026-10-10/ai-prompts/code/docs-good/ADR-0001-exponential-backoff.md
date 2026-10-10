# ADR-0001: Wykładniczy backoff z limitem prób i sufitem opóźnienia

Data: 2026-10-10

## Status

Przyjęty

## Kontekst

Wywołania zewnętrznego API zwracają przejściowe błędy (408, 429, 5xx). Natychmiastowe
ponowienia zwiększają obciążenie usługi, która już ma problem. Operację ponawia
`Backoff.RunAsync` w `Retry/Backoff.cs`.

## Decyzja

- Opóźnienie rośnie wykładniczo: `Backoff.Delay` = `baseDelay * 2^(attempt - 1)`.
- Limit prób: `Backoff.MaxAttempts` = 6, po nim `RetryExhaustedException`.
- Pojedyncze opóźnienie nie przekracza `Backoff.MaxDelay` = 30 s.
- Ponawiamy każdy wyjątek poza `OperationCanceledException`; które kody HTTP są przejściowe,
  rozstrzyga `Backoff.IsTransient`.

## Konsekwencje

- Pozytywne: przewidywalne, ograniczone obciążenie; najgorszy przypadek sumuje opóźnienia
  bez nieskończonej pętli.
- Negatywne: brak jittera - wiele klientów ponawia w tych samych momentach; każdy wyjątek
  jest ponawiany, także błąd programisty (np. `NullReferenceException`).
