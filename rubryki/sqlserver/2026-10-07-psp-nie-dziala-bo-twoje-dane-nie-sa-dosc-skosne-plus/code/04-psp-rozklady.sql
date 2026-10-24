-- 04-psp-rozklady.sql
-- Ta sama procedura, rozne ROZKLADY danych. Pytanie: przy jakim ksztalcie histogramu PSP w ogole ruszy?
-- Wymaga sesji XE psp_diag z 03-psp-diagnoza.sql.
SET NOCOUNT ON;
USE PspLab;
GO
-- Dane: n(i) -> TenantId wg 3 rozkladow w tabelach Ev_A / Ev_B / Ev_C (po ~200 000 wierszy)
DROP TABLE IF EXISTS dbo.Ev_A, dbo.Ev_B, dbo.Ev_C;
CREATE TABLE dbo.Ev_A (EventId int IDENTITY PRIMARY KEY, TenantId int NOT NULL, Payload char(200) NOT NULL DEFAULT 'x');
CREATE TABLE dbo.Ev_B (EventId int IDENTITY PRIMARY KEY, TenantId int NOT NULL, Payload char(200) NOT NULL DEFAULT 'x');
CREATE TABLE dbo.Ev_C (EventId int IDENTITY PRIMARY KEY, TenantId int NOT NULL, Payload char(200) NOT NULL DEFAULT 'x');
GO
;WITH n AS (SELECT TOP (200000) ROW_NUMBER() OVER (ORDER BY (SELECT NULL)) AS i FROM sys.all_objects a CROSS JOIN sys.all_objects b)
-- A: 1 gigant (95%) + 100 malych po 100  (to samo co dbo.Events)
INSERT dbo.Ev_A (TenantId) SELECT CASE WHEN i <= 190000 THEN 1 ELSE 2 + (i % 100) END FROM n;
;WITH n AS (SELECT TOP (200000) ROW_NUMBER() OVER (ORDER BY (SELECT NULL)) AS i FROM sys.all_objects a CROSS JOIN sys.all_objects b)
-- B: 3 "poziomy": 1 duzy (100 000), 10 srednich (po 5 000), ~50 000 malych (po 1 = unikalne)
INSERT dbo.Ev_B (TenantId) SELECT CASE WHEN i <= 100000 THEN 1 WHEN i <= 150000 THEN 2 + (i % 10) ELSE 100 + i END FROM n;
;WITH n AS (SELECT TOP (200000) ROW_NUMBER() OVER (ORDER BY (SELECT NULL)) AS i FROM sys.all_objects a CROSS JOIN sys.all_objects b)
-- C: 1 gigant (95%) + 10 000 malych po ~1 wiersz (unikalne klucze)
INSERT dbo.Ev_C (TenantId) SELECT CASE WHEN i <= 190000 THEN 1 ELSE 1000 + i END FROM n;
GO
CREATE INDEX IX_A ON dbo.Ev_A (TenantId);
CREATE INDEX IX_B ON dbo.Ev_B (TenantId);
CREATE INDEX IX_C ON dbo.Ev_C (TenantId);
GO
ALTER EVENT SESSION psp_diag ON SERVER STATE = STOP;
ALTER EVENT SESSION psp_diag ON SERVER STATE = START;
GO
DBCC FREEPROCCACHE;
GO
EXEC sp_executesql N'SELECT COUNT(*), MAX(Payload) /*A*/ FROM dbo.Ev_A WHERE TenantId = @t', N'@t int', @t = 1;
EXEC sp_executesql N'SELECT COUNT(*), MAX(Payload) /*B*/ FROM dbo.Ev_B WHERE TenantId = @t', N'@t int', @t = 1;
EXEC sp_executesql N'SELECT COUNT(*), MAX(Payload) /*C*/ FROM dbo.Ev_C WHERE TenantId = @t', N'@t int', @t = 1;
GO
SELECT x.ev.value('@name', 'varchar(100)') AS zdarzenie,
       x.ev.value('(data[@name="reason"]/text)[1]', 'varchar(60)') AS powod,
       x.ev.value('(data[@name="interesting_predicate_count"]/value)[1]', 'int') AS interesujace,
       x.ev.value('(data[@name="max_skewness"]/value)[1]', 'varchar(40)') AS max_skewness,
       x.ev.value('(data[@name="psp_optimization_supported"]/value)[1]', 'varchar(10)') AS supported,
       SUBSTRING(x.ev.value('(action[@name="sql_text"]/value)[1]', 'nvarchar(300)'), 1, 70) AS sql_text
FROM (SELECT CAST(st.target_data AS xml) AS d
      FROM sys.dm_xe_sessions s JOIN sys.dm_xe_session_targets st ON st.event_session_address = s.address
      WHERE s.name = 'psp_diag' AND st.target_name = 'ring_buffer') q
CROSS APPLY q.d.nodes('RingBufferTarget/event') x(ev);
GO
