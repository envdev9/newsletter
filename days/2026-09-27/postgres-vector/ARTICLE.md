<div align="center">

# 📰 TECH PRASÓWKA
### Wydanie #4 — 27 września 2026

![PostgreSQL + pgvector](https://img.shields.io/badge/PostgreSQL_%2B_pgvector_0.8.6-4169E1?style=for-the-badge&logo=postgresql&logoColor=white)
![.NET](https://img.shields.io/badge/.NET_10_%2B_Npgsql-512BD4?style=for-the-badge&logo=dotnet&logoColor=white)
![Poziom](https://img.shields.io/badge/poziom-zaawansowany-red?style=for-the-badge)
![Status kodu](https://img.shields.io/badge/kod-uruchomiony_%E2%9C%94-brightgreen?style=for-the-badge)

## pgvector z C#: Npgsql, typ `Vector`, kNN z parametrem i EF Core z indeksem HNSW

</div>

---

> _"`operator does not exist: vector <=> real[]` - czyli pierwszy błąd, który zobaczysz, jeśli po prostu
> podasz `float[]` jako parametr. Npgsql nie wie, że to wektor."_

## 🎯 Dlaczego to ważne

Trzy wydania SQL-a za nami, ale Twoja aplikacja to C#. Warstwa styku (parametr wektorowy, odczyt, mapowanie
w EF Core, indeks w migracji) jest miejscem, gdzie wychodzą **ciche i mało intuicyjne** pułapki: `float[]` jest
mapowany na `real[]`, a nie `vector`; wymiar niezgodny z kolumną wywala się dopiero po stronie serwera; `SET`
ustawiany na połączeniu z puli trafia gdzie indziej niż myślisz. Dzisiaj: kompletny, **uruchomiony** projekt na
.NET 10 - dane, binary COPY, kNN, HNSW z pomiarem recall, a na końcu to samo w EF Core.

> 🧪 **Uczciwie o danych.** Bez modelu embeddingowego i bez kluczy: 20 000 wektorów x 64 wymiary, wygenerowanych
> deterministycznie (`Random(42)`, 50 klastrów + szum), 50 zapytań. Liczby poniżej to **prawdziwy output**
> (.NET SDK 10.0.400, kontener `pgvector/pgvector:pg16`, pgvector 0.8.6, PostgreSQL 16.15). Czasy to
> `Stopwatch` po stronie klienta na jednej maszynie (z round-tripem do Dockera), więc orientacyjne. Dane są
> syntetyczne - recall na prawdziwych embeddingach może wyglądać inaczej.

## 1️⃣ Pakiety NuGet: kto za co odpowiada

| Pakiet | Wersja (u mnie) | Rola |
|---|---|---|
| `Npgsql` | 10.0.3 | sterownik ADO.NET |
| `Pgvector` | 0.3.2 | typ `Vector`, `UseVector()` dla `NpgsqlDataSourceBuilder` |
| `Pgvector.EntityFrameworkCore` | 0.3.0 | `UseVector()` dla EF, `CosineDistance` itd. |

Uwaga: `Pgvector.EntityFrameworkCore` 0.3.0 ciągnie `Npgsql.EntityFrameworkCore.PostgreSQL` **9.0.1** i EF Core
**9.0.0**, więc na `net10.0` działa na EF 9 (zbudowało się bez ostrzeżeń i zadziałało - patrz niżej), mimo że
sam Npgsql jest w wersji 10.

## 2️⃣ Npgsql: rejestracja typu i ładowanie danych

```csharp
var dsb = new NpgsqlDataSourceBuilder(connStr);
dsb.UseVector();                 // mapowanie Pgvector.Vector <-> vector
await using var ds = dsb.Build();
```

Kolejność ma znaczenie: `CREATE EXTENSION vector` wykonuję na **osobnym, zwykłym** `NpgsqlDataSource`, a dopiero
potem buduję ten z `UseVector()` - Npgsql poznaje typy bazy przy otwieraniu połączenia, więc rozszerzenie musi już
istnieć. (To ostrożność wynikająca z zasady działania Npgsql; **nie testowałem**, co dokładnie się stanie
w odwrotnej kolejności.)

Ładowanie 20 000 wierszy przez binary COPY, typ `Vector` zapisuje się wprost:

```csharp
await using var import = await conn.BeginBinaryImportAsync("COPY docs (id, category, emb) FROM STDIN (FORMAT BINARY)");
await import.StartRowAsync();
await import.WriteAsync(i);
await import.WriteAsync(data[i].Category);
await import.WriteAsync(new Vector(data[i].V));
```

Prawdziwy output: `Zaladowano 20000 wierszy w 825 ms`.

## 3️⃣ kNN z parametrem wektorowym

```csharp
const string sql = "SELECT id, emb <=> $1 AS dist FROM docs ORDER BY emb <=> $1 LIMIT $2";
cmd.Parameters.AddWithValue(new Vector(q));     // NIE float[]!
cmd.Parameters.AddWithValue(k);
```

```
  id=  7664  cosine_dist=0.0461  (klaster 14)
  id= 15514  cosine_dist=0.1759  (klaster 14)
  id=  8064  cosine_dist=0.1959  (klaster 14)
  id=  3864  cosine_dist=0.1992  (klaster 14)
  id=  3964  cosine_dist=0.2075  (klaster 14)
Dokladnie (Seq Scan): 22.13 ms/zapytanie
```

Wszystkie 5 wyników z tego samego klastra co zapytanie - zgodnie z konstrukcją danych. Bez indeksu to dokładny
Seq Scan: ok. 22 ms na 20 000 wierszy.

## 4️⃣ HNSW i recall@10 mierzony z C#

Prawdę (dokładne top-10) zebrałem *przed* utworzeniem indeksu, potem `CREATE INDEX ... USING hnsw`
(`m=16`, `ef_construction=64`, 6,9 s) i pomiar `hnsw.ef_search`:

```csharp
await using var tx = await conn.BeginTransactionAsync();
await new NpgsqlCommand("SET LOCAL hnsw.ef_search = 40", conn, tx).ExecuteNonQueryAsync();
// ... zapytania kNN ...
await tx.CommitAsync();
```

| `hnsw.ef_search` | recall@10 | czas/zapytanie |
|---:|---:|---:|
| 10 | 0,972 | 1,47 ms |
| 40 (domyślne) | 1,000 | 1,82 ms |
| 200 | 1,000 | 2,54 ms |
| *brak indeksu (dokładnie)* | *1,0* | *22,13 ms* |

> 💡 **`SET LOCAL` w transakcji** to bezpieczny wzorzec przy puli połączeń: ustawienie żyje tylko do końca
> transakcji i nie "wycieknie" do kolejnego użytkownika tego samego fizycznego połączenia. Zwykły `SET` zostaje na
> połączeniu po zwróceniu do puli (wniosek z semantyki puli; nie testowałem wycieku).

⚠️ **Powtarzalność:** dane są deterministyczne, ale budowa grafu HNSW nie. Recall przy `ef_search=10` w trzech
kolejnych przebiegach: **0,956 / 0,994 / 0,972**. Nie porównuj pojedynczych przebiegów - uśredniaj.

Planner faktycznie używa indeksu przy zapytaniu z **parametrem** (`EXPLAIN` z tym samym `Vector`):

```
Limit  (cost=167.17..171.63 rows=10 width=12)
  ->  Index Scan using docs_hnsw on docs  (cost=167.17..9092.00 rows=20000 width=12)
        Order By: (emb <=> '[...64 floaty...]'::vector)
```

## 5️⃣ Pułapki, które wyprodukowałem naprawdę

| Błąd | Realny komunikat |
|---|---|
| `float[]` zamiast `Vector` | `42883 operator does not exist: vector <=> real[]` |
| wektor 3D do kolumny `vector(64)` | `22000 different vector dimensions 3 and 64` |

Oba to `PostgresException` po stronie serwera - kompilator Ci nie pomoże, wymiar to nie część typu C#. Trzymaj stałą
wymiaru w jednym miejscu (u nas `HasColumnType("vector(64)")` i model embeddingowy muszą się zgadzać).

W drodze do działającego demo trafiłem też na zwykłą pułapkę EF, niezwiązaną z wektorami: `int Id` z wartością
`0` jest traktowany jako "niewypełniony" i generowany przez bazę, co przy ręcznie nadawanych kluczach kończy się
`23505 duplicate key ... PK_items`. Lekarstwo: `Property(x => x.Id).ValueGeneratedNever()`.

## 6️⃣ EF Core: kolumna, indeks HNSW i `CosineDistance`

Model (`OnModelCreating`) opisuje kolumnę **i** indeks:

```csharp
protected override void OnConfiguring(DbContextOptionsBuilder o)
    => o.UseNpgsql(connStr, npgsql => npgsql.UseVector());

mb.HasPostgresExtension("vector");
mb.Entity<Item>(e =>
{
    e.Property(x => x.Embedding).HasColumnType("vector(64)");
    e.HasIndex(x => x.Embedding, "ix_items_embedding")
        .HasMethod("hnsw")
        .HasOperators("vector_cosine_ops")
        .HasStorageParameter("m", 16)
        .HasStorageParameter("ef_construction", 64);
});
```

Zapytanie w LINQ:

```csharp
var q = new Vector(queryEmbedding);
var top = db.Items.OrderBy(x => x.Embedding!.CosineDistance(q)).Take(5)
            .Select(x => new { x.Id, x.Category, Dist = x.Embedding!.CosineDistance(q) });
```

Prawdziwy SQL z `ToQueryString()` (literał wektora skrócony):

```sql
-- @__q_0='[...64 floaty...]' (DbType = Object)
-- @__p_1='5'
SELECT i."Id", i."Category", i."Embedding" <=> @__q_0 AS "Dist"
FROM items AS i
ORDER BY i."Embedding" <=> @__q_0
LIMIT @__p_1
```

Dokładnie to samo zapytanie co ręczne - operator `<=>` to `CosineDistance`, więc **indeks z `vector_cosine_ops`
pasuje**. (`L2Distance` -> `<->` wymaga `vector_l2_ops`, `MaxInnerProduct` -> `<#>` wymaga `vector_ip_ops`; te
warianty **nie były uruchamiane**.) Indeks utworzony z modelu, odczytany z `pg_indexes`:

```
CREATE INDEX ix_items_embedding ON public.items USING hnsw ("Embedding" vector_cosine_ops) WITH (ef_construction='64', m='16')
```

Wynik (top 5 z pierwszych 2000 wierszy tabeli `items`; inny zbiór niż `docs`, stąd inne id): `id=664 dist=0,2183`,
`564 / 0,2291`, `1214 / 0,2489`, `464 / 0,2527`, `1714 / 0,2562`, wszystkie w klastrze 14.

> 📌 Co zweryfikowałem, a co nie w EF: schemat utworzyłem przez `EnsureCreated()` (nie przez migracje). Że
> `dotnet ef migrations add` wygeneruje `CREATE INDEX ... USING hnsw` identycznie - **nie sprawdzałem**. Nie
> sprawdzałem też, czy planner użył indeksu HNSW dla zapytania z EF (tabela `items` ma tylko 2000 wierszy;
> dla tak małej tabeli planner mógłby wybrać Seq Scan). Zapytanie jest jednak identyczne co do postaci z tym,
> dla którego `EXPLAIN` w pkt 4 pokazał `Index Scan using docs_hnsw`.

## 🚀 Jak uruchomić

```bash
cd days/2026-09-27/postgres-vector/code
bash run-demo.sh      # kontener pgvector-prasowka-d4 na porcie 54329, sprząta po sobie
```

Szczegóły i output: [`code/README.md`](code/README.md).

## 🧾 Status weryfikacji

| Element | Status |
|---|---|
| `dotnet build` net10.0 (0 ostrzeżeń, 0 błędów) i `dotnet run` przeciw pgvector 0.8.6 / PG 16.15 | ✅ prawdziwy output |
| Binary COPY z `Vector`, kNN z parametrem, HNSW + recall, EXPLAIN, dwa błędy | ✅ |
| EF Core: `HasColumnType`, indeks HNSW z modelu, `CosineDistance` + SQL | ✅ (przez `EnsureCreated`) |
| `run-demo.sh` jako całość | ⚠️ nie odpalony end-to-end; kontener i `dotnet run` uruchomione ręcznie tymi samymi komendami |
| Migracje EF (`dotnet ef`), `L2Distance`/`MaxInnerProduct`, plan EF na indeksie | ❌ nie sprawdzane |
| Kolejność `CREATE EXTENSION` vs `UseVector()` (opisana ostrożnościowo) | ❌ nie testowane |
| Wyciek `SET` przez pulę połączeń | ❌ wniosek z semantyki, nie test |
| Prawdziwe embeddingi; kod z wydania #2 (`fastembed`) | ❌ nadal niezweryfikowany |

---

<div align="center">

[← wróć do wydania #4 (wszystkie rubryki)](../README.md) · [spis wydań](../../README.md)

</div>
