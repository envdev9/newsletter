# 0001. Dapper zamiast EF Core

Status: przyjęta
Data: 2026-10-07

## Kontekst
Backend .NET na PostgreSQL, potrzebna pełna kontrola nad SQL.

## Decyzja
Dostęp do danych przez Dapper na NpgsqlDataSource.

## Konsekwencje
Ręcznie pisany, parametryzowany SQL; brak śledzenia zmian i migracji z modelu. Wymaga testów integracyjnych na prawdziwej bazie.
