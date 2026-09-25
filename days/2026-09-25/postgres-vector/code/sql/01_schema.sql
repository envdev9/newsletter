-- Schemat dla wydania #2: hybrid search + strojenie indeksów.
CREATE EXTENSION IF NOT EXISTS vector;

-- Mała baza wiedzy (24 ręcznie napisane dokumenty) - do demo hybrid search.
-- Wymiar 384 = wymiar modelu paraphrase-multilingual-MiniLM-L12-v2.
CREATE TABLE kb (
    id   int PRIMARY KEY,
    body text NOT NULL,
    emb  vector(384) NOT NULL,
    -- kolumna generowana: tsvector liczony przez Postgres, nie przez aplikację.
    -- Konfiguracja 'simple' (brak stemmingu) - w obrazie nie ma słownika polskiego.
    tsv  tsvector GENERATED ALWAYS AS (to_tsvector('simple', body)) STORED
);

-- Korpus do pomiarów recall/czasu (bez indeksów - dokładna prawda o sąsiadach).
CREATE TABLE bench (
    id   int PRIMARY KEY,
    body text NOT NULL,
    emb  vector(384) NOT NULL
);

-- Zapytania testowe (osobne od korpusu, ten sam rozkład).
CREATE TABLE bench_q (
    id   int PRIMARY KEY,
    body text NOT NULL,
    emb  vector(384) NOT NULL
);
