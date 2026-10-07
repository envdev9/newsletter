-- 05-psp-prog-skosnosci.sql
-- Bisekcja progu: gigant TenantId=1 ma zawsze 190 000 wierszy, "male" tenanty (200 sztuk) maja po k wierszy
-- (k = 1, 2, 3, 5, 10, 100). Dla kazdego k: jaki sygnal daje XE (kandydat PSP czy SkewnessThresholdNotMet)?
SET NOCOUNT ON;
USE PspLab;
GO
CREATE OR ALTER PROCEDURE dbo.BuildSkewTable @k int AS
BEGIN
    DECLARE @t sysname = CONCAT('dbo.Ev_k', @k);
    DECLARE @sql nvarchar(max) = CONCAT(N'DROP TABLE IF EXISTS ', @t, N';
        CREATE TABLE ', @t, N' (EventId int IDENTITY PRIMARY KEY, TenantId int NOT NULL, Payload char(200) NOT NULL DEFAULT ''x'');
        INSERT ', @t, N' (TenantId) SELECT TOP (190000) 1 FROM sys.all_objects a CROSS JOIN sys.all_objects b;
        ;WITH n AS (SELECT TOP (200) ROW_NUMBER() OVER (ORDER BY (SELECT NULL)) AS t FROM sys.all_objects),
              m AS (SELECT TOP (', @k, N') ROW_NUMBER() OVER (ORDER BY (SELECT NULL)) AS j FROM sys.all_objects a CROSS JOIN sys.all_objects b)
        INSERT ', @t, N' (TenantId) SELECT n.t + 1 FROM n CROSS JOIN m;
        CREATE INDEX IX_Tenant ON ', @t, N' (TenantId);');
    EXEC (@sql);
END
GO
EXEC dbo.BuildSkewTable 1;
EXEC dbo.BuildSkewTable 2;
EXEC dbo.BuildSkewTable 3;
EXEC dbo.BuildSkewTable 5;
EXEC dbo.BuildSkewTable 10;
EXEC dbo.BuildSkewTable 100;
GO
ALTER EVENT SESSION psp_diag ON SERVER STATE = STOP;
ALTER EVENT SESSION psp_diag ON SERVER STATE = START;
DBCC FREEPROCCACHE;
GO
-- wynik zapytania trafia do tabeli tymczasowej, zeby nie zalewac konsoli
CREATE TABLE #o (c int, p char(200));
GO
INSERT #o EXEC sp_executesql N'SELECT COUNT(*), MAX(Payload) /*k1*/ FROM dbo.Ev_k1 WHERE TenantId = @t', N'@t int', @t = 1;
GO
INSERT #o EXEC sp_executesql N'SELECT COUNT(*), MAX(Payload) /*k2*/ FROM dbo.Ev_k2 WHERE TenantId = @t', N'@t int', @t = 1;
GO
INSERT #o EXEC sp_executesql N'SELECT COUNT(*), MAX(Payload) /*k3*/ FROM dbo.Ev_k3 WHERE TenantId = @t', N'@t int', @t = 1;
GO
INSERT #o EXEC sp_executesql N'SELECT COUNT(*), MAX(Payload) /*k5*/ FROM dbo.Ev_k5 WHERE TenantId = @t', N'@t int', @t = 1;
GO
INSERT #o EXEC sp_executesql N'SELECT COUNT(*), MAX(Payload) /*k10*/ FROM dbo.Ev_k10 WHERE TenantId = @t', N'@t int', @t = 1;
GO
INSERT #o EXEC sp_executesql N'SELECT COUNT(*), MAX(Payload) /*k100*/ FROM dbo.Ev_k100 WHERE TenantId = @t', N'@t int', @t = 1;
GO
SELECT tabela, zdarzenie, powod, max_skewness
FROM (
  SELECT SUBSTRING(sql_text, CHARINDEX('/*k', sql_text), CHARINDEX('*/', sql_text) - CHARINDEX('/*k', sql_text) + 2) AS tabela,
         CAST(SUBSTRING(sql_text, CHARINDEX('/*k', sql_text) + 3, CHARINDEX('*/', sql_text) - CHARINDEX('/*k', sql_text) - 3) AS int) AS k,
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
  WHERE sql_text LIKE N'%/*k%') y
ORDER BY k, zdarzenie;
GO
