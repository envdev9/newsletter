-- HNSW ("Hierarchical Navigable Small World") - drugi, nowszy typ indeksu
-- przybliżonego wyszukiwania w pgvector (od wersji 0.5.0).
--
-- Jak to działa (w skrócie): zamiast dzielić dane na klastry, HNSW buduje
-- graf, w którym każdy wektor ma połączenia do kilku "sąsiadów" - z
-- dodatkowymi warstwami "autostrad" łączącymi odległe rejony grafu, żeby
-- dało się szybko przeskoczyć w dobry rejon zamiast iść krok po kroku.
-- Wyszukiwanie to nawigacja po tym grafie: start w losowym punkcie górnej
-- warstwy, schodzenie w stronę zapytania, aż trafi się w okolicę
-- prawdziwych najbliższych sąsiadów.
--
-- Różnica względem IVFFlat, która ma znaczenie w praktyce:
--   - HNSW NIE wymaga wcześniej wypełnionej tabeli do "treningu" - graf
--     rośnie przyrostowo z każdym INSERT-em, więc dobrze się nadaje do
--     danych, które napływają na bieżąco.
--   - HNSW ma zwykle LEPSZY recall (trafność) przy podobnej szybkości
--     zapytań niż IVFFlat, kosztem: wolniejszej budowy indeksu i
--     WIĘKSZEGO zużycia pamięci/dysku (graf z wieloma połączeniami waży
--     więcej niż lista klastrów).
--   - IVFFlat bywa szybszy do zbudowania na starcie, gdy dane są
--     statyczne i budujesz indeks raz na koniec importu.
--
-- Reguła kciuka: jeśli nie masz powodu, żeby wybrać inaczej - **HNSW jest
-- domyślnym wyborem** w większości nowych projektów z pgvector (lepszy
-- recall, prostsza eksploatacja). IVFFlat ma sens, gdy zależy ci na
-- szybszym budowaniu bardzo dużego, w większości statycznego indeksu i
-- akceptujesz nieco gorszy recall.
--
-- m = maks. liczba połączeń na węzeł grafu (domyślnie 16, wyżej = lepszy
-- recall, więcej pamięci). ef_construction = jak szeroko przeszukiwać przy
-- budowie grafu (domyślnie 64, wyżej = wolniejsza budowa, lepsza jakość).
-- Wartości domyślne wystarczają na start.
CREATE INDEX artykuly_hnsw_idx
    ON artykuly
    USING hnsw (temat_wektor vector_l2_ops)
    WITH (m = 16, ef_construction = 64);
