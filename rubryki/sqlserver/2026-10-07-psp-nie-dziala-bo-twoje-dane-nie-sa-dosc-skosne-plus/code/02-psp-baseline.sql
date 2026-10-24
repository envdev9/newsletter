-- 02-psp-baseline.sql
-- Scenariusz "jak w #8": Query Store WLACZONY, procedura bez hintow, SELECT z kolumnami spoza indeksu.
SET NOCOUNT ON;
USE PspLab;
GO
ALTER DATABASE PspLab SET QUERY_STORE = ON (OPERATION_MODE = READ_WRITE, QUERY_CAPTURE_MODE = ALL);
ALTER DATABASE PspLab SET QUERY_STORE CLEAR;
GO
CREATE OR ALTER PROCEDURE dbo.GetEventsByTenant @TenantId int AS
    SELECT EventId, TenantId, Payload FROM dbo.Events WHERE TenantId = @TenantId;
GO
DBCC FREEPROCCACHE;
GO
CREATE TABLE #r (EventId int, TenantId int, Payload char(200));
SET STATISTICS IO ON;
INSERT #r EXEC dbo.GetEventsByTenant @TenantId = 1;   -- INSERT..EXEC: nie zalewamy konsoli wynikami
TRUNCATE TABLE #r;
INSERT #r EXEC dbo.GetEventsByTenant @TenantId = 2;
SET STATISTICS IO OFF;
GO
-- Czy w cache jest plan z Dispatcherem (PSP)?
SELECT CASE WHEN CONVERT(nvarchar(max), qp.query_plan) LIKE N'%Dispatcher%' THEN 'TAK - Dispatcher' ELSE 'NIE - zwykly plan' END AS psp_w_planie,
       qs.execution_count
FROM sys.dm_exec_query_stats qs
CROSS APPLY sys.dm_exec_query_plan(qs.plan_handle) qp
CROSS APPLY sys.dm_exec_sql_text(qs.sql_handle) t
WHERE t.text LIKE N'%FROM dbo.Events WHERE TenantId%' AND t.text NOT LIKE N'%dm_exec%';
GO
