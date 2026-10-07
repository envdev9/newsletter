# 0003. Testy integracyjne na dedykowanej bazie testowej

Status: przyjęta
Data: 2026-10-07

## Kontekst
Testy integracyjne muszą działać na prawdziwym Postgresie, także w TeamCity.

## Decyzja
Dedykowana, współdzielona baza testowa zamiast Testcontainers; connection string z ConnectionStrings__TestDb, izolacja schematem na przebieg.

## Konsekwencje
Brak zależności od Dockera. Potrzebny sieciowy dostęp do bazy i ochrona przed trafieniem w inną bazę (sprawdzanie nazwy).
