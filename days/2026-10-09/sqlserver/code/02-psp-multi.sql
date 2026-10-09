-- 02-psp-multi.sql
-- PSP z WIELOMA predykatami: procedura filtruje po TenantId (skosna), Region (skosna) i Kind (rownomierna).
-- Pytania: (a) co PSP uznaje za "interesujace", (b) ile i jakie predykaty trafiaja do wariantow (predicate_range).
SET NOCOUNT ON;
USE PspMulti;
GO
IF EXISTS (SELECT 1 FROM sys.server_event_sessions WHERE name = 'psp_multi') DROP EVENT SESSION psp_multi ON SERVER;
GO
CREATE EVENT SESSION psp_multi ON SERVER
    ADD EVENT sqlserver.parameter_sensitive_plan_optimization_skipped_reason,
    ADD EVENT sqlserver.query_with_parameter_sensitivity
    ADD TARGET package0.ring_buffer WITH (MAX_DISPATCH_LATENCY = 1 SECONDS);
GO
ALTER EVENT SESSION psp_multi ON SERVER STATE = START;
GO
CREATE OR ALTER PROCEDURE dbo.Szukaj @TenantId int, @Region int, @Kind int
AS
    SELECT COUNT(*) AS n, MAX(Payload) AS maks FROM dbo.Ev WHERE TenantId = @TenantId AND Region = @Region AND Kind = @Kind;
GO
-- UWAGA: wywolania NIE moga byc owiniete w INSERT..EXEC (fałszywy negatyw, patrz #14)
SET STATISTICS IO ON;
PRINT '--- (1,1,5): gigant + dominujacy region';
EXEC dbo.Szukaj @TenantId = 1, @Region = 1, @Kind = 5;
PRINT '--- (2,2,5): maly tenant + maly region';
EXEC dbo.Szukaj @TenantId = 2, @Region = 2, @Kind = 5;
PRINT '--- (2,1,5): maly tenant + dominujacy region';
EXEC dbo.Szukaj @TenantId = 2, @Region = 1, @Kind = 5;
PRINT '--- (1,2,5): gigant + maly region';
EXEC dbo.Szukaj @TenantId = 1, @Region = 2, @Kind = 5;
SET STATISTICS IO OFF;
GO
WAITFOR DELAY '00:00:02';
PRINT '=== XE: co zobaczyl PSP ===';
SELECT x.ev.value('@name', 'varchar(100)') AS zdarzenie,
       x.ev.value('(data[@name="max_skewness"]/value)[1]', 'varchar(30)') AS max_skewness,
       x.ev.value('(data[@name="reason"]/text)[1]', 'varchar(60)') AS powod
FROM (SELECT CAST(st.target_data AS xml) AS d
      FROM sys.dm_xe_sessions s JOIN sys.dm_xe_session_targets st ON st.event_session_address = s.address
      WHERE s.name = 'psp_multi' AND st.target_name = 'ring_buffer') q
CROSS APPLY q.d.nodes('RingBufferTarget/event') x(ev);
GO
PRINT '=== plan cache: warianty i ich predicate_range ===';
SELECT cp.usecounts,
       SUBSTRING(t.text, CHARINDEX('option (PLAN PER VALUE', t.text), 400) AS naglowek_wariantu
FROM sys.dm_exec_cached_plans cp
CROSS APPLY sys.dm_exec_sql_text(cp.plan_handle) t
WHERE cp.objtype = 'Prepared' AND t.text LIKE N'%PLAN PER VALUE%' AND CHARINDEX(N'@Kind', t.text) > 0
ORDER BY t.text;
GO
