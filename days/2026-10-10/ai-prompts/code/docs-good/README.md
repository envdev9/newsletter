# Retry - wykładniczy backoff dla wywołań HTTP

Mała biblioteka (`Retry/Backoff.cs`): liczy opóźnienia między ponowieniami i wykonuje
operację z ponowieniami. Nie zna HTTP - klasyfikację kodów statusu daje `Backoff.IsTransient`.

## Stałe

- `Backoff.MaxAttempts` = 6 (łącznie z pierwszą próbą)
- `Backoff.MaxDelay` = 30 s

## API

| Składowa | Co robi | Wyjątki |
|---|---|---|
| `Backoff.Delay(attempt, baseDelay)` | `baseDelay * 2^(attempt - 1)`, obcięte do `Backoff.MaxDelay` | `ArgumentOutOfRangeException` |
| `Backoff.IsTransient(httpStatus)` | `true` dla 408, 429 i 500-599 | - |
| `Backoff.RunAsync(operation, baseDelay, sleep, ct)` | do `Backoff.MaxAttempts` prób z opóźnieniem między nimi | `ArgumentNullException`, `RetryExhaustedException` |

Przykłady (wykonywane przez `Retry.Demo`): `Backoff.Delay(3, 100 ms)` daje 400 ms;
po wyczerpaniu prób `RetryExhaustedException.Attempts` równa się liczbie wykonanych prób.

## Uruchomienie

```bash
dotnet build Retry
dotnet run --project Retry.Demo
```
