-- 07-psp-dziala.sql
-- Ta sama procedura na dwoch tabelach: Ev_k1 (skosnosc 190000 -> PSP rusza) i Ev_k2 (95000 -> PSP pominiete).
-- Mierzymy logical reads dla malego tenanta (TenantId=2) PO tym, jak pierwszy plan skompilowal duzy tenant (TenantId=1).
SET NOCOUNT ON;
USE PspLab;
GO
ALTER DATABASE PspLab SET QUERY_STORE = ON (OPERATION_MODE = READ_WRITE, QUERY_CAPTURE_MODE = ALL);
ALTER DATABASE PspLab SET QUERY_STORE CLEAR;
GO
CREATE OR ALTER PROCEDURE dbo.GetK1 @TenantId int AS
    SELECT COUNT(*) AS Ile, MAX(Payload) AS P FROM dbo.Ev_k1 WHERE TenantId = @TenantId;
GO
CREATE OR ALTER PROCEDURE dbo.GetK2 @TenantId int AS
    SELECT COUNT(*) AS Ile, MAX(Payload) AS P FROM dbo.Ev_k2 WHERE TenantId = @TenantId;
GO
DBCC FREEPROCCACHE;
GO
PRINT '=== Ev_k2 (skosnosc 95000, PSP pominiete): duzy tenant kompiluje plan, maly go dostaje ===';
SET STATISTICS IO ON;
EXEC dbo.GetK2 @TenantId = 1;
EXEC dbo.GetK2 @TenantId = 2;
SET STATISTICS IO OFF;
GO
PRINT '=== Ev_k1 (skosnosc 190000, PSP rusza): ta sama kolejnosc wywolan ===';
SET STATISTICS IO ON;
EXEC dbo.GetK1 @TenantId = 1;
EXEC dbo.GetK1 @TenantId = 2;
SET STATISTICS IO OFF;
GO
PRINT '=== plan cache: dispatcher i warianty ===';
SELECT CASE WHEN t.text LIKE N'%PLAN PER VALUE%' THEN 'wariant'
            WHEN CONVERT(nvarchar(max), qp.query_plan) LIKE N'%<Dispatcher>%' THEN 'dispatcher' ELSE 'zwykly' END AS rodzaj,
       CASE WHEN t.text LIKE N'%Ev_k1%' THEN 'Ev_k1' ELSE 'Ev_k2' END AS tabela,
       qs.execution_count AS wykonan,
       SUBSTRING(t.text, CHARINDEX('option (PLAN', t.text), 70) AS hint_psp
FROM sys.dm_exec_query_stats qs
CROSS APPLY sys.dm_exec_query_plan(qs.plan_handle) qp
CROSS APPLY sys.dm_exec_sql_text(qs.sql_handle) t
WHERE (t.text LIKE N'%FROM dbo.Ev_k1 WHERE%' OR t.text LIKE N'%FROM dbo.Ev_k2 WHERE%') AND t.text NOT LIKE N'%dm_exec%'
ORDER BY tabela, rodzaj;
GO
