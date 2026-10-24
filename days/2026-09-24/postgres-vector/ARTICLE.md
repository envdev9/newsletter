<div align="center">

# 📰 TECH PRASÓWKA
### Wydanie #1 — 24 września 2026

![PostgreSQL + pgvector](https://img.shields.io/badge/PostgreSQL_%2B_pgvector-4169E1?style=for-the-badge&logo=postgresql&logoColor=white)

## PostgreSQL jako baza wektorowa: `pgvector` od zera

</div>

---

> _"Nie potrzebujesz nowej bazy danych do wyszukiwania semantycznego - potrzebujesz
> jednego `CREATE EXTENSION` w bazie, która już u ciebie stoi."_

Dziś zupełne podstawy `pgvector` - rozszerzenia PostgreSQL, które dorzuca nowy typ
kolumny (`vector(N)`) i nowe operatory odległości, dzięki czemu zwykła relacyjna baza
danych potrafi robić to, co dotąd kojarzyło się z osobnymi, egzotycznymi "wektorowymi
bazami danych" (Pinecone, Weaviate, Qdrant...). Zero płatnych API - cały przykład w
[`code/`](code/) sprawdzony lokalnie na `pgvector/pgvector:pg16` w Dockerze.

**Uczciwe zastrzeżenie na start:** wektory użyte w przykładzie kodu są **ręcznie
skonstruowane**, nie są embeddingami z prawdziwego modelu językowego. To celowe - patrz
sekcja "Jaki model embeddingowy?" niżej.

---

## 1️⃣ Czym w ogóle jest "wyszukiwanie wektorowe"?

### Problem, który to rozwiązuje

Klasyczne `WHERE tytul LIKE '%kot%'` znajdzie tylko teksty, które **dosłownie** zawierają
słowo "kot". Nie znajdzie tekstu o "kocurze" ani o "zwierzętach domowych", mimo że dla
człowieka to oczywiste skojarzenie. Wyszukiwanie pełnotekstowe (`tsvector`/`tsquery` w
Postgresie) trochę to łagodzi (odmiany, synonimy przez słowniki), ale wciąż operuje na
**słowach**, nie na **znaczeniu**.

Wyszukiwanie wektorowe robi coś innego: zamienia każdy tekst (albo obraz, dźwięk...) na
listę liczb - **wektor** - w taki sposób, że teksty o podobnym znaczeniu dostają wektory,
które są **blisko siebie** w przestrzeni wielowymiarowej. "Kot śpi na kanapie" i "Kocur
drzemie na sofie" wylądują blisko siebie, mimo że nie mają wspólnych słów. Samo znalezienie
"tego co najbliżej" to potem czysta geometria - liczenie odległości między punktami.

### Skąd się biorą te liczby (embeddingi)?

W prawdziwym systemie ten wektor liczb ("embedding") produkuje **model** (np. sieć
neuronowa wytrenowana na tekstach) - to osobny temat, dziś go nie trenujemy ani nie
odpalamy w pełnej postaci (patrz zastrzeżenie o budżecie niżej). Na potrzeby dzisiejszego
wydania interesuje nas coś innego: **co Postgres robi z takim wektorem, gdy już go ma** -
jak go przechowuje, indeksuje i przeszukuje. Ta mechanika jest identyczna niezależnie od
tego, czy wektor wyprodukował ciężki model językowy, czy - jak w naszym przykładzie -
człowiek, który ręcznie przypisał liczby.

---

## 2️⃣ Kolumna `vector(N)` - jak to wygląda w tabeli

### Instalacja rozszerzenia

`pgvector` to rozszerzenie, nie osobna baza danych - instalujesz je **w konkretnej bazie**
jednym poleceniem:

```sql
CREATE EXTENSION IF NOT EXISTS vector;
```

Obraz Dockera `pgvector/pgvector:pg16` ma je już wbudowane (skompilowane, tylko czeka na
`CREATE EXTENSION`) - nie trzeba nic kompilować ręcznie.

### Kolumna wektorowa

```sql
CREATE TABLE artykuly (
    id           serial PRIMARY KEY,
    tytul        text NOT NULL,
    temat_wektor vector(4) NOT NULL
);
```

`vector(4)` to typ danych ze **sztywno zapisaną długością** - dokładnie 4 liczby
zmiennoprzecinkowe, ani mniej, ani więcej. To samo zabezpieczenie co np. `char(10)` w SQL:
próba wstawienia wektora o innej liczbie wymiarów kończy się błędem na poziomie typu:

```
ERROR:  expected 4 dimensions, not 3
```

(Ten błąd sprawdziliśmy naprawdę - patrz [`code/README.md`](code/README.md).) W
prawdziwym systemie RAG ta liczba to wymiar embeddingu z konkretnego modelu (popularne
wartości: 384, 768, 1536) - musi być identyczna dla całej kolumny, bo dwóch wektorów o
różnej długości nie da się w ogóle ze sobą porównać geometrycznie.

Wstawianie wygląda jak wstawianie tekstu - wektor to string w nawiasach kwadratowych:

```sql
INSERT INTO artykuly (tytul, temat_wektor)
VALUES ('Koty domowe śpią średnio 16 godzin na dobę', '[0.90, 0.00, 0.00, 0.00]');
```

---

## 3️⃣ Jak wygląda realne wyszukiwanie podobieństwa

Zero `WHERE`. Typowe zapytanie k-NN (k-nearest-neighbors, "k najbliższych sąsiadów") to
**sortowanie po odległości i ucięcie do k wyników**:

```sql
SELECT tytul
FROM artykuly
ORDER BY temat_wektor <-> '[1,0,0,0]'
LIMIT 4;
```

`<->` to operator odległości - "policz, jak daleko jest każdy wiersz od tego wektora, i
posortuj rosnąco" (im mniejsza odległość, tym bardziej podobne). `LIMIT 4` ucina do
czterech najbliższych. Bez indeksu Postgres policzyłby to dla **każdego** wiersza
(sekwencyjne skanowanie) - przy milionie wierszy i wektorach o setkach wymiarów to
realnie wolne. Stąd indeksy wektorowe (sekcja 4).

### Trzy operatory odległości - i dlaczego akurat te trzy

pgvector daje trzy sposoby liczenia "jak daleko":

| Operator | Nazwa | Co mierzy | Kiedy używać |
|---|---|---|---|
| `<->` | odległość euklidesowa (L2) | odległość "w linii prostej", liczy się **kierunek i długość** wektora | ogólny przypadek, dane nieznormalizowane |
| `<=>` | odległość kosinusowa | liczy się **wyłącznie kąt** między wektorami, długość nie ma znaczenia | najpopularniejszy wybór dla embeddingów tekstowych - liczy się "o czym", nie "jak intensywnie" |
| `<#>` | ujemny iloczyn skalarny | jak `<=>`, ale bez normalizacji - szybszy, poprawny **tylko** gdy wektory są już znormalizowane do długości 1 | wektory już znormalizowane, liczy się każda mikrosekunda |

`<#>` zwraca wynik **ze znakiem minus** - to nie pomyłka. Postgres potrafi używać indeksu
tylko przy sortowaniu rosnąco, a "większy iloczyn skalarny = bardziej podobne", więc
pgvector odwraca znak, żeby zwykłe `ORDER BY ... ASC` dawało poprawną kolejność
(najbardziej podobne pierwsze), spójną z `<->` i `<=>`.

**Realny przykład różnicy między `<->` a `<=>`** (pełne dane i wynik w
[`code/README.md`](code/README.md)): zapytanie `[1,0,0,0]` ("temat: zwierzęta") vs. cztery
teksty o tematach GPU/Postgres/piłka/koszykówka/pierogi - wszystkie mają **zero** w
wymiarze "zwierzęta", więc są od niego **ortogonalne**. Po `<=>` (kosinus) wszystkie
dostają identyczny dystans `1.0000` - kosinus widzi tylko kierunek, a "brak związku ze
zwierzętami" to dla każdego z nich ten sam kierunek (prostopadły). Po `<->` (L2) te same
wiersze mają **różne** dystanse (`1.3086`, `1.3124`, ...), bo L2 uwzględnia też długość
wektora w pozostałych wymiarach. To nie jest teoria z podręcznika - to prawdziwy wynik
zapytania na naszych danych.

---

## 4️⃣ Indeksy: IVFFlat vs HNSW - od podstaw

Bez indeksu `ORDER BY ... <-> ...` to zawsze **pełne skanowanie** (policz odległość do
każdego wiersza, posortuj wszystko, utnij do k). Dokładne, ale liniowo wolniejsze wraz z
rozmiarem tabeli. Indeksy wektorowe w pgvector są **przybliżone** (ANN - Approximate
Nearest Neighbors) - świadomie rezygnują z gwarancji "zawsze dokładnie k najbliższych" w
zamian za drastyczne przyspieszenie. W praktyce przy dobrze dobranych parametrach różnica
w trafności jest minimalna, a różnica w szybkości - ogromna.

### IVFFlat - dziel na klastry, szukaj tylko w kilku

**Budowa:** algorytm k-means dzieli WSZYSTKIE wektory w tabeli na `lists` klastrów -
grupuje bliskie sobie punkty, znajduje "środek ciężkości" (centroid) każdej grupy.

**Wyszukiwanie:** zamiast liczyć odległość do każdego wiersza, baza najpierw znajduje
kilka najbliższych centroidów (parametr `probes`), a dopiero **w tych klastrach** liczy
dokładnie. Jeśli szukany wynik leży tuż przy granicy klastra, który akurat nie został
przeszukany - można go przegapić. Stąd "przybliżone".

**Kluczowe ograniczenie praktyczne:** IVFFlat trzeba budować **na już wypełnionej
tabeli** - k-means potrzebuje danych, żeby wyznaczyć sensowne klastry. Jeśli zbudujesz
indeks na pustej/małej tabeli, a potem dorzucisz dużo nowych danych o innym rozkładzie,
klastry przestają pasować i trzeba przebudować indeks (`REINDEX`).

```sql
CREATE INDEX artykuly_ivfflat_idx
    ON artykuly
    USING ivfflat (temat_wektor vector_l2_ops)
    WITH (lists = 1);
```

`vector_l2_ops` mówi indeksowi, dla którego operatora odległości go budujemy (tu: `<->`;
jest też `vector_cosine_ops` dla `<=>` i `vector_ip_ops` dla `<#>` - indeks trzeba
zbudować osobno pod każdy operator, którego realnie używasz). Oficjalna rekomendacja
pgvector na `lists`: `rows / 1000` dla tabel do ~1 mln wierszy, `sqrt(rows)` dla
większych. Nasza tabela demo ma 8 wierszy, więc wzięliśmy praktyczne minimum `lists = 1`
- w tej skali indeks i tak przeszukuje wszystko, więc demo pokazuje **składnię**, nie
przyspieszenie (które ma sens dopiero przy tysiącach/milionach wierszy).

### HNSW - graf sąsiedztw zamiast klastrów

**Budowa:** zamiast dzielić dane na grupy, HNSW buduje **graf** - każdy wektor ma
połączenia do kilku najbliższych "sąsiadów", z dodatkowymi warstwami "autostrad"
łączącymi odległe rejony grafu (stąd "hierarchical" w nazwie), żeby dało się szybko
przeskoczyć w dobry rejon zamiast iść krok po kroku po najbliższych sąsiadach.

**Wyszukiwanie:** start w losowym punkcie górnej (rzadkiej) warstwy grafu, nawigacja w
stronę zapytania, schodzenie do gęstszych warstw, aż trafi się blisko prawdziwych
najbliższych sąsiadów.

**Różnica względem IVFFlat, która ma znaczenie w praktyce:**

| | IVFFlat | HNSW |
|---|---|---|
| Wymaga danych do budowy | tak (k-means na już wypełnionej tabeli) | nie - graf rośnie przyrostowo z każdym `INSERT`-em |
| Trafność (recall) przy podobnej szybkości zapytań | niższa | zwykle wyższa |
| Szybkość budowy indeksu | szybsza | wolniejsza |
| Zużycie pamięci/dysku | mniejsze (lista klastrów) | większe (graf z wieloma połączeniami) |
| Dobre dla danych napływających na bieżąco | słabo (klastry się "starzeją") | dobrze |

```sql
CREATE INDEX artykuly_hnsw_idx
    ON artykuly
    USING hnsw (temat_wektor vector_l2_ops)
    WITH (m = 16, ef_construction = 64);
```

`m` = maksymalna liczba połączeń na węzeł grafu (domyślnie 16 - wyżej: lepszy recall,
więcej pamięci). `ef_construction` = jak szeroko przeszukiwać przy budowie grafu
(domyślnie 64 - wyżej: wolniejsza budowa, lepsza jakość). Wartości domyśle wystarczają na
start.

### Kiedy który?

**Reguła kciuka: HNSW jest domyślnym wyborem** w większości nowych projektów z pgvector -
lepszy recall, prostsza eksploatacja (nie trzeba dbać o "przebudowę po zmianie
rozkładu danych"). IVFFlat ma sens, gdy zależy ci na szybszym zbudowaniu bardzo dużego, w
większości statycznego indeksu (jednorazowy import, potem głównie odczyt) i akceptujesz
nieco gorszą trafność w zamian za szybszą budowę i mniejsze zużycie zasobów.

### Ciekawostka z weryfikacji: na małej tabeli planer olewa indeks

Przy sprawdzaniu przykładu (`EXPLAIN` na tabeli z 8 wierszami) Postgres **wybrał pełne
skanowanie zamiast indeksu**, mimo że oba indeksy (IVFFlat i HNSW) istniały:

```
Limit  (cost=1.22..1.23 rows=4 width=40)
  ->  Sort  (cost=1.22..1.24 rows=8 width=40)
        ->  Seq Scan on artykuly  (cost=0.00..1.10 rows=8 width=40)
```

To nie błąd - to prawidłowa decyzja optymalizatora: przy 8 wierszach posortowanie
wszystkiego jest po prostu tańsze niż nawigacja po strukturze indeksu. Wymuszenie użycia
indeksu (`SET enable_seqscan = off;`) pokazuje, że oba indeksy **działają poprawnie** i
zwracają identyczny wynik:

```
Limit  (cost=7.56..9.61 rows=4 width=40)
  ->  Index Scan using artykuly_ivfflat_idx on artykuly (cost=7.56..11.66 rows=8 width=40)
```

Na tabeli z milionami wierszy planer sam wybierze indeks, bo tam faktycznie jest tańszy.
Pełny log tego eksperymentu (obie wersje `EXPLAIN`, ten sam wynik zapytania) jest w
[`code/README.md`](code/README.md).

---

## 5️⃣ Jaki model embeddingowy? (i dlaczego dziś żaden)

Zgodnie z linią redakcyjną tej rubryki - zero płatnych kluczy API (żadnego OpenAI itp.).
Realna, lokalna alternatywa to mały model przez `sentence-transformers` w Pythonie (np.
`all-MiniLM-L6-v2`, ~90 MB) - działa offline, bez opłat. W środowisku, w którym
przygotowano to wydanie, zabrakło jednak na to miejsca na dysku (VM ma 40 GB, w chwili
przygotowania przykładu zostało < 1 GB wolnego, a `sentence-transformers` + PyTorch to
kolejne >1-2 GB zależności) - więc **dzisiejszy przykład używa ręcznie skonstruowanych,
4-wymiarowych wektorów demonstracyjnych** (temat: zwierzęta/technologia/sport/kuchnia),
jasno oznaczonych jako takie w kodzie i w tabeli wyżej.

To nie jest oszustwo pod płaszczykiem uproszczenia - mechanika, którą dziś poznajesz
(typ `vector(N)`, `CREATE INDEX ... USING ivfflat/hnsw`, `ORDER BY ... <-> ... LIMIT k`,
różnica `<->`/`<=>`/`<#>`) jest **dokładnie ta sama**, niezależnie od tego, skąd wziął się
wektor. Prawdziwy lokalny model embeddingowy (`sentence-transformers` albo mniejsza
alternatywa) to naturalny temat na kolejne wydanie tej rubryki, gdy będzie więcej miejsca
na dysku.

---

## 📎 Jak uruchomić kod z tego wydania

Zobacz [`code/README.md`](code/README.md) - jedna komenda (`./run.sh`) odpala kontener,
tworzy schemat, ładuje dane, buduje oba indeksy, wykonuje realne zapytania i **sprząta po
sobie** (usuwa kontener na koniec).

---

<div align="center">

[← wróć do wydania #1 (wszystkie rubryki)](../README.md) · [spis wydań](../../README.md)

</div>
