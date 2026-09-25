# Kod do wydania #1 — PostgreSQL jako baza wektorowa (`pgvector`)

Pełny artykuł: [`../ARTICLE.md`](../ARTICLE.md). Poniżej ten sam kod + jak go odpalić +
prawdziwy output z weryfikacji (skopiowany 1:1 z terminala, bez ręcznych poprawek).

Wymagania: **Docker** (`docker ps` działa). Nic więcej — `psql` odpalamy przez
`docker exec`, nie trzeba go instalować na hoście.

## Fragment prasówki, którego dotyczy ten kod

> `vector(4)` to typ danych ze sztywno zapisaną długością - dokładnie 4 liczby
> zmiennoprzecinkowe. Próba wstawienia wektora o innej liczbie wymiarów kończy się
> błędem na poziomie typu: `ERROR: expected 4 dimensions, not 3`.
>
> Typowe zapytanie k-NN to sortowanie po odległości i ucięcie do k wyników:
> `ORDER BY temat_wektor <-> '[1,0,0,0]' LIMIT 4`. `<->` to L2 (liczy się kierunek i
> długość wektora), `<=>` to odległość kosinusowa (liczy się tylko kierunek), `<#>` to
> ujemny iloczyn skalarny (jak `<=>`, ale bez normalizacji — szybszy, poprawny tylko dla
> wektorów już znormalizowanych do długości 1).
>
> IVFFlat dzieli dane na klastry (k-means) i szuka tylko w kilku najbliższych — trzeba
> budować na już wypełnionej tabeli. HNSW buduje graf sąsiedztw, rośnie przyrostowo z
> każdym `INSERT`-em, zwykle ma lepszy recall kosztem wolniejszej budowy i większego
> zużycia pamięci. Reguła kciuka: HNSW jako domyślny wybór.

**Ważne zastrzeżenie:** wektory `[0.90, 0.00, 0.00, 0.00]` itd. użyte niżej są **ręcznie
skonstruowane** (4 wymiary = [zwierzęta, technologia, sport, kuchnia], liczba = "jak
mocno tekst jest o tym temacie"), **nie** są embeddingami z prawdziwego modelu
językowego. Powód: brak miejsca na dysku dev-VM na `sentence-transformers`/PyTorch w
chwili przygotowania tego wydania — patrz sekcja 5 w [`../ARTICLE.md`](../ARTICLE.md).
Mechanika (typ kolumny, indeksy, zapytania, operatory) jest identyczna jak z prawdziwymi
embeddingami.

## Struktura

```
code/
├── run.sh              # odpala WSZYSTKO od zera i sprząta na końcu (jedna komenda)
└── sql/
    ├── 01_schema.sql        # CREATE EXTENSION vector; CREATE TABLE z kolumną vector(4)
    ├── 02_data.sql          # 8 wierszy z ręcznymi wektorami demonstracyjnymi
    ├── 03_index_ivfflat.sql # CREATE INDEX ... USING ivfflat
    ├── 04_index_hnsw.sql    # CREATE INDEX ... USING hnsw
    ├── 05_queries.sql       # ORDER BY <-> / <=> / <#> LIMIT k + EXPLAIN
    └── 06_bledy.sql         # demo błędu: wstawienie wektora o złej liczbie wymiarów
```

## Jak odpalić od zera

Jedna komenda — stawia kontener, ładuje wszystko, wypisuje wyniki i **usuwa kontener na
końcu**:

```bash
cd days/2026-09-24/postgres-vector/code
./run.sh
```

Albo ręcznie, krok po kroku (dokładnie to, co robi `run.sh` w środku):

```bash
docker run -d --name pgvector-demo \
  -e POSTGRES_PASSWORD=demo -e POSTGRES_USER=demo -e POSTGRES_DB=demo \
  -p 5544:5432 \
  pgvector/pgvector:pg16

# poczekaj aż wystartuje
docker exec pgvector-demo pg_isready -U demo

docker exec -i pgvector-demo psql -U demo -d demo < sql/01_schema.sql
docker exec -i pgvector-demo psql -U demo -d demo < sql/02_data.sql
docker exec -i pgvector-demo psql -U demo -d demo < sql/03_index_ivfflat.sql
docker exec -i pgvector-demo psql -U demo -d demo < sql/04_index_hnsw.sql
docker exec -i pgvector-demo psql -U demo -d demo < sql/05_queries.sql
docker exec -i pgvector-demo psql -U demo -d demo < sql/06_bledy.sql   # spodziewany błąd

# sprzątanie — NIE zostawiać kontenera w tle
docker rm -f pgvector-demo
```

## Prawdziwy output z weryfikacji (24.09.2026, `pgvector/pgvector:pg16`, obraz zbudowany na Postgresie 16.15, pgvector 0.8.6)

### Rozszerzenie

```
$ docker exec -i pgvector-demo psql -U demo -d demo -c "CREATE EXTENSION IF NOT EXISTS vector;"
CREATE EXTENSION

$ docker exec -i pgvector-demo psql -U demo -d demo -c "\dx vector"
                           List of installed extensions
  Name  | Version | Schema |                     Description
--------+---------+--------+------------------------------------------------------
 vector | 0.8.6   | public | vector data type and ivfflat and hnsw access methods
(1 row)
```

### Schemat tabeli (kolumna `vector(4)` + oba indeksy)

```
$ docker exec -i pgvector-demo psql -U demo -d demo -c "\d artykuly"
                                Table "public.artykuly"
    Column    |   Type    | Collation | Nullable |               Default
--------------+-----------+-----------+----------+---------------------------------------
 id           | integer   |           | not null | nextval('artykuly_id_seq'::regclass)
 tytul        | text      |           | not null |
 temat_wektor | vector(4) |           | not null |
Indexes:
    "artykuly_pkey" PRIMARY KEY, btree (id)
    "artykuly_hnsw_idx" hnsw (temat_wektor vector_l2_ops) WITH (m='16', ef_construction='64')
    "artykuly_ivfflat_idx" ivfflat (temat_wektor) WITH (lists='1')
```

### Zapytanie 1: `ORDER BY temat_wektor <-> '[1,0,0,0]' LIMIT 4` (temat "zwierzęta domowe")

```
                        tytul                         |  temat_wektor  | l2_dystans
------------------------------------------------------+----------------+------------
 Koty domowe śpią średnio 16 godzin na dobę           | [0.9,0,0,0]    |     0.1000
 Psy rasy border collie potrzebują długich spacerów   | [0.8,0,0.15,0] |     0.2500
 Kucharz przygotował rybę na obiad w restauracji      | [0.05,0,0,0.9] |     1.3086
 PostgreSQL to relacyjna baza danych z rozszerzeniami | [0,0.85,0,0]   |     1.3124
(4 rows)
```

Wynik ma sens: koty i psy (duża wartość w wymiarze "zwierzęta") są najbliżej. Ryba jest
trzecia, bo ma niewielką (0.05), ale niezerową wartość w tym wymiarze — bliżej niż czysto
technologiczny artykuł o Postgresie (który ma tam idealne zero).

### To samo zapytanie, `<=>` (kosinus) — pokazuje różnicę względem `<->`

```
                        tytul                         |  temat_wektor  | cosine_dystans
------------------------------------------------------+----------------+----------------
 Koty domowe śpią średnio 16 godzin na dobę           | [0.9,0,0,0]    |         0.0000
 Psy rasy border collie potrzebują długich spacerów   | [0.8,0,0.15,0] |         0.0171
 Kucharz przygotował rybę na obiad w restauracji      | [0.05,0,0,0.9] |         0.9445
 PostgreSQL to relacyjna baza danych z rozszerzeniami | [0,0.85,0,0]   |         1.0000
(4 rows)
```

Zwróć uwagę: artykuł o Postgresie dostał dystans dokładnie `1.0000` — bo jego wektor jest
**ortogonalny** (prostopadły, iloczyn skalarny = 0) do zapytania, a kosinus liczy tylko
kąt, nie długość. Przy `<->` (L2) ten sam wiersz miał `1.3124`, nie identyczny z innymi
ortogonalnymi wektorami — bo L2 uwzględnia też długość wektora w pozostałych wymiarach.
To realna, zmierzona różnica między obiema metrykami, nie teoria.

### To samo zapytanie, `<#>` (ujemny iloczyn skalarny)

```
                        tytul                         |  temat_wektor  | neg_inner_product
------------------------------------------------------+----------------+-------------------
 Koty domowe śpią średnio 16 godzin na dobę           | [0.9,0,0,0]    |           -0.9000
 Psy rasy border collie potrzebują długich spacerów   | [0.8,0,0.15,0] |           -0.8000
 Kucharz przygotował rybę na obiad w restauracji      | [0.05,0,0,0.9] |           -0.0500
 PostgreSQL to relacyjna baza danych z rozszerzeniami | [0,0.85,0,0]   |            0.0000
(4 rows)
```

Wartości ujemne — zgodnie z konwencją pgvector (`<#>` zwraca `-1 * iloczyn_skalarny`, żeby
zwykłe `ORDER BY ASC` dawało "najbardziej podobne pierwsze").

### Zapytanie 2: inny temat zapytania (`[0,0,0.5,0.5]` — "sport + kuchnia")

```
                          tytul                          |  temat_wektor  | l2_dystans
---------------------------------------------------------+----------------+------------
 Reprezentacja wygrała mecz piłki nożnej w finale        | [0,0,0.9,0.05] |     0.6021
 Kucharz przygotował rybę na obiad w restauracji         | [0.05,0,0,0.9] |     0.6423
 Koszykówka to jeden z najpopularniejszych sportów w USA | [0,0,0.95,0]   |     0.6727
 Przepis na pierogi z kapustą i grzybami na wigilię      | [0,0,0,0.95]   |     0.6727
(4 rows)
```

Zmiana zapytania od razu zmieniła kolejność wyników — teraz na górze sport i jedzenie,
koty/GPU/Postgres wypadły poza top 4. Dokładnie tego oczekiwaliśmy od wektorów
skonstruowanych tak, jak je skonstruowaliśmy.

### `EXPLAIN` — ciekawy, prawdziwy wynik: planer olewa indeks na małej tabeli

```
$ docker exec -i pgvector-demo psql -U demo -d demo -c "EXPLAIN SELECT tytul FROM artykuly ORDER BY temat_wektor <-> '[1,0,0,0]' LIMIT 4;"
                             QUERY PLAN
---------------------------------------------------------------------
 Limit  (cost=1.22..1.23 rows=4 width=40)
   ->  Sort  (cost=1.22..1.24 rows=8 width=40)
         Sort Key: ((temat_wektor <-> '[1,0,0,0]'::vector))
         ->  Seq Scan on artykuly  (cost=0.00..1.10 rows=8 width=40)
(4 rows)
```

Przy 8 wierszach pełne skanowanie + sortowanie jest tańsze niż nawigacja po indeksie —
optymalizator ma rację, to nie błąd konfiguracji. Wymuszenie użycia indeksu pokazuje, że
**oba indeksy realnie działają** i dają identyczny wynik zapytania:

```
$ docker exec -i pgvector-demo psql -U demo -d demo -c "
SET enable_seqscan = off;
EXPLAIN SELECT tytul FROM artykuly ORDER BY temat_wektor <-> '[1,0,0,0]' LIMIT 4;"
                                         QUERY PLAN
---------------------------------------------------------------------------------------------
 Limit  (cost=7.56..9.61 rows=4 width=40)
   ->  Index Scan using artykuly_ivfflat_idx on artykuly  (cost=7.56..11.66 rows=8 width=40)
         Order By: (temat_wektor <-> '[1,0,0,0]'::vector)
(3 rows)

$ docker exec -i pgvector-demo psql -U demo -d demo -c "
SET enable_seqscan = off;
SELECT tytul, round((temat_wektor <-> '[1,0,0,0]')::numeric,4) AS l2 FROM artykuly ORDER BY temat_wektor <-> '[1,0,0,0]' LIMIT 4;"
                        tytul                         |   l2
------------------------------------------------------+--------
 Koty domowe śpią średnio 16 godzin na dobę           | 0.1000
 Psy rasy border collie potrzebują długich spacerów   | 0.2500
 Kucharz przygotował rybę na obiad w restauracji      | 1.3086
 PostgreSQL to relacyjna baza danych z rozszerzeniami | 1.3124
(4 rows)
```

Identyczny wynik jak bez wymuszania indeksu — potwierdza, że indeks zwraca poprawne
odpowiedzi, planer po prostu (słusznie) go tu nie potrzebuje.

### Demo błędu: zły wymiar wektora

```
$ docker exec -i pgvector-demo psql -U demo -d demo -c "INSERT INTO artykuly (tytul, temat_wektor) VALUES ('x', '[1,2,3]');"
ERROR:  expected 4 dimensions, not 3
```

### Sprzątanie po weryfikacji

```bash
docker rm -f pgvector-demo
```

Kontener zatrzymany i usunięty — `docker ps -a` po tej komendzie nie pokazuje
`pgvector-demo`. Obraz `pgvector/pgvector:pg16` też usunięty po weryfikacji
(`docker rmi pgvector/pgvector:pg16`), żeby oddać miejsce na dysku dev-VM — przy
ponownym odpaleniu `./run.sh` obraz pobierze się od nowa automatycznie.

Wszystkie powyższe bloki to dosłowny output z terminala podczas przygotowania tego
wydania — bez ręcznych poprawek liczb.
