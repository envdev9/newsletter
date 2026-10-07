# 0004. .NET Aspire

Status: przyjęta
Data: 2026-10-07

## Kontekst
Wiele serwisów i zależności, potrzebna spójna konfiguracja i telemetria.

## Decyzja
Orkiestracja i konfiguracja przez Aspire (AppHost, ServiceDefaults).

## Konsekwencje
Serwis zna tylko klucz ConnectionStrings:db. Na Kubernetesie AppHost nie działa, więc konfigurację dostarcza chart. Health endpointy muszą działać poza Development.
