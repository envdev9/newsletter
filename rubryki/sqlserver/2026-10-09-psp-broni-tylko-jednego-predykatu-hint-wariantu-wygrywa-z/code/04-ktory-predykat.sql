-- 04-ktory-predykat.sql
-- Skoro dwie kolumny sa skosne (w 01: TenantId 190000:1, Region 179999:1), a PSP wzial tylko TenantId -
-- czym kieruje sie wyborem? Trzy hipotezy: (H1) pierwszy w WHERE, (H2) najbardziej skosny, (H3) pierwszy w kolejnosci kolumn/indeksow.
-- Budujemy 4 tabele o tych samych 200 000 wierszach, rozni sie rozkladem i kolejnoscia predykatow w WHERE.
--   EvC: TenantId skosnosc 150000:1,  Region 199999:1  (Region bardziej skosny), WHERE TenantId, Region
--   EvD: TenantId 190000:1, Region 190000:1 (remis),                      WHERE TenantId, Region
--   EvE: jak EvC (Region bardziej skosny),                                 WHERE Region, TenantId   (odwrocona kolejnosc)
--   EvF: jak 01 (TenantId bardziej skosny: 190000 vs 179999),              WHERE Region, TenantId   (odwrocona kolejnosc)
SET NOCOUNT ON;
USE PspMulti;
GO
CREATE OR ALTER PROCEDURE dbo.Zbuduj @Tabela sysname, @TenantExpr nvarchar(400), @RegionExpr nvarchar(400), @Where nvarchar(400)
AS
BEGIN
    DECLARE @sql nvarchar(max) = N'
    IF OBJECT_ID(''dbo.' + @Tabela + N''') IS NOT NULL DROP TABLE dbo.' + @Tabela + N';
    CREATE TABLE dbo.' + @Tabela + N' (EventId int IDENTITY(1,1) PRIMARY KEY, TenantId int NOT NULL, Region int NOT NULL, Payload char(200) NOT NULL DEFAULT ''x'');
    ;WITH n AS (SELECT TOP (200000) ROW_NUMBER() OVER (ORDER BY (SELECT NULL)) AS i FROM sys.all_objects a CROSS JOIN sys.all_objects b)
    INSERT dbo.' + @Tabela + N' (TenantId, Region) SELECT ' + @TenantExpr + N', ' + @RegionExpr + N' FROM n;
    CREATE INDEX IX_' + @Tabela + N'_T ON dbo.' + @Tabela + N' (TenantId);
    CREATE INDEX IX_' + @Tabela + N'_R ON dbo.' + @Tabela + N' (Region);';
    EXEC (@sql);
    SET @sql = N'CREATE OR ALTER PROCEDURE dbo.Szukaj_' + @Tabela + N' @TenantId int, @Region int AS
        SELECT COUNT(*) AS n, MAX(Payload) AS maks FROM dbo.' + @Tabela + N' WHERE ' + @Where + N';';
    EXEC (@sql);
END
GO
-- rozklady: gigant 1 + jeden wiersz "2" + reszta rozproszona
DECLARE @t_150k nvarchar(400) = N'CASE WHEN i <= 150000 THEN 1 WHEN i = 150001 THEN 2 ELSE 3 + (i % 5000) END';
DECLARE @t_190k nvarchar(400) = N'CASE WHEN i <= 190000 THEN 1 WHEN i = 190001 THEN 2 ELSE 3 + (i % 50) END';
DECLARE @r_199k nvarchar(400) = N'CASE WHEN i = 5 THEN 2 ELSE 1 END';
DECLARE @r_190k nvarchar(400) = N'CASE WHEN i >= 10001 THEN 1 WHEN i = 10000 THEN 2 ELSE 3 + (i % 50) END';
DECLARE @r_180k nvarchar(400) = N'CASE WHEN i = 5 THEN 2 WHEN i % 10 = 0 THEN 3 + (i % 7) ELSE 1 END';
EXEC dbo.Zbuduj 'EvC', @t_150k, @r_199k, N'TenantId = @TenantId AND Region = @Region';
EXEC dbo.Zbuduj 'EvD', @t_190k, @r_190k, N'TenantId = @TenantId AND Region = @Region';
EXEC dbo.Zbuduj 'EvE', @t_150k, @r_199k, N'Region = @Region AND TenantId = @TenantId';
EXEC dbo.Zbuduj 'EvF', @t_190k, @r_180k, N'Region = @Region AND TenantId = @TenantId';
GO
SELECT 'EvC' AS tabela, 'TenantId' AS kol, TenantId AS wartosc, COUNT(*) AS wierszy FROM dbo.EvC WHERE TenantId IN (1,2) GROUP BY TenantId
UNION ALL SELECT 'EvC', 'Region', Region, COUNT(*) FROM dbo.EvC WHERE Region IN (1,2) GROUP BY Region
UNION ALL SELECT 'EvD', 'TenantId', TenantId, COUNT(*) FROM dbo.EvD WHERE TenantId IN (1,2) GROUP BY TenantId
UNION ALL SELECT 'EvD', 'Region', Region, COUNT(*) FROM dbo.EvD WHERE Region IN (1,2) GROUP BY Region
UNION ALL SELECT 'EvF', 'TenantId', TenantId, COUNT(*) FROM dbo.EvF WHERE TenantId IN (1,2) GROUP BY TenantId
UNION ALL SELECT 'EvF', 'Region', Region, COUNT(*) FROM dbo.EvF WHERE Region IN (1,2) GROUP BY Region
ORDER BY 1, 2, 3;
GO
-- Wywolania: najpierw gigant/gigant (kompilacja), potem male wartosci
EXEC dbo.Szukaj_EvC 1, 1; EXEC dbo.Szukaj_EvC 2, 1; EXEC dbo.Szukaj_EvC 1, 2;
EXEC dbo.Szukaj_EvD 1, 1; EXEC dbo.Szukaj_EvD 2, 1; EXEC dbo.Szukaj_EvD 1, 2;
EXEC dbo.Szukaj_EvE 1, 1; EXEC dbo.Szukaj_EvE 2, 1; EXEC dbo.Szukaj_EvE 1, 2;
EXEC dbo.Szukaj_EvF 1, 1; EXEC dbo.Szukaj_EvF 2, 1; EXEC dbo.Szukaj_EvF 1, 2;
GO
EXEC sys.sp_query_store_flush_db;
GO
PRINT '=== ktore predykaty weszly do wariantow (Query Store) ===';
SELECT DISTINCT
       CASE WHEN CHARINDEX(N'[EvC]', qt.query_sql_text) > 0 THEN 'EvC (T 150000:1, R 199999:1; WHERE T,R)'
            WHEN CHARINDEX(N'[EvD]', qt.query_sql_text) > 0 THEN 'EvD (T 190000:1, R 190000:1; WHERE T,R)'
            WHEN CHARINDEX(N'[EvE]', qt.query_sql_text) > 0 THEN 'EvE (T 150000:1, R 199999:1; WHERE R,T)'
            WHEN CHARINDEX(N'[EvF]', qt.query_sql_text) > 0 THEN 'EvF (T 190000:1, R 179999:1; WHERE R,T)'
            ELSE 'Ev z 01/02 (T 190000:1, R 179999:1; WHERE T,R,Kind)' END AS tabela,
       SUBSTRING(qt.query_sql_text, CHARINDEX('predicate_range', qt.query_sql_text), 120) AS predicate_range
FROM sys.query_store_query_variant v
JOIN sys.query_store_query q ON q.query_id = v.query_variant_query_id
JOIN sys.query_store_query_text qt ON qt.query_text_id = q.query_text_id
WHERE qt.query_sql_text LIKE N'%PLAN PER VALUE%'
ORDER BY 1;
GO
