-- 06-psp-prog-ratio.sql
-- Czy prog zalezy od ILORAZU max/min, czy od tego, ze najrzadsza wartosc ma dokladnie 1 wiersz?
-- Pary (g, k): g = wiersze giganta (TenantId=1), k = wiersze kazdego z 200 malych tenantow.
SET NOCOUNT ON;
USE PspLab;
GO
CREATE OR ALTER PROCEDURE dbo.BuildSkewTable2 @g int, @k int AS
BEGIN
    DECLARE @t sysname = CONCAT('dbo.Ev_g', @g, '_k', @k);
    DECLARE @sql nvarchar(max) = CONCAT(N'DROP TABLE IF EXISTS ', @t, N';
        CREATE TABLE ', @t, N' (EventId int IDENTITY PRIMARY KEY, TenantId int NOT NULL, Payload char(200) NOT NULL DEFAULT ''x'');
        INSERT ', @t, N' (TenantId) SELECT TOP (', @g, N') 1 FROM sys.all_objects a CROSS JOIN sys.all_objects b;
        ;WITH n AS (SELECT TOP (200) ROW_NUMBER() OVER (ORDER BY (SELECT NULL)) AS t FROM sys.all_objects),
              m AS (SELECT TOP (', @k, N') ROW_NUMBER() OVER (ORDER BY (SELECT NULL)) AS j FROM sys.all_objects a CROSS JOIN sys.all_objects b)
        INSERT ', @t, N' (TenantId) SELECT n.t + 1 FROM n CROSS JOIN m;
        CREATE INDEX IX_Tenant ON ', @t, N' (TenantId);');
    EXEC (@sql);
END
GO
EXEC dbo.BuildSkewTable2 50000, 1;
EXEC dbo.BuildSkewTable2 10000, 1;
EXEC dbo.BuildSkewTable2 1000, 1;
EXEC dbo.BuildSkewTable2 100000, 2;
GO
ALTER EVENT SESSION psp_diag ON SERVER STATE = STOP;
ALTER EVENT SESSION psp_diag ON SERVER STATE = START;
DBCC FREEPROCCACHE;
GO
CREATE TABLE #o (c int, p char(200));
GO
INSERT #o EXEC sp_executesql N'SELECT COUNT(*), MAX(Payload) /*g50000_k1*/ FROM dbo.Ev_g50000_k1 WHERE TenantId = @t', N'@t int', @t = 1;
GO
INSERT #o EXEC sp_executesql N'SELECT COUNT(*), MAX(Payload) /*g10000_k1*/ FROM dbo.Ev_g10000_k1 WHERE TenantId = @t', N'@t int', @t = 1;
GO
INSERT #o EXEC sp_executesql N'SELECT COUNT(*), MAX(Payload) /*g1000_k1*/ FROM dbo.Ev_g1000_k1 WHERE TenantId = @t', N'@t int', @t = 1;
GO
INSERT #o EXEC sp_executesql N'SELECT COUNT(*), MAX(Payload) /*g100000_k2*/ FROM dbo.Ev_g100000_k2 WHERE TenantId = @t', N'@t int', @t = 1;
GO
SELECT SUBSTRING(sql_text, CHARINDEX('/*g', sql_text), CHARINDEX('*/', sql_text) - CHARINDEX('/*g', sql_text) + 2) AS tabela,
       zdarzenie, powod, max_skewness
FROM (
    SELECT x.ev.value('@name', 'varchar(100)') AS zdarzenie,
           x.ev.value('(data[@name="reason"]/text)[1]', 'varchar(60)') AS powod,
           x.ev.value('(data[@name="max_skewness"]/value)[1]', 'varchar(40)') AS max_skewness,
           x.ev.value('(action[@name="sql_text"]/value)[1]', 'nvarchar(400)') AS sql_text
    FROM (SELECT CAST(st.target_data AS xml) AS d
          FROM sys.dm_xe_sessions s JOIN sys.dm_xe_session_targets st ON st.event_session_address = s.address
          WHERE s.name = 'psp_diag' AND st.target_name = 'ring_buffer') q
    CROSS APPLY q.d.nodes('RingBufferTarget/event') x(ev)) z
WHERE sql_text LIKE N'%/*g%' AND (powod IS NULL OR powod <> 'UnsupportedStatementType')
ORDER BY tabela;
GO
