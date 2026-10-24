-- Pomocnicza PROCEDURE (nie FUNCTION/DO) uzyta do zmierzenia realnej blokady zapisow
-- podczas rebuildu indeksu HNSW. PROCEDURE umie robic COMMIT w trakcie swojego
-- wykonania (DO $$ ... $$ i zwykle funkcje nie moga) - dzieki temu kazdy INSERT ladowany
-- w petli jest WLASNA, autocommitujaca transakcja (symuluje wielu niezaleznych klientow
-- zapisujacych jeden po drugim), a nie jedna wielka transakcja ktora sama zablokowalaby
-- `CREATE INDEX CONCURRENTLY` (ktory czeka na zakonczenie wszystkich transakcji widzacych
-- tabele w momencie startu).
CREATE OR REPLACE PROCEDURE writer_probe(id_offset int, n int, delay_s float)
LANGUAGE plpgsql AS $$
DECLARE
    i int;
    vec vector(64);
BEGIN
    SELECT ('[' || string_agg('0.01', ',') || ']')::vector(64)
      INTO vec
      FROM generate_series(1, 64);

    FOR i IN 1..n LOOP
        INSERT INTO items ("Id", "Category", "Embedding")
        VALUES (id_offset + i, 'writer-probe', vec);

        RAISE NOTICE 'insert id=% committed_at=%', id_offset + i, clock_timestamp();
        COMMIT;
        PERFORM pg_sleep(delay_s);
    END LOOP;
END $$;

-- Uzycie (w tle, podczas gdy w innej sesji leci `dotnet ef database update`):
--   docker exec <container> psql -U postgres -d demo -c "CALL writer_probe(900000, 60, 0.3);"
-- Kazdy NOTICE to jeden realnie zacommitowany INSERT z serwerowym znacznikiem czasu -
-- odstepy miedzy kolejnymi liniami > 0.3s (poza szumem) = zapis byl zablokowany.
