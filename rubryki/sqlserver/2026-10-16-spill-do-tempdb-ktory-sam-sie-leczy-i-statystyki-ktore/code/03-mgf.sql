-- 03-mgf.sql
-- Wymaga bazy StatLab z 01-lab.sql (dowolny tryb). Nieaktualne statystyki "robimy" sami:
-- AUTO_UPDATE_STATISTICS OFF, potem dosypujemy 600 000 wierszy z nowa wartoscia Status.
-- Pokazujemy, co robi memory grant feedback (tryb wierszowy) z zaniżonym grantem i spillem:
--   proba A: ROW_MODE_MEMORY_GRANT_FEEDBACK = OFF  (procedura dbo.Med9,  Status = 9)
--   proba B: ROW_MODE_MEMORY_GRANT_FEEDBACK = ON   (procedura dbo.Med10, Status = 10)
-- Dwie osobne procedury/wartosci, zeby feedback zapisany w Query Store z jednej proby nie zmieszal sie z druga.
SET NOCOUNT ON;
USE StatLab;
GO
ALTER DATABASE StatLab SET AUTO_UPDATE_STATISTICS OFF;
GO
;WITH n AS (SELECT TOP (600000) ROW_NUMBER() OVER (ORDER BY (SELECT NULL)) AS i FROM sys.all_objects a CROSS JOIN sys.all_objects b CROSS JOIN sys.all_objects c)
INSERT dbo.Orders (Status, Note) SELECT 9, CONCAT('dziewiec-', (i * 104729) % 600011) FROM n;
;WITH n AS (SELECT TOP (600000) ROW_NUMBER() OVER (ORDER BY (SELECT NULL)) AS i FROM sys.all_objects a CROSS JOIN sys.all_objects b CROSS JOIN sys.all_objects c)
INSERT dbo.Orders (Status, Note) SELECT 10, CONCAT('dziesiec-', (i * 104729) % 600011) FROM n;
GO
-- zapytania sa wciaz nieznane optymalizatorowi: obie wartosci powstaly po ostatnim UPDATE STATISTICS
CREATE OR ALTER PROCEDURE dbo.Med9 AS
SELECT Note FROM (SELECT Note, ROW_NUMBER() OVER (ORDER BY Note) AS rn FROM dbo.Orders WHERE Status = 9) q WHERE rn = 300000;
GO
CREATE OR ALTER PROCEDURE dbo.Med10 AS
SELECT Note FROM (SELECT Note, ROW_NUMBER() OVER (ORDER BY Note) AS rn FROM dbo.Orders WHERE Status = 10) q WHERE rn = 300000;
GO
SELECT name, value FROM sys.database_scoped_configurations WHERE name LIKE '%MEMORY_GRANT_FEEDBACK%';
SELECT compatibility_level FROM sys.databases WHERE name = 'StatLab';
GO
CREATE TABLE #r (Note varchar(60));
CREATE TABLE #log (proba char(1), wywolanie int, spille_stron bigint, grant_kb bigint, uzyty_grant_kb bigint, czas_ms bigint);
GO
-- proba A: feedback OFF
ALTER DATABASE SCOPED CONFIGURATION SET ROW_MODE_MEMORY_GRANT_FEEDBACK = OFF;
DBCC FREEPROCCACHE WITH NO_INFOMSGS;
GO
DECLARE @i int = 1;
WHILE @i <= 5
BEGIN
    INSERT #r EXEC dbo.Med9;
    INSERT #log
    SELECT 'A', @i, qs.last_spills, qs.last_grant_kb, qs.last_used_grant_kb, qs.last_elapsed_time / 1000
    FROM sys.dm_exec_query_stats qs CROSS APPLY sys.dm_exec_sql_text(qs.sql_handle) t
    WHERE t.objectid = OBJECT_ID('dbo.Med9');
    SET @i += 1;
END
GO
-- proba B: feedback ON
ALTER DATABASE SCOPED CONFIGURATION SET ROW_MODE_MEMORY_GRANT_FEEDBACK = ON;
DBCC FREEPROCCACHE WITH NO_INFOMSGS;
GO
DECLARE @i int = 1;
WHILE @i <= 5
BEGIN
    INSERT #r EXEC dbo.Med10;
    INSERT #log
    SELECT 'B', @i, qs.last_spills, qs.last_grant_kb, qs.last_used_grant_kb, qs.last_elapsed_time / 1000
    FROM sys.dm_exec_query_stats qs CROSS APPLY sys.dm_exec_sql_text(qs.sql_handle) t
    WHERE t.objectid = OBJECT_ID('dbo.Med10');
    SET @i += 1;
END
GO
SELECT * FROM #log ORDER BY proba, wywolanie;
GO
