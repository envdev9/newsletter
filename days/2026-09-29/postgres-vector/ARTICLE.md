<div align="center">

# 📰 TECH PRASÓWKA
### Wydanie #7 — 29 września 2026

![PostgreSQL + pgvector](https://img.shields.io/badge/PostgreSQL_%2B_pgvector_0.8.6-4169E1?style=for-the-badge&logo=postgresql&logoColor=white)
![.NET](https://img.shields.io/badge/.NET_10_%2B_EF_Core_9-512BD4?style=for-the-badge&logo=dotnet&logoColor=white)
![Poziom](https://img.shields.io/badge/poziom-zaawansowany-red?style=for-the-badge)
![Status kodu](https://img.shields.io/badge/kod-uruchomiony_%E2%9C%94-brightgreen?style=for-the-badge)

## pgvector przez migracje EF Core: `dotnet ef migrations add` z indeksem HNSW, od pustej bazy

</div>

---

> _"Zmieniłem tylko `m` i `ef_construction` w konfiguracji indeksu. EF sam wygenerował
> `DROP INDEX` + `CREATE INDEX` - nie ma czegoś takiego jak `ALTER INDEX ... SET (m = ...)`
> dla HNSW, więc jedyne wyjście to zbudować indeks od nowa."_

## 🎯 Dlaczego to ważne

W wydaniu #4 poznaliśmy pgvector z .NET, ale schemat (kolumna `vector(64)` + indeks HNSW) powstawał przez
`EnsureCreated()` - metodę, której **nikt nie używa na produkcji**. Tam żyją migracje: `dotnet ef migrations add`,
code review diffa migracji, `dotnet ef database update` w pipeline CI/CD. Pytanie, na które #4 nie odpowiedziało:
czy EF w ogóle **umie** wygenerować `CREATE EXTENSION vector` + kolumnę wektorową + indeks HNSW z parametrami
(`m`, `ef_construction`) w migracji, i co się dzieje, gdy zmienisz te parametry później? Dziś to sprawdzam
od zera: pusta baza, `dotnet ef migrations add`, realny `dotnet ef database update`, a potem zmiana parametrów
indeksu i **druga** migracja - żeby zobaczyć, czy EF robi `ALTER`, czy coś zupełnie innego.

> 🧪 **Uczciwie o danych.** Dane: 20 000 wektorów × 64 wymiary, deterministyczne (`Random(42)`, 50 klastrów +
> szum) - identyczna metoda co w #4, żeby liczby (recall, czasy) były porównywalne. Bez modelu embeddingowego,
> bez kluczy API. Wersje: .NET SDK 10.0.400, `dotnet-ef` **10.0.12** (jako lokalne narzędzie, patrz pkt 2),
> `Pgvector.EntityFrameworkCore` 0.3.0 (EF Core **9.0.0** w tle), kontener `pgvector/pgvector:pg16`
> (pgvector 0.8.6, PostgreSQL 16.15). Wszystkie logi i SQL poniżej to **prawdziwy output** z tej maszyny.

## 1️⃣ `dotnet ef` jako narzędzie globalne? Nie tutaj

```
$ dotnet tool install --global dotnet-ef
# odrzucone przez uprawnienia środowiska (piaskownica blokuje zapis poza katalogiem roboczym)
```

Zamiast tego lokalny manifest **w katalogu projektu** - to i tak lepsza praktyka (wersja `dotnet-ef` przypięta
per-repo, nie zależy od tego, co ktoś ma zainstalowane globalnie):

```bash
dotnet new tool-manifest        # tworzy dotnet-tools.json
dotnet tool install dotnet-ef   # bez --global
```

Prawdziwy output:

```
Tool 'dotnet-ef' (version '10.0.12') was successfully installed.
```

Odtąd narzędzie odpala się przez `dotnet tool run dotnet-ef ...` (albo `dotnet dotnet-ef ...` po `dotnet tool restore`
na innej maszynie/w CI). ⚠️ Uwaga na wersje: `dotnet-ef` **10.0.12** generuje migracje dla modelu zbudowanego na
EF Core **9.0.0** (bo tyle ciągnie `Pgvector.EntityFrameworkCore` 0.3.0) - zadziałało bez ostrzeżeń, ale to nie jest
oczywiste z samych numerków wersji.

## 2️⃣ Model: kolumna wektorowa + indeks HNSW w `OnModelCreating`

Identycznie jak w #4, ale tym razem to jedyne źródło prawdy o schemacie - nie ma już `EnsureCreated()`:

```csharp
protected override void OnModelCreating(ModelBuilder modelBuilder)
{
    modelBuilder.HasPostgresExtension("vector");

    modelBuilder.Entity<Item>(e =>
    {
        e.ToTable("items");
        e.Property(x => x.Id).ValueGeneratedNever();
        e.Property(x => x.Embedding).HasColumnType("vector(64)");

        e.HasIndex(x => x.Embedding, "ix_items_embedding_hnsw")
            .HasMethod("hnsw")
            .HasOperators("vector_cosine_ops")
            .HasStorageParameter("m", 16)
            .HasStorageParameter("ef_construction", 64);
    });
}
```

Do tego fabryka design-time (`IDesignTimeDbContextFactory<AppDbContext>`) - bez niej `dotnet ef` próbowałby
uruchomić `Program.Main` (który u nas ładuje 20 000 wierszy), więc lepiej dać mu osobną, "suchą" ścieżkę budowy
kontekstu tylko do migracji.

## 3️⃣ Pierwsza migracja: `dotnet ef migrations add InitialCreate`

```
$ dotnet tool run dotnet-ef migrations add InitialCreate
Build started...
Build succeeded.
Done. To undo this action, use 'ef migrations remove'
```

Wygenerowany plik migracji (`Migrations/20260929024044_InitialCreate.cs`, fragment):

```csharp
protected override void Up(MigrationBuilder migrationBuilder)
{
    migrationBuilder.AlterDatabase()
        .Annotation("Npgsql:PostgresExtension:vector", ",,");

    migrationBuilder.CreateTable(
        name: "items",
        columns: table => new
        {
            Id = table.Column<int>(type: "integer", nullable: false),
            Category = table.Column<string>(type: "character varying(64)", maxLength: 64, nullable: false),
            Embedding = table.Column<Vector>(type: "vector(64)", nullable: true)
        },
        constraints: table => table.PrimaryKey("PK_items", x => x.Id));

    migrationBuilder.CreateIndex(
        name: "ix_items_embedding_hnsw",
        table: "items",
        column: "Embedding")
        .Annotation("Npgsql:IndexMethod", "hnsw")
        .Annotation("Npgsql:IndexOperators", new[] { "vector_cosine_ops" })
        .Annotation("Npgsql:StorageParameter:ef_construction", 64)
        .Annotation("Npgsql:StorageParameter:m", 16);
}
```

**Odpowiedź na pytanie z nagłówka artykułu: tak.** EF wie, jak z `HasPostgresExtension` + `HasColumnType("vector(64)")`
+ `.HasMethod("hnsw").HasStorageParameter(...)` złożyć kompletną migrację - włącznie z `CREATE EXTENSION`. Podgląd
surowego SQL (`dotnet ef migrations script`):

```sql
START TRANSACTION;
CREATE EXTENSION IF NOT EXISTS vector;

CREATE TABLE items (
    "Id" integer NOT NULL,
    "Category" character varying(64) NOT NULL,
    "Embedding" vector(64),
    CONSTRAINT "PK_items" PRIMARY KEY ("Id")
);

CREATE INDEX ix_items_embedding_hnsw ON items USING hnsw ("Embedding" vector_cosine_ops) WITH (ef_construction=64, m=16);
...
COMMIT;
```

## 4️⃣ `dotnet ef database update` na PUSTEJ bazie - naprawdę

Kontener `pgvector/pgvector:pg16`, **żadnej ręcznej `CREATE EXTENSION`** - to ma zrobić migracja:

```
$ dotnet tool run dotnet-ef database update
Acquiring an exclusive lock for migration application.
Applying migration '20260929024044_InitialCreate'.
Done.
```

Sprawdzone z drugiej strony, bezpośrednio w bazie (`\d items` + `pg_indexes` + `pg_extension`):

```
                        Table "public.items"
  Column   |         Type          | Nullable
-----------+-----------------------+----------
 Id        | integer               | not null
 Category  | character varying(64) | not null
 Embedding | vector(64)            |
Indexes:
    "PK_items" PRIMARY KEY, btree ("Id")
    "ix_items_embedding_hnsw" hnsw ("Embedding" vector_cosine_ops) WITH (ef_construction='64', m='16')

 extname | extversion
---------+------------
 vector  | 0.8.6
```

Dokładnie to, co opisywała migracja. Zero ręcznego SQL-a.

## 5️⃣ Zmiana parametrów HNSW → druga migracja: `DROP INDEX` + `CREATE INDEX`, nie `ALTER`

Podnoszę `m: 16 → 24` i `ef_construction: 64 → 128` w `OnModelCreating` i każę EF zdiffować model:

```
$ dotnet tool run dotnet-ef migrations add BumpHnswParams
Build succeeded.
Done.
```

Wygenerowany diff:

```csharp
protected override void Up(MigrationBuilder migrationBuilder)
{
    migrationBuilder.DropIndex(name: "ix_items_embedding_hnsw", table: "items");

    migrationBuilder.CreateIndex(
        name: "ix_items_embedding_hnsw", table: "items", column: "Embedding")
        .Annotation("Npgsql:IndexMethod", "hnsw")
        .Annotation("Npgsql:IndexOperators", new[] { "vector_cosine_ops" })
        .Annotation("Npgsql:StorageParameter:ef_construction", 128)
        .Annotation("Npgsql:StorageParameter:m", 24);
}
```

**To jest konkretna, praktyczna odpowiedź**, której nie było w #1-#4: EF **nie próbuje** `ALTER INDEX ... SET
(m = 24)` (Postgres i tak by to odrzucił dla HNSW - te parametry działają tylko przy tworzeniu indeksu, nie da się
ich zmienić w locie). Zamiast tego EF robi to, co musiałbyś zrobić ręcznie: `DROP` + `CREATE`. Konsekwencja: na
tabeli z 20 000 wierszami ta migracja (`dotnet ef database update`) zajęła realnie:

```
Applying migration '20260929024410_BumpHnswParams'.
Done.
real    0m19.4s   (w tym build dotnet-ef; sam rebuild indeksu to większość tego czasu)
```

Na dużej tabeli produkcyjnej to jest **downtime albo blokada zapisów** na czas budowy indeksu (chyba że dodasz
`CREATE INDEX CONCURRENTLY` ręcznie do migracji - EF domyślnie tego nie robi). Sprawdziłem też `Down()` (rollback):

```
$ dotnet tool run dotnet-ef database update InitialCreate
Reverting migration '20260929024410_BumpHnswParams'.
Done.
```

`pg_indexes` po rollbacku pokazał z powrotem `ef_construction='64', m='16'` - `Down()` też robi pełny rebuild, w
drugą stronę. Odtworzyłem `BumpHnswParams` z powrotem przed dalszymi testami.

## 6️⃣ Czy zbudowany od migracji indeks realnie działa? (`EXPLAIN`, recall, EF LINQ)

Program ładuje 20 000 wektorów przez binary COPY, a potem pyta przez EF (`OrderBy(x => x.Embedding.CosineDistance(q))`).
Weryfikacja szła w dwóch etapach: raz z `m=16/ef_construction=64` (pierwsza migracja), raz z `m=24/ef_construction=128`
(po `BumpHnswParams`) - dokładnie ten sam kod, inny stan schematu:

| Konfiguracja HNSW (z migracji) | Czas ładowania 20k wierszy | recall@10 | czas/zapytanie |
|---|---:|---:|---:|
| `m=16, ef_construction=64` | 25,5–25,7 s | 0,984 | 0,80 ms |
| `m=24, ef_construction=128` | 49,2–49,5 s | 0,980–1,000 | 0,88–0,92 ms |

Ładowanie jest wolniejsze przy wyższym `m` - to spodziewane: HNSW aktualizuje graf **przy każdym wstawianym
wierszu**, a większe `m` = więcej połączeń do policzenia na wstawienie. Recall nie różni się jednoznacznie na tak
małym zbiorze (50 zapytań, 20k wektorów) - różnica mieści się w szumie pomiarowym HNSW, o którym już pisaliśmy w #4.

`EXPLAIN` potwierdza użycie indeksu z migracji (nie Seq Scan):

```
Limit  (cost=186.05..187.77 rows=5 width=12)
  ->  Index Scan using ix_items_embedding_hnsw on items  (cost=186.05..10394.32 rows=29716 width=12)
        Order By: ("Embedding" <=> '[...64 floaty...]'::vector)
```

SQL z `ToQueryString()` - identyczny wzorzec co w #4 (`<=>` = `CosineDistance`, pasuje do `vector_cosine_ops`
indeksu):

```sql
SELECT i."Id", i."Category", i."Embedding" <=> @__qParam_0 AS "Dist"
FROM items AS i
ORDER BY i."Embedding" <=> @__qParam_0
LIMIT @__p_1
```

## 7️⃣ Pułapki, na które naprawdę wpadłem po drodze

| Pułapka | Co się stało |
|---|---|
| `EXPLAIN SELECT id FROM items ...` (małe litery) | `42703 column "id" does not exist` - EF tworzy kolumnę `"Id"` (wielka litera, cudzysłów), Postgres bez cudzysłowu składuje/szuka małych liter. Trzeba cytować dokładnie tak, jak nazwał ją EF. |
| `new NpgsqlConnection(connStr)` bez `UseVector()` | `InvalidCastException: Writing values of 'Pgvector.Vector' is not supported...` - zwykłe połączenie ADO nie zna typu `vector`; do binary COPY z `Vector` trzeba `NpgsqlDataSourceBuilder(...).UseVector()`, tak jak w #4. |
| Wyższe `m/ef_construction` (24/128) + domyślny timeout | `TimeoutException` w środku `BeginBinaryImportAsync` (30 s to za mało na 20k insertów budujących cięższy graf HNSW w locie) - podniesione do `Command Timeout=120` w connection stringu. |
| Test recall po zmianie parametrów bazy na nowe dane | Zliczanie trafień po `Id` z listy C# (0-based) vs `Id` w Postgresie (1-based, bo COPY pisał `i+1`) dawało recall≈0,02 - wyglądało jak katastrofa indeksu, a to było zwykłe przesunięcie o 1 w kodzie testowym, nie problem pgvector. Warto to przyznać: pierwszy pomiar recall w tym wydaniu był fałszywie zaniżony, dopóki nie znalazłem przesunięcia. |

Ostatnia pozycja to uczciwe przyznanie się do błędu w kodzie weryfikującym, nie w kodzie demo - ale dokładnie
dlatego trzymamy się zasady "wklej prawdziwy output": bez uruchomienia nigdy byśmy tego nie złapali.

## 🚀 Jak uruchomić

```bash
cd days/2026-09-29/postgres-vector/code
bash run-demo.sh      # kontener pgvector-prasowka-d7 na porcie 54340, sprząta po sobie
```

Szczegóły, pełny output i uruchomienie krok po kroku: [`code/README.md`](code/README.md).

## 🧾 Status weryfikacji

| Element | Status |
|---|---|
| `dotnet tool install dotnet-ef` (lokalnie, bez `--global`) | ✅ zadziałało; `--global` odrzucone przez sandbox |
| `dotnet ef migrations add InitialCreate` (extension + tabela + HNSW) z modelu EF | ✅ prawdziwy output i plik migracji |
| `dotnet ef database update` od **pustej** bazy (bez ręcznego `CREATE EXTENSION`) | ✅ zweryfikowane `\d items` + `pg_indexes` + `pg_extension` |
| Zmiana `m`/`ef_construction` → druga migracja generuje `DROP INDEX`+`CREATE INDEX` (nie `ALTER`) | ✅ prawdziwy diff, zmierzony czas aplikacji (~19,4 s) |
| Rollback (`database update InitialCreate`) cofa też indeks do starych parametrów | ✅ potwierdzone `pg_indexes` po rollbacku |
| `dotnet run` (binary COPY 20k, EF LINQ `CosineDistance`, `EXPLAIN`, recall@10) na obu wersjach schematu | ✅ prawdziwy output, dwa pełne przebiegi |
| `run-demo.sh` jako całość (od `docker run` do `dotnet run`) | ⚠️ nie odpalony jako plik wykonywalny (blokada środowiska na uruchamianie `.sh`); wszystkie kroki wykonane ręcznie, tymi samymi komendami co w skrypcie |
| `CREATE INDEX CONCURRENTLY` w migracji zamiast blokującego rebuildu | ❌ nie sprawdzane - naturalny następny krok |
| `HalfVector` w .NET, `iterative_scan` z pulą połączeń, partycjonowanie z HNSW | ❌ nadal niezweryfikowane (patrz #3/#4) |
| Kod z wydania #2 (prawdziwe embeddingi `fastembed`) | ❌ nadal niezweryfikowany |

---

<div align="center">

[← wróć do wydania #7 (wszystkie rubryki)](../README.md) · [spis wydań](../../README.md)

</div>
