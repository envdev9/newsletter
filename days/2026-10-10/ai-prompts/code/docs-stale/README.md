# Retry - backoff z jitterem dla wywołań HTTP

Biblioteka (`Retry/Throttle.cs`) liczy opóźnienia między ponowieniami. Konfiguracja przez `RetryPolicy`.

## Stałe

- `Backoff.MaxAttempts` = 5
- `Backoff.MaxDelay` = 60 s

## API

| Składowa | Co robi |
|---|---|
| `Backoff.Delay(attempt, baseDelay, jitter)` | opóźnienie wykładnicze z jitterem |
| `Backoff.ShouldRetry(httpStatus)` | czy kod HTTP jest przejściowy |
| `Backoff.RunAsync(operation, baseDelay, sleep, ct)` | ponawia operację |
| `RetryExhaustedException.AttemptCount` | liczba prób |

## Uruchomienie

```bash
dotnet run --project Retry.Sample
```
