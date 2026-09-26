-- 03-query-store.sql
-- Query Store: czarna skrzynka zapytań. Włączamy, generujemy dwa różne plany dla
-- TEGO SAMEGO zapytania (usp_Plain), porównujemy je w sys.query_store_* i
-- WYMUSZAMY dobry plan. Uruchamiaj z sqlcmd -I. Wymaga 02 (procedury).
USE PrasowkaQS;
GO

ALTER DATABASE PrasowkaQS SET QUERY_STORE = ON
    (OPERATION_MODE = READ_WRITE, QUERY_CAPTURE_MODE = ALL,
     INTERVAL_LENGTH_MINUTES = 1, DATA_FLUSH_INTERVAL_SECONDS = 60);
GO
ALTER DATABASE PrasowkaQS SET QUERY_STORE CLEAR;
GO

SELECT actual_state_desc, query_capture_mode_desc, interval_length_minutes
FROM sys.database_query_store_options;
GO

-- Plan #1: skompilowany pod klienta rzadkiego (Seek + Key Lookup), uzyty na hurtowniku.
ALTER DATABASE SCOPED CONFIGURATION CLEAR PROCEDURE_CACHE;
GO
EXEC dbo.usp_Plain @CustomerId = 4242;
GO
EXEC dbo.usp_Plain @CustomerId = 1;
GO
EXEC dbo.usp_Plain @CustomerId = 1;
GO

-- Plan #2: po "restarcie" pierwszy wchodzi hurtownik (Scan).
ALTER DATABASE SCOPED CONFIGURATION CLEAR PROCEDURE_CACHE;
GO
EXEC dbo.usp_Plain @CustomerId = 1;
GO
EXEC dbo.usp_Plain @CustomerId = 1;
GO
EXEC dbo.usp_Plain @CustomerId = 1;
GO

EXEC sys.sp_query_store_flush_db;
GO

-- Jedno zapytanie (query_id), dwa plany (plan_id) i ich koszty.
SELECT q.query_id, p.plan_id, p.is_forced_plan,
       SUM(rs.count_executions)                         AS Wykonan,
       CAST(AVG(rs.avg_logical_io_reads) AS BIGINT)     AS AvgLogicalReads,
       CAST(AVG(rs.avg_duration) / 1000.0 AS DECIMAL(10,1)) AS AvgDurationMs,
       CASE WHEN CAST(p.query_plan AS NVARCHAR(MAX)) LIKE '%Index Seek%'
              OR CAST(p.query_plan AS NVARCHAR(MAX)) LIKE '%Key Lookup%'
              OR CAST(p.query_plan AS NVARCHAR(MAX)) LIKE '%Lookup="1"%'
            THEN 'Seek + Key Lookup' ELSE 'Clustered Index Scan' END AS RodzajPlanu
FROM sys.query_store_query q
JOIN sys.query_store_plan p          ON p.query_id = q.query_id
JOIN sys.query_store_runtime_stats rs ON rs.plan_id = p.plan_id
WHERE q.object_id = OBJECT_ID('dbo.usp_Plain')
GROUP BY q.query_id, p.plan_id, p.is_forced_plan, CAST(p.query_plan AS NVARCHAR(MAX))
ORDER BY p.plan_id;
GO

-- Tekst zapytania, ktore Query Store sledzi.
SELECT q.query_id, qt.query_sql_text
FROM sys.query_store_query q
JOIN sys.query_store_query_text qt ON qt.query_text_id = q.query_text_id
WHERE q.object_id = OBJECT_ID('dbo.usp_Plain');
GO
