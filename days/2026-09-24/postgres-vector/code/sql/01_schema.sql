-- Włączenie rozszerzenia pgvector w bieżącej bazie.
-- Trzeba to zrobić raz na bazę (nie na klaster) - każda baza, która ma
-- używać typu `vector`, potrzebuje własnego CREATE EXTENSION.
CREATE EXTENSION IF NOT EXISTS vector;

-- Tabela z kolumną wektorową. vector(4) oznacza: "wektor liczb
-- zmiennoprzecinkowych o STAŁEJ długości 4". Długość jest częścią typu -
-- próba wstawienia wektora o innej liczbie wymiarów zakończy się błędem
-- (patrz demo w 06_bledy.sql). W prawdziwym RAG-u ta liczba to wymiar
-- embeddingu z modelu (np. 384, 768, 1536) - tu używamy 4, żeby dało się
-- ręcznie policzyć każdą odległość na kartce i sprawdzić, że wynik ma sens.
--
-- UWAGA: to NIE są embeddingi z modelu językowego. Każdy wymiar to ręcznie
-- przypisana "siła powiązania" tekstu z jednym z czterech tematów:
--   [zwierzęta, technologia, sport, kuchnia]
-- Liczba bliska 1.0 = tekst mocno o tym temacie, bliska 0.0 = w ogóle.
-- To uproszczenie celowe (patrz ARTICLE.md) - ale sama mechanika: typ
-- kolumny, indeks, ORDER BY <-> LIMIT k, jest identyczna jak z prawdziwymi
-- embeddingami z sentence-transformers/OpenAI/etc.
DROP TABLE IF EXISTS artykuly;
CREATE TABLE artykuly (
    id          serial PRIMARY KEY,
    tytul       text NOT NULL,
    temat_wektor vector(4) NOT NULL
);

COMMENT ON COLUMN artykuly.temat_wektor IS
    'Ręczny wektor demonstracyjny [zwierzęta, technologia, sport, kuchnia], NIE embedding z modelu';
