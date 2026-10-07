---
name: feature-backend
description: Workflow implementacji funkcji backendowej (.NET, PostgreSQL) - design, implementacja z testami, równoległe code review i security review, commit. Uruchamiany ręcznie przez /feature-backend <opis>.
disable-model-invocation: true
---

# Feature backend

Wykonaj kroki po kolei. Nie przeskakuj bramek zatwierdzenia.

Opis zadania: $ARGUMENTS

## 1. Zrozumienie i design

- Przeczytaj `CLAUDE.md`, `.claude/rules/` oraz `docs/domain/` i `docs/architecture/` (ADR-y), jeśli zadanie ich dotyczy. Przeczytaj też repo: strukturę rozwiązania, sąsiedni kod, modele, migracje, istniejące testy. Znajdź komendy build/test.
- Jeśli zadanie wymaga nowej decyzji architektonicznej, zaproponuj nowy ADR (`docs/architecture/adr/`) w designie.
- Jeśli brakuje informacji, które zmieniają design, zadaj pytania pojedynczo (maksymalnie kilka).
- Przedstaw krótki design na czacie: endpointy/serwisy, zmiany schematu bazy, lista plików, plan testów.
- **STOP.** Czekaj na wyraźne "tak". Bez zatwierdzenia nie zmieniaj plików.

## 2. Implementacja

- Uruchom subagenta `dotnet-developer` (narzędzie Agent). Agent nie widzi tej rozmowy, więc w prompcie podaj: zatwierdzony design, ścieżki plików, komendy build/test, ograniczenia (bez commita, bez zmian na nielokalnej bazie).
- Migracje: tylko na lokalnej/testowej bazie. Jeśli connection string nie wygląda na lokalny, zapytaj mnie.
- Po raporcie agenta sam uruchom `dotnet build` i `dotnet test` i sprawdź wynik. Nie ufaj samemu raportowi.
- Testy integracyjne działają na dedykowanej bazie testowej Postgres (connection string ze zmiennej środowiskowej, np. `ConnectionStrings__TestDb`). Jeśli go brak lub baza nie wygląda na testową, zapytaj mnie zamiast pomijać te testy lub celować w inną bazę.

- Aplikacja ma być cloud-ready pod Kubernetes (wiele replik, konfiguracja z env, health checks, graceful shutdown). Jeśli zadanie wymaga zmian w chartcie Helm lub deployu, nie rób ich sam: zaproponuj użycie skilla `helm-deploy` jako osobny krok po commicie.

- Projekt używa .NET Aspire (AppHost, ServiceDefaults), a CI to domyślnie TeamCity. Agent zna te założenia, ale najpierw sprawdź w repo, czy się zgadzają (wersja Aspire, istniejące pipeline'y). Zmian w konfiguracji TeamCity nie rób sam; zaproponuj je w podsumowaniu.

## 3. Review i security równolegle

- Pobierz diff (`git diff` ze zmianami, uwzględnij nowe pliki).
- W jednej wiadomości uruchom dwa subagenty `general-purpose`, każdy z diffem i swoim promptem:
  - code review: prompt z `reviewer-prompt.md` (obok tego pliku),
  - security: prompt z `security-prompt.md` (obok tego pliku).
- Oba tylko czytają, nie edytują.

## 4. Poprawki

- Oceń ustalenia krytycznie: odrzuć fałszywe alarmy z uzasadnieniem, resztę przekaż do `dotnet-developer`.
- Po poprawkach ponownie `dotnet build` i `dotnet test`. Przy zmianach krytycznych powtórz review.

## 5. Commit

- Pokaż `git status` i podsumowanie zmian (co, testy, wynik review).
- Po moim potwierdzeniu zrób commit z opisowym komunikatem. Nie rób push.

## Zasady

- Raportuj uczciwie: jeśli testy padają lub krok pominięto, napisz to wprost z outputem.
- Jeśli w trakcie wyjdzie, że zadanie jest większe niż design (nowy podsystem, zmiana kontraktów), zatrzymaj się i wróć do kroku 1.
