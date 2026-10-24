---
name: ef-core-migration-safety
description: Sprawdza migracje Entity Framework Core pod katem bezpieczenstwa danych na produkcji - DROP COLUMN/TABLE bez etapu przejsciowego, zmiana typu kolumny bez konwersji danych, dodanie NOT NULL bez wartosci domyslnej, brak indeksu na nowym kluczu obcym. Uzyj, gdy uzytkownik dodaje lub przeglada migracje EF Core (dotnet ef migrations add), zmienia model domeny wplywajacy na istniejaca tabele, albo pyta czy dana migracja jest bezpieczna do wgrania na produkcji.
allowed-tools: Read, Grep, Glob
---

# ef-core-migration-safety

Checklist do przejrzenia kazdego pliku `*_Migration.cs` (metoda `Up`) przed wgraniem na
baze z realnymi danymi. Nie modyfikuje kodu - tylko diagnozuje i podaje bezpieczny wzorzec.

## Co sprawdzic w metodzie `Up`

1. **`DropColumn` / `DropTable`** - nieodwracalne. Zamiast jednego kroku: (a) release N -
   przestan czytac/pisac kolumne w kodzie, (b) release N+1 - dopiero `DropColumn`.
2. **`AlterColumn` ze zmiana typu** (np. `int` -> `decimal`, `nvarchar(50)` -> `nvarchar(20)`)
   - sprawdz czy istniejace dane mieszcza sie w nowym typie/dlugosci. Zwezenie dlugosci
     bez walidacji danych = utrata danych po migracji.
3. **`AddColumn` z `nullable: false` bez `defaultValue`/`defaultValueSql`** - na tabeli
   z istniejacymi wierszami migracja padnie albo wstawi NULL tam gdzie constraint tego
   zabrania (zalezne od providera). Wymagaj `defaultValueSql` albo dwuetapowego wdrozenia.
4. **Nowy `ForeignKey` bez `CreateIndex` na kolumnie FK** - dziala, ale kazdy JOIN po tej
   kolumnie robi table scan. EF Core samo nie dodaje indeksu na FK (w odroznieniu od PK).
5. **`RenameColumn`** - dla wielu providerow to w praktyce `DROP` + `ADD`, nie operacja
   w miejscu. Traktuj jak punkt 1 (dwa etapy), nie jak "kosmetyczna" zmiana.

## Jak zobaczyc realne SQL przed wgraniem

```bash
dotnet ef migrations script <poprzednia-migracja> <ta-migracja> --idempotent
```

Czytaj wygenerowany SQL, nie tylko kod C# migracji - EF Core czasem generuje krok
pomocniczy (np. tabela tymczasowa przy `AlterColumn` na SQLite), ktorego nie widac w `Up()`.
