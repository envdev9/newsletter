-- Realne wyszukiwanie podobieństwa. Zapytanie NIE ma WHERE - typowe użycie
-- pgvector to "znajdź k najbliższych" (k-NN), więc mechanizm to ORDER BY
-- <operator odległości> query_vector LIMIT k. Baza (z indeksem HNSW/IVFFlat)
-- nie musi liczyć odległości do wszystkich wierszy - to jest cały sens
-- indeksu wektorowego.
--
-- Trzy operatory odległości pgvector - wszystkie zwracają "im mniej, tym
-- bliżej" (nawet <#>, mimo nazwy "inner product" - patrz niżej):
--
--   <->   odległość euklidesowa (L2). Klasyczna odległość "w linii prostej"
--         między dwoma punktami w przestrzeni N-wymiarowej. Uwzględnia
--         zarówno KIERUNEK, jak i DŁUGOŚĆ (magnitude) wektora.
--
--   <=>   odległość kosinusowa = 1 - cosinus kąta między wektorami.
--         Liczy się WYŁĄCZNIE kierunek - dwa wektory wskazujące dokładnie
--         w tę samą stronę mają dystans 0, niezależnie od tego, jak długi
--         jest każdy z nich. To najpopularniejszy wybór dla embeddingów z
--         modeli językowych, bo tam zwykle liczy się "o czym jest tekst",
--         nie "jak bardzo intensywnie".
--
--   <#>   ujemny iloczyn skalarny (negative inner product). Postgres
--         potrafi używać indeksu tylko przy sortowaniu ROSNĄCO, a "większy
--         iloczyn skalarny = bardziej podobne" - więc pgvector zwraca
--         iloczyn ZE ZNAKIEM MINUS, żeby zwykłe ORDER BY ... ASC dawało
--         poprawną kolejność (najbardziej podobne pierwsze). Używane
--         głównie, gdy embeddingi są już znormalizowane do długości 1 -
--         wtedy wynik pokrywa się z odległością kosinusową, ale liczy się
--         szybciej (bez dzielenia przez normy wektorów).
--
-- Zapytanie 1: "zwierzęta domowe" -> wektor [1, 0, 0, 0].
-- Oczekiwanie: na górze koty i psy (mają duże wartości w wymiarze
-- "zwierzęta"), reszta daleko.
SELECT tytul,
       temat_wektor,
       round((temat_wektor <-> '[1,0,0,0]')::numeric, 4) AS l2_dystans
FROM artykuly
ORDER BY temat_wektor <-> '[1,0,0,0]'
LIMIT 4;

SELECT tytul,
       temat_wektor,
       round((temat_wektor <=> '[1,0,0,0]')::numeric, 4) AS cosine_dystans
FROM artykuly
ORDER BY temat_wektor <=> '[1,0,0,0]'
LIMIT 4;

SELECT tytul,
       temat_wektor,
       round((temat_wektor <#> '[1,0,0,0]')::numeric, 4) AS neg_inner_product
FROM artykuly
ORDER BY temat_wektor <#> '[1,0,0,0]'
LIMIT 4;

-- Zapytanie 2: temat "pomiędzy sportem a kuchnią" -> wektor [0, 0, 0.5, 0.5].
-- Oczekiwanie: piłka nożna/koszykówka i pierogi/ryba na górze (mają
-- niezerowe wartości w wymiarach sport/kuchnia), koty/GPU/postgres na dole.
SELECT tytul,
       temat_wektor,
       round((temat_wektor <-> '[0,0,0.5,0.5]')::numeric, 4) AS l2_dystans
FROM artykuly
ORDER BY temat_wektor <-> '[0,0,0.5,0.5]'
LIMIT 4;

-- Dowód, że indeks faktycznie jest używany (nie tylko "utworzony i leży
-- odłogiem"): EXPLAIN pokazuje plan zapytania.
EXPLAIN SELECT tytul
FROM artykuly
ORDER BY temat_wektor <-> '[1,0,0,0]'
LIMIT 4;
