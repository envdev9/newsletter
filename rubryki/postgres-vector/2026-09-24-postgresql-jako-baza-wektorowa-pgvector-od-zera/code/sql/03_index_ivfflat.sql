-- IVFFlat ("Inverted File with Flat compression") - pierwszy typ indeksu
-- przybliżonego wyszukiwania najbliższych sąsiadów w pgvector.
--
-- Jak to działa (w skrócie): przy budowie indeksu pgvector dzieli WSZYSTKIE
-- wektory na `lists` klastrów metodą k-means (tak jak grupowanie punktów na
-- mapie w "dzielnice"). Każdy wektor trafia do jednego klastra, do którego
-- jego środek (centroid) jest najbliżej. Przy wyszukiwaniu baza NIE
-- porównuje zapytania ze wszystkimi wierszami - najpierw znajduje kilka
-- najbliższych centroidów (`probes`), a dopiero w tych klastrach szuka
-- dokładnie. To szybsze niż pełne skanowanie, ale przybliżone: jeśli
-- właściwy wynik leży tuż przy granicy klastra, którego nie przeszukano,
-- można go przegapić.
--
-- Kluczowa wada w praktyce: IVFFlat trzeba ZBUDOWAĆ na już wypełnionej
-- tabeli (k-means potrzebuje danych, żeby wyznaczyć klastry) i przebudować,
-- gdy dane się mocno zmienią - inaczej klastry przestają pasować do
-- rozkładu danych i jakość wyszukiwania spada.
--
-- `lists` = liczba klastrów. Oficjalna rekomendacja pgvector:
--   lists = rows / 1000   dla tabel do ~1 mln wierszy
--   lists = sqrt(rows)    dla większych tabel
-- Przy 8 wierszach matematycznie wyszłoby < 1, więc bierzemy praktyczne
-- minimum: lists = 1 (czyli w tym mikro-przykładzie IVFFlat i tak
-- przeszukuje wszystko - demo pokazuje SKŁADNIĘ, nie przyspieszenie, które
-- ma sens dopiero przy tysiącach/milionach wierszy).
CREATE INDEX artykuly_ivfflat_idx
    ON artykuly
    USING ivfflat (temat_wektor vector_l2_ops)
    WITH (lists = 1);
