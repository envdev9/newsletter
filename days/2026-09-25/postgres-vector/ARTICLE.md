<div align="center">

# 📰 TECH PRASÓWKA
### Wydanie #2 — 25 września 2026

![PostgreSQL + pgvector](https://img.shields.io/badge/PostgreSQL_%2B_pgvector-4169E1?style=for-the-badge&logo=postgresql&logoColor=white)
![Poziom](https://img.shields.io/badge/poziom-%C5%9Bredni-orange?style=for-the-badge)
![Status kodu](https://img.shields.io/badge/kod-NIE_uruchomiony_w_tym_wydaniu-red?style=for-the-badge)

## Hybrid search i strojenie indeksów: wektor + tsvector + Reciprocal Rank Fusion

</div>

---

> _"Wyszukiwanie wektorowe zna znaczenie, wyszukiwanie pełnotekstowe zna słowa. Kod błędu `40001`
> nie ma 'znaczenia' - a użytkownik i tak będzie go wpisywał."_

> ⚠️ **UCZCIWA NOTA O STANIE TEGO WYDANIA (przeczytaj najpierw).**
> Kod w [`code/`](code/) został napisany w całości, ale **nie został w tym wydaniu uruchomiony**:
> uruchomienie `run-demo.sh` zostało odrzucone przez uprawnienia środowiska (zablokowane też
> `chmod +x`), a zasada tej rubryki brzmi: nie obchodzimy blokady i nie zmyślamy outputu.
> Dlatego **w tym artykule nie ma ani jednej liczby z pomiaru** - żadnego recallu, żadnego czasu.
> Wszystko poniżej o zachowaniu kodu to **oczekiwania wynikające z dokumentacji pgvector**,
> a nie wyniki. Co zostało zweryfikowane realnie: obraz `pgvector/pgvector:pg16` da się pobrać, a
> kontener `python:3.12-slim` ma dostęp do PyPI (`pip download fastembed` przeszło). Reszta - do
> zweryfikowania przez ciebie jedną komendą (sekcja "Jak uruchomić").

---

## 🎯 Dlaczego to ważne

Wydanie #1 skończyło się na `ORDER BY emb <-> q LIMIT k`. W prawdziwym produkcie to za mało z dwóch
powodów:

1. **Wektor gubi dokładne tokeny** - kody błędów, identyfikatory, nazwy parametrów (`ef_search`,
   `40001`). Model embeddingowy rozmywa je w "znaczenie". Pełnotekstowe je łapie bezbłędnie.
2. **Indeks przybliżony to pokrętła, nie magia** - `lists/probes` i `m/ef_construction/ef_search`
   wymieniają recall na czas. Bez pomiaru "względem dokładnego wyszukiwania" nie wiesz, co oddałeś.

## 1️⃣ Hybrid search: dwa rankingi, jeden wynik

| | 🧠 Wektorowe | 🔤 Pełnotekstowe (`tsvector`) |
|---|---|---|
| Mocna strona | parafrazy, synonimy, inny język | dokładne tokeny, rzadkie słowa |
| Słaba strona | rzadkie identyfikatory, kody | brak wspólnych słów = brak trafień |
| Indeks w Postgresie | HNSW / IVFFlat | **GIN** na kolumnie `tsvector` |
| Wynik | odległość (`<=>`) | `ts_rank_cd` |

Problem: odległość kosinusowa i `ts_rank_cd` to **różne skale** - nie da się ich sensownie dodać.
**Reciprocal Rank Fusion (RRF)** omija ten kłopot, bo ignoruje wartości i patrzy tylko na
**pozycję** w każdej liście:

```
rrf(dok) = Σ po listach  1 / (k + pozycja_w_liście)      k = 60 (stała z pracy Cormacka i in.)
```

Dokument wysoko w obu listach wygrywa; dokument tylko w jednej nadal dostaje punkty. W repo
([`sql/03_hybrid_rrf.sql`](code/sql/03_hybrid_rrf.sql)) to jedno zapytanie: dwa CTE
(`vec`, `fts`) z `row_number()`, `FULL OUTER JOIN` i suma `1/(60+rnk)`.

Trzy szczegóły wdrożeniowe, na które warto uważać:

- **`tsvector` jako kolumna generowana** (`GENERATED ALWAYS AS (to_tsvector('simple', body)) STORED`)
  - Postgres sam go utrzymuje; do tego `CREATE INDEX ... USING gin (tsv)`.
- **Konfiguracja `simple`**: w obrazie nie ma polskiego słownika (stemmingu), więc tekst jest
  tylko rozbijany na słowa i sprowadzany do małych liter. Efekt: "indeksu" != "indeks". To
  ograniczenie realne - i dobry powód, dla którego wektory dokładają wartość.
- **AND vs OR w zapytaniu**: `websearch_to_tsquery` łączy słowa przez AND, więc długie zdanie
  prawie nigdy nic nie zwróci. Kod składa `tsquery` z operatorem `|` (OR) i pozwala `ts_rank_cd`
  premiować dokumenty trafiające w więcej słów.

## 2️⃣ Prawdziwy model, bez kluczy

Zamiast ręcznych 4-wymiarowych wektorów z wydania #1 kod używa **`paraphrase-multilingual-MiniLM-L12-v2`**
(384 wymiary, wielojęzyczny - obsługuje polski) uruchamianego lokalnie przez **`fastembed`**
(ONNX Runtime, bez PyTorcha, więc lekko: dysk ma dużo wolnego miejsca, nie potrzeba GPU ani
płatnych kluczy). Model pobiera się z internetu przy pierwszym uruchomieniu (rzędu 200+ MB -
dokładnego rozmiaru nie zmierzyłem).

Uczciwe zastrzeżenie o danych: 24 dokumenty bazy wiedzy (`kb`) do demo hybrid search są napisane
ręcznie, ale **korpus do pomiaru indeksów jest sztuczny** - zdania składane z szablonów (6 tematów).
Embeddingi są prawdziwe, tekst nie. To wystarcza do mierzenia zachowania indeksu, ale rozkład
takich danych bywa łatwiejszy (lub inny) niż w realnym korpusie, więc **wyniki strojenia nie
przenoszą się 1:1** na twoje dane. Zmierz na własnych.

## 3️⃣ Strojenie: co jest pokrętłem

| Indeks | Parametr | Kiedy działa | Więcej = |
|---|---|---|---|
| IVFFlat | `lists` (budowa) | na ile klastrów podzielić dane | mniejsze klastry, szybsze skanowanie, ale trzeba więcej `probes` |
| IVFFlat | `ivfflat.probes` (zapytanie) | ile klastrów przeszukać | wyższy recall, wolniej; `probes = lists` = wynik dokładny |
| HNSW | `m` (budowa) | liczba połączeń na węzeł | wyższy recall, większy indeks |
| HNSW | `ef_construction` (budowa) | szerokość szukania przy budowie | lepszy graf, wolniejsza budowa |
| HNSW | `hnsw.ef_search` (zapytanie) | ilu kandydatów śledzi zapytanie | wyższy recall, wolniej |

Wskazówka z dokumentacji pgvector: `ef_search` (domyślnie 40) powinno być **>= `LIMIT`**, bo indeks
nie zwróci więcej wyników niż kandydatów, których śledzi.

**Metodologia pomiaru w [`py/tuning.py`](code/py/tuning.py)** (to jest ważniejsze niż same liczby):

1. Prawda: `ORDER BY emb <=> q LIMIT 10` na tabeli **bez indeksu** (Seq Scan) = dokładni sąsiedzi.
2. Dla każdej konfiguracji: budowa indeksu (czas + rozmiar), potem 100 zapytań (jedno przejście
   rozgrzewkowe, jedno mierzone).
3. **recall@10** = średnia z |wynik ∩ prawda| / 10; obok średni i p95 czas oraz krotność względem Seq Scan.
4. Kontrola `EXPLAIN`: skrypt ostrzega, gdy planner **nie użył** indeksu (wtedy "recall 100%" byłby
   złudny - to byłby po prostu Seq Scan).
5. `max_parallel_workers_per_gather = 0` - jeden rdzeń, żeby porównanie było uczciwe i powtarzalne.

Czego spodziewać się po dokumentacji (**hipoteza, nie wynik**): recall rośnie z `probes`/`ef_search`,
czas też; przy `probes = lists` IVFFlat degeneruje do pełnego skanu. Czy na tym korpusie (8000 x 384)
indeks w ogóle wygra z Seq Scan i ile - tego **nie wiem**, dopóki ktoś nie uruchomi skryptu.

## 📊 Wyniki pomiarów

**Brak.** Skrypt nie został uruchomiony w tym wydaniu (patrz nota na górze). Po uruchomieniu
`run-demo.sh` wklej output do [`code/README.md`](code/README.md) - tabela wygeneruje się sama.

## 🚀 Jak uruchomić

```bash
cd days/2026-09-25/postgres-vector/code
bash run-demo.sh          # Docker + internet; sprząta własny kontener i sieć
```

Szczegóły i strukturę katalogu opisuje [`code/README.md`](code/README.md).

---

<div align="center">

[← wróć do wydania #2 (wszystkie rubryki)](../README.md) · [spis wydań](../../README.md)

</div>
