---
paths:
  - "**/*.sql"
---

# Skrypty SQL (SqlDeployer)

- Nazwa: numer na początku, np. `00001-Opis.sql`. Skrypty w katalogu wykonują się alfabetycznie.
- Przed dodaniem skryptu obejrzyj istniejące i dopasuj katalog, nazwę i numer.
- Zmiany wstecznie kompatybilne (najpierw dodaj, później usuń), bo stara i nowa wersja działają równolegle podczas rolling update. Rollback nie jest udokumentowany.
- Duże tabele: indeksy `CONCURRENTLY`, ostrożnie z blokadami.
- Czas: `timestamptz`. Identyfikatory: `uuid`. Pieniądze: `numeric`.
- Pierwszy przebieg zawsze z `--dryrun`.
