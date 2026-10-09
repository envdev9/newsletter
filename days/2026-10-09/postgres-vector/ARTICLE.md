<div align="center">

# 📰 TECH PRASÓWKA
### Wydanie #9 — 9 października 2026

![PostgreSQL + pgvector](https://img.shields.io/badge/PostgreSQL_16_%2B_pgvector-4169E1?style=for-the-badge&logo=postgresql&logoColor=white)
![.NET](https://img.shields.io/badge/.NET_10_%2B_Npgsql_10-512BD4?style=for-the-badge&logo=dotnet&logoColor=white)
![Poziom](https://img.shields.io/badge/poziom-zaawansowany-red?style=for-the-badge)
![Status kodu](https://img.shields.io/badge/kod-uruchomiony_%E2%9C%94-brightgreen?style=for-the-badge)

## `HalfVector` w .NET i `iterative_scan` na puli połączeń: połowa pamięci, a ustawienie, które potrafi „przeciec” do cudzego żądania

</div>

---

> _"Ustawiłem `hnsw.iterative_scan = relaxed_order`, filtr zaczął działać. Dwa tygodnie później inny endpoint, który
> niczego nie ustawiał, zwraca wyniki w dziwnej kolejności."_
> — scenariusz, który poniżej zreprodukowałem liczbami

## 🎯 Dlaczego to ważne

Dwie rzeczy, które w .NET-owym pgvector wychodzą dopiero na produkcji:

1. **Embeddingi z modeli typu 3072-wymiarowych nie wejdą do indeksu HNSW jako `vector`** (limit 2000 wymiarów). Wejdą jako
   `halfvec` (limit 4000) - i przy okazji zajmą połowę miejsca.
2. **`hnsw.iterative_scan` to ustawienie sesji Postgresa, a sesja to fizyczne połączenie z puli Npgsql.** Plain `SET`
   przeżywa zwrot połączenia do puli, jeśli pula go nie resetuje. Zmierzyłem, jak bardzo.

> 🧪 **Uczciwie o danych.** 20 000 wektorów × 64 wymiary, syntetyczne i deterministyczne (`Random(42)`, 50 klastrów + szum),
> bez modelu embeddingowego. Przy 1536/3072 wymiarach mierzone są tylko rozmiary i limity na wektorach losowych (bez
> recall). .NET SDK **10.0.400**, `Npgsql` **10.0.3**, `Pgvector` **0.3.2**, kontener `pgvector/pgvector:pg16`. Cały output
> poniżej pochodzi z uruchomienia na tej maszynie; kod: [`code/`](code/).

## 1️⃣ `HalfVector` w C#: to samo API, 2 bajty na wymiar

```csharp
await w.WriteAsync(new Vector(data[i]));                                    // vector(64)
await w.WriteAsync(new HalfVector(data[i].Select(x => (Half)x).ToArray())); // halfvec(64)
```

Binary COPY działa tak samo jak dla `Vector`; odczyt: `reader.GetFieldValue<HalfVector>(i).ToArray()` daje `Half[]`.
Konwersja `float → Half` dzieje się po stronie klienta, więc dostajesz błąd zaokrąglenia ~1e-4 na składową:

```
float32=0.330712  half=0.33081055  blad=9.86E-005
```

Rozmiary (64 wymiary, 20 000 wierszy):

| | `vector(64)` | `halfvec(64)` |
|---|---|---|
| `pg_column_size` | 264 B | 136 B |
| indeks HNSW (m=16, ef_c=64) | 11,4 MB | 8,7 MB (−24%) |

Tylko −24%, bo przy 64 wymiarach większość wielkości indeksu to nie wektory, tylko listy sąsiadów grafu. Dlatego sprawdziłem
realne wymiary (`dims.sql`, 3000 losowych wektorów):

| | wynik |
|---|---|
| 1536 wymiarów: indeks `vector` vs `halfvec` | 24 584 192 B vs 12 296 192 B = **2,00×** |
| `pg_column_size` 1536 wym. | 6148 B vs 3080 B |
| HNSW na `vector(3072)` | `ERROR: column cannot have more than 2000 dimensions for hnsw index` |
| HNSW na `(e::halfvec(3072))` | działa, 24 584 192 B |
| HNSW na `halfvec(4001)` | `ERROR: column cannot have more than 4000 dimensions for hnsw index` |

**Wzorzec, który polecam, gdy nie chcesz zmieniać kolumny:** kolumna zostaje `vector`, indeks na rzutowaniu, a zapytanie
musi użyć *dokładnie tego samego wyrażenia*:

```sql
CREATE INDEX ON items USING hnsw ((embedding::halfvec(64)) halfvec_cosine_ops);
SELECT id FROM items ORDER BY embedding::halfvec(64) <=> $1 LIMIT 10;   -- $1 jako HalfVector
```

`EXPLAIN` potwierdził `Index Scan using ix_items_cast` dla tego wyrażenia i `ix_items_vec` dla gołego `embedding <=> $1`
(czyli rzutowanie w zapytaniu jest wymagane, planner nie zgaduje).

**Recall:** 20 zapytań, `ef_search=40`, ground truth = dokładny kNN na float32: `halfvec` 1,000, `vector` 0,995 (w innym
przebiegu 0,955). Ta różnica to **niedeterministyczna budowa grafu**, nie zaleta `halfvec` - wniosek jest tylko taki, że
nie widać straty jakości. Jeden zestaw danych, jedna budowa; nie uogólniaj.

## 2️⃣ Problem, który rozwiązuje `iterative_scan` (zwięzłe przypomnienie z #3)

Filtr po kolumnie bez indeksu (5% wierszy), `LIMIT 10`, 20 zapytań, oczekiwane 200 wierszy:

```
iterative_scan=off            wierszy zwroconych:  39/200  recall: 0.195
iterative_scan=strict_order   wierszy zwroconych: 200/200  recall: 1.000
iterative_scan=relaxed_order  wierszy zwroconych: 200/200  recall: 1.000
```

Ciekawostka: filtr po `tenant` (~0,5%, z indeksem B-tree) **nie miał tego problemu**, bo planner w ogóle nie sięgnął po HNSW
(`Bitmap Heap Scan` + `Sort`). Problem dotyczy filtrów mało selektywnych lub bez indeksu - tam, gdzie planner idzie po HNSW
z `Filter:` na końcu.

## 3️⃣ Gdzie to ustawić w .NET? Pula połączeń

Cztery eksperymenty (`dotnet run -- pool`):

**a) Plain `SET` a zwrot do puli.** Pula z jednym połączeniem, ten sam `pg_backend_pid` przed i po:

```
No Reset On Close=False  ... SHOW przed zwrotem: relaxed_order  po ponownym otwarciu: (pusty)
No Reset On Close=True   ... SHOW przed zwrotem: relaxed_order  po ponownym otwarciu: relaxed_order
```

Domyślnie Npgsql resetuje sesję przy zwrocie (ustawienie znika). Z `No Reset On Close=true` (używane dla wydajności, np.
przy bardzo krótkich zapytaniach) - **zostaje**.

**b) Skala wycieku.** Pula 4, 16 równoległych zadań × 50 zapytań, `No Reset On Close=true`. Parzyste zadania robią
`SET hnsw.iterative_scan='relaxed_order'`, nieparzyste *nic nie ustawiają* i sprawdzają wartość:

```
5a (SET sesyjny):                     nieparzyste zobaczyly relaxed_order w 398 z 400 zapytan
5b (set_config(..., true) w tx):      nieparzyste zobaczyly relaxed_order w   0 z 400 zapytan
```

**c) `Options` w connection stringu** - ustawienie jako domyślne dla całej puli:

```
Options=-c hnsw.iterative_scan=relaxed_order -c hnsw.max_scan_tuples=5000
swieze polaczenie : iterative_scan=relaxed_order, max_scan_tuples=5000
po SET ... 'off'  : iterative_scan=off
po zwrocie do puli (reset): iterative_scan=relaxed_order      <- reset wraca do wartosci z Options
```

**d) Transakcyjnie**, per zapytanie - `set_config('hnsw.iterative_scan', 'relaxed_order', true)` (3. argument `true` =
`SET LOCAL`; wersja z parametrem, więc bez sklejania SQL-a):

```csharp
await using var tx = await conn.BeginTransactionAsync();
await using (var set = new NpgsqlCommand("SELECT set_config('hnsw.iterative_scan', $1, true)", conn, tx))
{ set.Parameters.AddWithValue("relaxed_order"); await set.ExecuteScalarAsync(); }
// ... zapytanie kNN w tej samej transakcji ...
await tx.CommitAsync();
```

**Moja rekomendacja:** domyślny tryb globalnie przez `Options` (c), wyjątki od niego przez `set_config(..., true)` w
transakcji (d). Plain `SET` omijaj, zwłaszcza jeśli ktoś w zespole może kiedyś włączyć `No Reset On Close`.

## 🪤 Pułapki (wszystkie napotkane naprawdę)

| Pułapka | Objaw / naprawa |
|---|---|
| `CREATE EXTENSION vector` na połączeniu, które już załadowało typy Npgsql | `Cannot resolve 'vector' to a fully qualified datatype name` → `await conn.ReloadTypesAsync()` po `CREATE EXTENSION` |
| `SHOW hnsw.iterative_scan` na świeżym backendzie | `42704: unrecognized configuration parameter` - GUC istnieje dopiero po załadowaniu biblioteki `vector`; używaj `current_setting('hnsw.iterative_scan', true)` (NULL zamiast błędu) |
| Wartość po resecie to pusty string, nie `off` | Zaobserwowane w `SHOW`; hipoteza (placeholder GUC sprzed załadowania biblioteki) **niezweryfikowana**, jak zachowuje się wtedy wyszukiwanie - też |
| Filtr z B-tree i małą selektywnością | HNSW w ogóle nieużyty, więc „test iterative_scan” niczego nie pokazuje - dobierz filtr |
| `halfvec` zamiast `vector` „poprawił recall” | To szum budowy grafu (0,955 vs 0,995 dla tego samego `vector` w dwóch przebiegach) |

## 🚀 Jak uruchomić

Kroki: [`code/README.md`](code/README.md) (kontener `pgvector-prasowka-d9`, `dotnet run -- load | halfvec | pool`,
`dims.sql`).

## 🧾 Status weryfikacji

| Element | Status |
|---|---|
| `HalfVector`: binary COPY, odczyt, rozmiary kolumny i indeksu (64 wym.) | ✅ uruchomione |
| Limity wymiarów 2000/4000, rozmiar indeksu przy 1536 i 3072 wym. | ✅ `psql`, losowe wektory |
| Indeks na `embedding::halfvec(N)` używany przez planner | ✅ `EXPLAIN` |
| `iterative_scan` off/strict/relaxed z filtrem (recall 0,195 → 1,000) | ✅ 20 zapytań, jeden zestaw danych |
| Wyciek `SET` przez pulę (398/400) i brak wycieku z `set_config(…, true)` (0/400) | ✅ uruchomione, `No Reset On Close=true` |
| `Options` w connection stringu zachowuje się po resecie puli | ✅ uruchomione |
| Recall `halfvec` przy 1536/3072 wym. | ❌ nie mierzone (tylko rozmiary) |
| `max_scan_tuples` w działaniu, partycjonowanie z HNSW, `HalfVector` w EF Core | ❌ niezweryfikowane |
| Przyczyna pustego stringu po resecie | ❌ hipoteza, niesprawdzona |
| Kod z #2 (fastembed) | ❌ nadal niezweryfikowany |

---

<div align="center">

[← wróć do wydania #9 (wszystkie rubryki)](../README.md) · [spis wydań](../../README.md)

</div>
