---
name: ef-migration-review
description: Review migracji EF Core (pliki w Migrations/*.cs, zmiany w ModelSnapshot) pod kątem utraty danych, blokad na dużych tabelach, brakującego/pustego Down() i zgodności ze snapshotem. Użyj gdy ktoś prosi o review migracji, gdy w diffie pojawia się nowy plik w katalogu Migrations albo po `dotnet ef migrations add`.
allowed-tools: Read, Glob, Grep, Bash(python3 *scan_migration.py*), Bash(dotnet ef migrations list*), Bash(dotnet ef migrations has-pending-model-changes*), Bash(dotnet ef migrations script*)
---

# ef-migration-review

Review migracji EF Core w dwóch krokach: najpierw **deterministyczny skaner** (żeby nic
nie umknęło), potem **ocena kontekstowa** (tego skaner nie zrobi).

## Krok 1 — skaner

Uruchom skaner dołączony do tego skilla na każdym zmienionym pliku migracji
(`*.cs` w `Migrations/`, **pomijaj** `*.Designer.cs` i `*ModelSnapshot.cs`):

```bash
python3 .claude/skills/ef-migration-review/scan_migration.py Migrations/<plik>.cs
```

Skaner zwraca linie `plik:linia | POZIOM | opis` (exit 1 = są znaleziska). Traktuj je
jako *kandydatów*, nie werdykt.

## Krok 2 — ocena kontekstowa (ręcznie, przez Read)

Dla każdego znaleziska i dodatkowo dla całej migracji odpowiedz:

1. **Utrata danych.** `DropColumn`/`DropTable`/zawężenie typu w `AlterColumn`: czy dane
   są gdzieś przenoszone (`migrationBuilder.Sql` wcześniej)? Czy `Down()` odtwarza
   *strukturę* (dane i tak przepadną - napisz to wprost)?
2. **Rename czy drop+add?** EF potrafi zamienić zmianę nazwy właściwości na
   `DropColumn` + `AddColumn`. Jeśli intencją był rename - migracja kasuje dane; popraw
   ręcznie na `RenameColumn`.
3. **NOT NULL na istniejącej tabeli.** Czy wartość domyślna ma sens biznesowy, czy to
   tylko `""`/`0` wpisane przez scaffolder?
4. **Blokady na dużych tabelach.** `CreateIndex`, `AlterColumn`: zapytaj o rząd wielkości
   tabeli. Na SQL Server rozważ indeks online (`.Annotation("SqlServer:Online", true)`,
   zależne od edycji).
5. **Zgodność wsteczna przy rolling deploy.** Czy stara wersja aplikacji zadziała na
   nowym schemacie (rename/drop łamią ją)? Jeśli nie - zaproponuj wzorzec
   expand/contract w dwóch migracjach.
6. **`Down()`.** Nie jest pusty, odwraca operacje w odwrotnej kolejności.
7. **Snapshot.** Czy `*ModelSnapshot.cs` zmienił się spójnie z migracją? Jeśli masz
   dostęp do projektu, sprawdź `dotnet ef migrations has-pending-model-changes`
   (zakończenie kodem != 0 = model różni się od snapshotu).
8. **Skrypt SQL.** Dla zmian ryzykownych zaproponuj wygenerowanie skryptu do przeglądu
   DBA: `dotnet ef migrations script <poprzednia> <ta> --idempotent`.

## Format odpowiedzi

Tabela, tylko wiersze z zastrzeżeniami:

| Plik:linia | Ryzyko | Problem | Proponowana poprawka |
|---|---|---|---|

Pod tabelą jedno zdanie werdyktu: **OK do merge** / **OK po poprawkach** / **blokuje**.
Nie zmieniaj migracji sam, dopóki użytkownik o to nie poprosi - to review.
