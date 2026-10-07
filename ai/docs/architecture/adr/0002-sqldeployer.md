# 0002. SqlDeployer do migracji

Status: przyjęta
Data: 2026-10-07

## Kontekst
Potrzebne migracje schematu bez EF Migrations.

## Decyzja
Migracje jako zwykłe skrypty SQL uruchamiane SqlDeployerem.

## Konsekwencje
Pełna kontrola nad SQL, brak udokumentowanego rollbacku, więc zmiany wstecznie kompatybilne. Migracje jako osobny Job/zasób, nie w Main replik.
