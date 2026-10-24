<div align="center">

# 📰 TECH PRASÓWKA
### Wydanie #23 — 16 października 2026

![AI](https://img.shields.io/badge/AI_%2F_Claude_Code-D97757?style=for-the-badge&logo=anthropic&logoColor=white)
![Poziom](https://img.shields.io/badge/poziom-zaawansowany-red?style=for-the-badge)
![PostgreSQL](https://img.shields.io/badge/PostgreSQL_16-4169E1?style=for-the-badge&logo=postgresql&logoColor=white)
![pg_trgm](https://img.shields.io/badge/pg__trgm-gin__trgm__ops-336791?style=for-the-badge)
![citext](https://img.shields.io/badge/citext-ILIKE-orange?style=for-the-badge)

## Rachunek za GIN: ile kosztuje indeks, który ratuje `Contains` — i co z `ILIKE` oraz `citext`

</div>

---

> _"Indeks, który przyspiesza odczyt 100-krotnie, jest darmowy tylko wtedy, gdy nikt nic nie zapisuje."_

W #16 skill `ef-core-review` poradził: dla `Contains` załóż GIN z `gin_trgm_ops` (17 buforów
zamiast 1696). Zostawiłem wtedy dług: **ile to kosztuje przy zapisie** oraz co z `ILIKE` i
`citext`. Dziś rachunek — czysty SQL, bez .NET, bo pytanie dotyczy silnika, nie ORM-a.

---

## 1️⃣ 🎯 Dlaczego to ważne

Skill, który mówi "dodaj indeks" bez ceny, robi z zespołu ofiary własnej rady. Reguła
`LIKE-LEADING-WILDCARD` powinna wypisać obie strony: zysk w odczycie i koszt w zapisie.

## 2️⃣ 🔬 Pomiar 1: koszt zapisu i rozmiar

PostgreSQL 16 (Docker, własny kontener), tabela `email varchar(100)`, 200 000 wierszy.
Czasy z `EXPLAIN ANALYZE` pojedynczych uruchomień:

| Operacja | bez indeksu | btree | pattern_ops | GIN trgm |
|---|---|---|---|---|
| INSERT 200 000 | 457 ms | 2739 ms | 1541 ms | **8661 ms** |
| INSERT 20 000 do zaindeksowanej | 34 ms | 257 ms | – | **900 ms** |
| UPDATE 20 000 (zmiana e-maila) | 89 ms | 416 ms | – | **1156 ms** |

GIN to ok. **19× wolniejszy insert** niż brak indeksu i ok. 3,2× wolniejszy niż btree przy
tych danych (zmierzone, jedna maszyna, jeden kształt danych).

Rozmiar jest mniej oczywisty:

- po insercie przyrostowym wszystkie trzy indeksy miały po **19 MB** (heap: 14 MB), GIN urósł
  do 21 MB po dołożeniu 20 tys. wierszy i 22 MB po UPDATE;
- po `CREATE INDEX` na gotowej tabeli: btree **12 MB**, GIN **15 MB**; budowa GIN 3,99 s, btree 1,24 s.

Wniosek praktyczny: budowa indeksu "od ręki" jest ok. 2x tańsza niż to samo w trakcie wstawiania
(btree 1,2 s vs 2,7 s), a indeks zbudowany przyrostowo jest większy. Przy dużym imporcie: najpierw
dane, potem indeks.

## 3️⃣ 🪤 `fastupdate`: koszt, który się przesuwa

GIN domyślnie odkłada zapisy do **pending list** (`fastupdate=on`). Po wstawieniu 20 000
wierszy w pending list było 3035 krotek / 276 stron. Zmierzone:

```
fastupdate = on :   933 ms   (pending: 276 stron, 3035 krotek)
fastupdate = off: 10481 ms
gin_clean_pending_list('ix_gin') -> 276 stron wyczyszczonych
```

Uczciwie: wariant `off` wstawiał do **większej** tabeli (po dwóch poprzednich insertach), więc
10x to górne oszacowanie, nie czysta różnica. Kierunek jest jednak pewny: `fastupdate` nie
usuwa kosztu, tylko go odracza — płaci go autovacuum albo zapytanie, które trafi na pełną
pending list. Nie mierzyłem opóźnienia tego zapytania, więc nie podam liczby.

## 4️⃣ 🔬 Pomiar 2: `ILIKE`, `lower()`, `citext`

Szukany adres: `user77777.…@mail.example`, zapytanie dostaje wersję WIELKIMI literami.
Plany z `EXPLAIN (ANALYZE, BUFFERS)`:

| Wariant | Plan | Bufory | Czas |
|---|---|---|---|
| `lower(email) = lower(@p)`, indeks btree na `email` | Parallel Seq Scan | 2132 | 117 ms |
| to samo, indeks btree na `lower(email)` | Index Scan | 4 | 0,09 ms |
| `citext`, btree, `email = @p` | Index Scan | 4 | 0,16 ms |
| `email ILIKE '%…%'` (36 znaków), GIN trgm | Bitmap Index Scan | 824 | 28 ms |
| `email ILIKE 'USER77777.%'`, btree pattern_ops | Seq Scan | 1768 | 295 ms |
| `lower(email) LIKE 'user77777.%'`, btree na `lower` bez pattern_ops | Parallel Seq Scan | 1768 | 102 ms |
| `citext`, `email LIKE 'USER77777.%'`, btree | Seq Scan | 1768 | 272 ms |

Cztery wnioski:

1. **`ToLower()` w LINQ przy zwykłym indeksie = pełny skan.** Dwa lekarstwa dla równości:
   indeks funkcyjny na `lower(email)` albo `citext`; oba schodzą do ~4 buforów.
2. **`ILIKE` z prefiksem nie używa `varchar_pattern_ops`.** `pattern_ops` z #16 działa dla
   `LIKE`, nie dla `ILIKE` — Seq Scan, 1768 buforów.
3. **`citext` nie daje indeksowanego prefiksu**: `LIKE 'X%'` na kolumnie `citext` to Seq Scan.
4. **GIN działa dla `ILIKE` z `%`**, ale 36-znakowa igła to dużo trigramów: 823 bufory indeksu,
   a nie 17 jak dla krótkiego słowa w #16. Kolumna `citext` przyjęła `gin_trgm_ops`
   bezpośrednio (indeks powstał), lecz `LIKE '%…%'` na `citext` go **nie użył** (Seq Scan,
   1768 buforów); zadziałał dopiero indeks na wyrażeniu `(email::text)` i zapytanie z tym samym
   rzutowaniem (661 buforów). Indeks, który się zbudował i nie jest używany, to zmarnowany koszt
   zapisu z sekcji 2.

## 5️⃣ 🧩 Co z tego wpada do skilla

Zmiany **zaproponowane**, nie wdrożone dziś (patrz sekcja 6):

| Reguła | Zmiana |
|---|---|
| `LIKE-LEADING-WILDCARD` (Npgsql) | komunikat dopisuje koszt: "GIN ~3x wolniejszy zapis niż btree, ~2x rozmiaru przy budowie przyrostowej" — z zastrzeżeniem, że to jedna maszyna |
| nowa `TOLOWER-NO-FUNC-INDEX` | `ToLower()`/`ToUpper()` w predykacie `==` → INFO: indeks funkcyjny albo `citext` |
| nowa `ILIKE-PATTERN-OPS` | `EF.Functions.ILike(x, "abc%")` → INFO: `pattern_ops` nie pomoże |
| `citext` + GIN | ostrzeżenie: indeks musi być na `(col::text)`, a zapytanie używać tego samego rzutowania |

## 6️⃣ ✅ Co zweryfikowano, a czego nie

| ✅ Zmierzone | ⚠️ Niezweryfikowane |
|---|---|
| PostgreSQL 16 w własnym kontenerze `prasowka-ai-pg-1016`; wszystkie liczby wyżej z `bench.sql`/`bench2.sql` | **Reguły skilla nie zostały zmienione ani przetestowane** — sekcja 5 to propozycja |
| Czasy `INSERT`/`UPDATE`/`CREATE INDEX`, rozmiary, plany z buforami | Czasy: pojedyncze uruchomienia, jedna maszyna, jeden kształt danych (200 000 e-maili) |
| `fastupdate` on/off, pending list przez `gin_metapage_info` | Test `fastupdate=off` na większej tabeli — nie jest czystym porównaniem |
| `citext`: indeks btree i GIN, plany | Brak wpływu kolacji, `citext` z kolacjami nie-ASCII; brak pomiaru autovacuum; brak pomiaru opóźnienia zapytania z pełną pending list |
| Kontener usunięty (`docker rm -f`), `docker ps -a` pokazuje tylko cudze | Żywa sesja `claude` i hook — nadal niesprawdzone (od #1) |
| | Spill typu Hash na SQL Server — brak SQL Servera, dalej dług |
| | Wartość `H9` (`gin_trgm_ops` na `citext`) przeszła bez błędu w tej wersji; inne wersje nie sprawdzane |

> 💡 **Wniosek:** indeks to nie prezent, tylko kredyt. GIN trigram zamienił 1696 buforów w 17
> przy odczycie, ale kosztował 3x więcej niż btree przy zapisie i bywa nieużywany, gdy typ
> kolumny jest "prawie ten sam" (`citext`). Skill ma pokazywać rachunek, nie samą poradę.

Następny krok: wdrożyć trzy proponowane reguły do `scan_ef.py` z testami, zmierzyć opóźnienie
zapytania przy pełnej pending list oraz (jeśli środowisko pozwoli) odpalić hook w żywej sesji
`claude` i zmierzyć spill typu Hash w SQL Server.

---

<div align="center">

[← wróć do wydania #23 (wszystkie rubryki)](../README.md) · [spis wydań](../../README.md)

</div>
