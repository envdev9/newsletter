-- 03-psp-diagnoza.sql
-- Zamiast zgadywac: Extended Event "parameter_sensitive_plan_optimization_skipped_reason" mowi, DLACZEGO PSP zostal pominiety.
SET NOCOUNT ON;
USE master;
GO
SELECT map_key, map_value FROM sys.dm_xe_map_values WHERE name = 'psp_skipped_reason_enum' ORDER BY map_key;
GO
IF EXISTS (SELECT 1 FROM sys.server_event_sessions WHERE name = 'psp_diag') DROP EVENT SESSION psp_diag ON SERVER;
GO
CREATE EVENT SESSION psp_diag ON SERVER
    ADD EVENT sqlserver.parameter_sensitive_plan_optimization_skipped_reason
        (ACTION (sqlserver.sql_text)),
    ADD EVENT sqlserver.query_with_parameter_sensitivity
        (ACTION (sqlserver.sql_text))
    ADD TARGET package0.ring_buffer
    WITH (MAX_DISPATCH_LATENCY = 1 SECONDS);
ALTER EVENT SESSION psp_diag ON SERVER STATE = START;
GO
USE PspLab;
GO
CREATE TABLE #r (EventId int, TenantId int, Payload char(200));
GO
DBCC FREEPROCCACHE;
INSERT #r EXEC dbo.GetEventsByTenant @TenantId = 1;
INSERT #r EXEC dbo.GetEventsByTenant @TenantId = 2;
GO
-- ring_buffer: co zarejestrowal silnik
SELECT x.ev.value('@name', 'varchar(100)') AS zdarzenie,
       x.ev.value('(data[@name="reason"]/text)[1]', 'varchar(200)') AS powod_pominiecia,
       x.ev.value('(data[@name="interesting_predicate_count"]/value)[1]', 'int') AS interesujace_predykaty,
       x.ev.value('(data[@name="max_skewness"]/value)[1]', 'varchar(50)') AS max_skewness,
       x.ev.value('(data[@name="psp_optimization_supported"]/value)[1]', 'varchar(10)') AS psp_supported,
       LEFT(x.ev.value('(action[@name="sql_text"]/value)[1]', 'nvarchar(300)'), 80) AS sql_text
FROM (SELECT CAST(st.target_data AS xml) AS d
      FROM sys.dm_xe_sessions s JOIN sys.dm_xe_session_targets st ON st.event_session_address = s.address
      WHERE s.name = 'psp_diag' AND st.target_name = 'ring_buffer') q
CROSS APPLY q.d.nodes('RingBufferTarget/event') x(ev);
GO
