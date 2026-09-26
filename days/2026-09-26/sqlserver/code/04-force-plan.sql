-- 04-force-plan.sql
-- Wymuszenie planu w Query Store (bez zmiany kodu aplikacji!). Wymaga 03.
-- Wybieramy plan o NAJNIZSZYM sredniem logical reads dla usp_Plain i go wymuszamy.
USE PrasowkaQS;
GO

DECLARE @qid BIGINT, @pid BIGINT;
SELECT TOP (1) @qid = p.query_id, @pid = p.plan_id
FROM sys.query_store_plan p
JOIN sys.query_store_query q ON q.query_id = p.query_id
JOIN sys.query_store_runtime_stats rs ON rs.plan_id = p.plan_id
WHERE q.object_id = OBJECT_ID('dbo.usp_Plain')
GROUP BY p.query_id, p.plan_id
ORDER BY AVG(rs.avg_logical_io_reads) ASC;
PRINT 'Wymuszam query_id=' + CAST(@qid AS VARCHAR(20)) + ', plan_id=' + CAST(@pid AS VARCHAR(20));
EXEC sys.sp_query_store_force_plan @query_id = @qid, @plan_id = @pid;
GO

SELECT p.query_id, p.plan_id, p.is_forced_plan, p.force_failure_count, p.last_force_failure_reason_desc
FROM sys.query_store_plan p
JOIN sys.query_store_query q ON q.query_id = p.query_id
WHERE q.object_id = OBJECT_ID('dbo.usp_Plain');
GO

-- Ten sam pechowy scenariusz co zawsze: po "restarcie" pierwszy wchodzi rzadki klient.
-- Bez wymuszenia: hurtownik dostawalby plan Seek+Lookup (600 350 odczytow).
ALTER DATABASE SCOPED CONFIGURATION CLEAR PROCEDURE_CACHE;
GO
SET STATISTICS IO ON;
GO
PRINT '--- po force: rzadki (4242) pierwszy';
EXEC dbo.usp_Plain @CustomerId = 4242;
GO
PRINT '--- po force: hurtownik (1)';
EXEC dbo.usp_Plain @CustomerId = 1;
GO
SET STATISTICS IO OFF;
GO

-- Zdjecie wymuszenia i porzadki.
DECLARE @qid2 BIGINT, @pid2 BIGINT;
SELECT @qid2 = p.query_id, @pid2 = p.plan_id
FROM sys.query_store_plan p
JOIN sys.query_store_query q ON q.query_id = p.query_id
WHERE q.object_id = OBJECT_ID('dbo.usp_Plain') AND p.is_forced_plan = 1;
EXEC sys.sp_query_store_unforce_plan @query_id = @qid2, @plan_id = @pid2;
GO
SELECT COUNT(*) AS ForcedPlans FROM sys.query_store_plan WHERE is_forced_plan = 1;
GO
