-- 03-create-index.sql
-- Tworzymy nieklastrowany indeks (nonclustered index) na CustomerId.
--
-- Co to jest indeks, w skrócie: to osobna, posortowana struktura danych
-- (B-drzewo - "B-tree") trzymana obok tabeli. Węzły liścia B-drzewa
-- zawierają wartości CustomerId w kolejności rosnącej + wskaźnik
-- ("row locator") do konkretnego wiersza w tabeli głównej (przy tabeli
-- z indeksem klastrowanym - jak nasza Orders - tym wskaźnikiem jest klucz
-- klastrowany, czyli OrderId). Szukanie w B-drzewie to logarytmiczna liczba
-- porównań (przy 500 000 wierszy to raptem kilkanaście "skoków" w głąb
-- drzewa), zamiast przeglądania wszystkich wierszy po kolei.
CREATE NONCLUSTERED INDEX IX_Orders_CustomerId
    ON dbo.Orders (CustomerId);
GO

-- Sprawdzenie, że indeks powstał i ile miejsca zajmuje.
SELECT
    i.name                          AS IndexName,
    i.type_desc                     AS IndexType,
    ps.page_count                   AS Strony8KB,
    ps.page_count * 8 / 1024.0      AS RozmiarMB
FROM sys.indexes AS i
JOIN sys.dm_db_index_physical_stats(DB_ID(), OBJECT_ID('dbo.Orders'), NULL, NULL, 'DETAILED') AS ps
    ON ps.object_id = i.object_id AND ps.index_id = i.index_id
WHERE i.name = 'IX_Orders_CustomerId';
GO
