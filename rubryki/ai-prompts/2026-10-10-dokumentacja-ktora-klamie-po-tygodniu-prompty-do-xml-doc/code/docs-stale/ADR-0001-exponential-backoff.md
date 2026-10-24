# ADR-0001: Exponential backoff

## Status

Accepted

## Kontekst

Chcemy ponawiać nieudane wywołania.

## Decyzja

Używamy backoffu wykładniczego z limitem `Backoff.MaxAttempts` = 5.

## Konsekwencje

- Mniej błędów, lepsza niezawodność.
