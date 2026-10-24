<div align="center">

# 🧬 PostgreSQL jako baza wektorowa

### TECH PRASÓWKA — wszystkie artykuły rubryki, najnowsze na górze

</div>

---

Każdy artykuł to osobny folder `<data>-<tytuł>/` z `ARTICLE.md` i pełnym, uruchamialnym
kodem w `code/`. Kolejne artykuły podnoszą poziom — postęp rubryki jest w
[`STATE.md`](../../STATE.md).

| Data | Artykuł | W skrócie | Kod |
|------|---------|-----------|-----|
| 2026-10-16 | [Partycjonowanie z indeksem HNSW: wielotenantowy kNN bez post-filtrowania — i `max_scan_tuples`, czyli bezpiecznik skanu iteracyjnego](2026-10-16-partycjonowanie-z-indeksem-hnsw-wielotenantowy-knn-bez-post/ARTICLE.md) | Osiem tenantów w jednej tabeli wektorów i `WHERE tenant = 3` zwraca 4,5 wiersza z 10? Partycje z osobnym grafem HNSW na tenanta dają zawsze 10 wierszy i recall do 1,00, a `max_scan_tuples` pokazuje, jak łatwo cicho uciąć wyniki. | [Kod](2026-10-16-partycjonowanie-z-indeksem-hnsw-wielotenantowy-knn-bez-post/code/) |
| 2026-10-09 | [`HalfVector` w .NET i `iterative_scan` na puli połączeń: połowa pamięci, a ustawienie, które potrafi „przeciec” do cudzego żądania](2026-10-09-halfvector-w-net-i-iterative-scan-na-puli-polaczen-polowa/ARTICLE.md) | Embeddingi 3072-wymiarowe nie wejdą do indeksu HNSW jako `vector`, ale jako `halfvec` wejdą w połowie rozmiaru — a zwykły `SET hnsw.iterative_scan` przecieka między żądaniami na puli Npgsql (398 z 400 zapytań trafiło na cudzy tryb). | [Kod](2026-10-09-halfvector-w-net-i-iterative-scan-na-puli-polaczen-polowa/code/) |
| 2026-10-04 | [`CREATE INDEX CONCURRENTLY` w migracji EF Core dla HNSW: istnieje, działa, ale EF i tak Cię ostrzeże](2026-10-04-create-index-concurrently-w-migracji-ef-core-dla-hnsw/ARTICLE.md) | `CREATE INDEX CONCURRENTLY` w migracji EF Core dla HNSW: istnieje (`.IsCreatedConcurrently()`), EF sam rozbija transakcję — i realnie znosi blokadę zapisów (zmierzone: 10,9 s blokady bez niego vs zero zablokowanych insertów z nim, na dwóch równoległych sesjach). | [Kod](2026-10-04-create-index-concurrently-w-migracji-ef-core-dla-hnsw/code/) |
| 2026-09-29 | [pgvector przez migracje EF Core: `dotnet ef migrations add` z indeksem HNSW, od pustej bazy](2026-09-29-pgvector-przez-migracje-ef-core-dotnet-ef-migrations-add-z/ARTICLE.md) | `dotnet ef migrations add` naprawdę umie złożyć migrację z indeksem HNSW od zera (włącznie z `CREATE EXTENSION`) — a zmiana parametrów `m`/`ef_construction` nie robi `ALTER`, tylko pełny `DROP`+`CREATE` indeksu (zmierzone: ~19,4 s na 20k wierszy). | [Kod](2026-09-29-pgvector-przez-migracje-ef-core-dotnet-ef-migrations-add-z/code/) |
| 2026-09-27 | [pgvector z C#: Npgsql, typ `Vector`, kNN z parametrem i EF Core z indeksem HNSW](2026-09-27-pgvector-z-c-npgsql-typ-vector-knn-z-parametrem-i-ef-core-z/ARTICLE.md) | pgvector z C#: Npgsql + `Pgvector` + EF Core `CosineDistance`, indeks HNSW z modelu i pułapka `float[]` kontra `Vector` — 20 000 wektorów, recall 0,97–1,00 przy ~1,5–2,5 ms (Seq Scan: 22 ms), prawdziwy output na .NET 10. | [Kod](2026-09-27-pgvector-z-c-npgsql-typ-vector-knn-z-parametrem-i-ef-core-z/code/) |
| 2026-09-26 | [Wektory z filtrem WHERE i w odchudzonej wersji: iterative scan, partial index, halfvec, bit](2026-09-26-wektory-z-filtrem-where-i-w-odchudzonej-wersji-iterative/ARTICLE.md) | Filtr `WHERE` potrafi po cichu wyzerować wyniki HNSW (recall 0,019), a `iterative_scan`, partial index i `halfvec` to naprawiają lub odchudzają indeks — zmierzone na pgvector 0.8.6, z uczciwym rachunkiem, gdzie kwantyzacja binarna na razie zawodzi. | [Kod](2026-09-26-wektory-z-filtrem-where-i-w-odchudzonej-wersji-iterative/code/) |
| 2026-09-25 | [Hybrid search i strojenie indeksów: wektor + tsvector + Reciprocal Rank Fusion](2026-09-25-hybrid-search-i-strojenie-indeksow-wektor-tsvector/ARTICLE.md) | Wektor nie zna kodu błędu `40001`, a pełnotekstowe nie zna parafraz — łączymy oba rankingi przez Reciprocal Rank Fusion i mierzymy koszt recallu przy strojeniu IVFFlat/HNSW. ⚠️ Kod napisany, ale niezweryfikowany uruchomieniem (blokada uprawnień). | [Kod](2026-09-25-hybrid-search-i-strojenie-indeksow-wektor-tsvector/code/) |
| 2026-09-24 | [PostgreSQL jako baza wektorowa: `pgvector` od zera](2026-09-24-postgresql-jako-baza-wektorowa-pgvector-od-zera/ARTICLE.md) | `pgvector`, IVFFlat vs HNSW, realne zapytanie podobieństwa — i uczciwy moment, w którym | [Kod](2026-09-24-postgresql-jako-baza-wektorowa-pgvector-od-zera/code/) |
<!-- kolejne wiersze dopisywane automatycznie, najnowsze na górze -->

---

<div align="center">

[← spis rubryk](../../README.md)

</div>
