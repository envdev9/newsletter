-- 05-skosnosc-i-cena.sql
-- (a) max_skewness raportowane przez XE dla kazdej z tabel z 04 (po jednej kompilacji procedury),
-- (b) cena "nieobjetego" predykatu: dbo.Ev z 01-02 - PSP chroni TenantId, ale nie Region.
SET NOCOUNT ON;
USE PspMulti;
GO
ALTER EVENT SESSION psp_multi ON SERVER STATE = STOP;
ALTER EVENT SESSION psp_multi ON SERVER STATE = START;
GO
EXEC sys.sp_recompile 'dbo.Szukaj_EvC'; EXEC dbo.Szukaj_EvC 1, 1;
EXEC sys.sp_recompile 'dbo.Szukaj_EvD'; EXEC dbo.Szukaj_EvD 1, 1;
EXEC sys.sp_recompile 'dbo.Szukaj_EvE'; EXEC dbo.Szukaj_EvE 1, 1;
EXEC sys.sp_recompile 'dbo.Szukaj_EvF'; EXEC dbo.Szukaj_EvF 1, 1;
GO
WAITFOR DELAY '00:00:02';
PRINT '=== (a) kolejnosc zdarzen = kolejnosc kompilacji: EvC, EvD, EvE, EvF ===';
SELECT ROW_NUMBER() OVER (ORDER BY x.ev.value('@timestamp', 'datetime2')) AS lp,
       x.ev.value('@name', 'varchar(100)') AS zdarzenie,
       x.ev.value('(data[@name="max_skewness"]/value)[1]', 'varchar(30)') AS max_skewness,
       x.ev.value('(data[@name="reason"]/text)[1]', 'varchar(60)') AS powod
FROM (SELECT CAST(st.target_data AS xml) AS d
      FROM sys.dm_xe_sessions s JOIN sys.dm_xe_session_targets st ON st.event_session_address = s.address
      WHERE s.name = 'psp_multi' AND st.target_name = 'ring_buffer') q
CROSS APPLY q.d.nodes('RingBufferTarget/event') x(ev);
GO
PRINT '=== (b) dbo.Ev: gigant-tenant + MALY region (predykat Region nie jest objety PSP) ===';
SET STATISTICS IO ON;
PRINT '--- przez procedure z PSP (wariant "duzy" na TenantId):';
EXEC dbo.Szukaj @TenantId = 1, @Region = 2, @Kind = 5;
PRINT '--- to samo z OPTION (RECOMPILE) - plan liczony pod te wartosci:';
EXEC sys.sp_executesql
    N'SELECT COUNT(*) AS n, MAX(Payload) AS maks FROM dbo.Ev WHERE TenantId = @TenantId AND Region = @Region AND Kind = @Kind OPTION (RECOMPILE)',
    N'@TenantId int, @Region int, @Kind int', 1, 2, 5;
SET STATISTICS IO OFF;
GO
