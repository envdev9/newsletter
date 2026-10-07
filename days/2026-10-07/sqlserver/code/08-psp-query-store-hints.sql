-- 08-psp-query-store-hints.sql
-- Query Store hint na zapytaniu z PSP: czy trzyma sie RODZICA (dispatcher), czy WARIANTU (dziecka)?
-- Wymaga 07-psp-dziala.sql (dbo.GetK1 na Ev_k1; wariant 1 = maly tenant, wariant 3 = duzy tenant).
-- Uzywamy OPTION(OPTIMIZE FOR UNKNOWN): to hint wspierany w Query Store (zweryfikowane: TABLE HINT oraz
-- OPTIMIZE FOR (@p = ...) zwracaja blad 12455 "not supported") i daje widoczny efekt w logical reads
-- (plan liczony ze sredniej gestosci zamiast z wartosci parametru).
SET NOCOUNT ON;
USE PspLab;
GO
EXEC sys.sp_query_store_flush_db;
GO
PRINT '=== krok 0: drzewo rodzic -> warianty w Query Store ===';
SELECT v.parent_query_id, v.query_variant_query_id AS wariant_query_id, v.dispatcher_plan_id,
       SUBSTRING(qt.query_sql_text, CHARINDEX('QueryVariantID', qt.query_sql_text), 20) AS wariant
FROM sys.query_store_query_variant v
JOIN sys.query_store_query q ON q.query_id = v.query_variant_query_id
JOIN sys.query_store_query_text qt ON qt.query_text_id = q.query_text_id
JOIN sys.query_store_query pq ON pq.query_id = v.parent_query_id
JOIN sys.query_store_query_text pqt ON pqt.query_text_id = pq.query_text_id
WHERE pqt.query_sql_text LIKE N'%Ev_k1%'
ORDER BY v.query_variant_query_id;
GO
DECLARE @parent int, @low int, @high int;
SELECT @parent = MIN(v.parent_query_id) FROM sys.query_store_query_variant v
  JOIN sys.query_store_query pq ON pq.query_id = v.parent_query_id
  JOIN sys.query_store_query_text pqt ON pqt.query_text_id = pq.query_text_id
  WHERE pqt.query_sql_text LIKE N'%Ev_k1%';
SELECT @low  = v.query_variant_query_id FROM sys.query_store_query_variant v
  JOIN sys.query_store_query q ON q.query_id = v.query_variant_query_id JOIN sys.query_store_query_text qt ON qt.query_text_id = q.query_text_id
  WHERE v.parent_query_id = @parent AND qt.query_sql_text LIKE N'%QueryVariantID = 1,%';
SELECT @high = v.query_variant_query_id FROM sys.query_store_query_variant v
  JOIN sys.query_store_query q ON q.query_id = v.query_variant_query_id JOIN sys.query_store_query_text qt ON qt.query_text_id = q.query_text_id
  WHERE v.parent_query_id = @parent AND qt.query_sql_text LIKE N'%QueryVariantID = 3,%';
SELECT @parent AS parent_query_id, @low AS wariant1_maly, @high AS wariant3_duzy;

PRINT '=== krok 1: BEZ hintow (punkt odniesienia) ===';
EXEC sys.sp_recompile 'dbo.GetK1';
SET STATISTICS IO ON;
EXEC dbo.GetK1 @TenantId = 1;
EXEC dbo.GetK1 @TenantId = 2;
SET STATISTICS IO OFF;

PRINT '=== krok 2: OPTIMIZE FOR UNKNOWN TYLKO na wariancie 3 (duzy tenant) ===';
EXEC sys.sp_query_store_set_hints @query_id = @high, @query_hints = N'OPTION(OPTIMIZE FOR UNKNOWN)';
EXEC sys.sp_recompile 'dbo.GetK1';
SET STATISTICS IO ON;
EXEC dbo.GetK1 @TenantId = 1;
EXEC dbo.GetK1 @TenantId = 2;
SET STATISTICS IO OFF;
SELECT query_id, query_hint_text, source_desc FROM sys.query_store_query_hints;
EXEC sys.sp_query_store_clear_hints @query_id = @high;

PRINT '=== krok 3: ten sam hint na RODZICU - czy oba warianty dziedzicza? ===';
EXEC sys.sp_query_store_set_hints @query_id = @parent, @query_hints = N'OPTION(OPTIMIZE FOR UNKNOWN)';
EXEC sys.sp_recompile 'dbo.GetK1';
SET STATISTICS IO ON;
EXEC dbo.GetK1 @TenantId = 1;
EXEC dbo.GetK1 @TenantId = 2;
SET STATISTICS IO OFF;
SELECT query_id, query_hint_text, source_desc FROM sys.query_store_query_hints;
EXEC sys.sp_query_store_clear_hints @query_id = @parent;

PRINT '=== krok 4: OPTION(RECOMPILE) na rodzicu - co sie dzieje z PSP? (sprawdzamy XE psp_diag z 03) ===';
ALTER EVENT SESSION psp_diag ON SERVER STATE = STOP;
ALTER EVENT SESSION psp_diag ON SERVER STATE = START;
EXEC sys.sp_query_store_set_hints @query_id = @parent, @query_hints = N'OPTION(RECOMPILE)';
EXEC sys.sp_recompile 'dbo.GetK1';
SET STATISTICS IO ON;
EXEC dbo.GetK1 @TenantId = 1;
EXEC dbo.GetK1 @TenantId = 2;
SET STATISTICS IO OFF;
EXEC sys.sp_query_store_clear_hints @query_id = @parent;
SELECT powod_pominiecia_psp, COUNT(*) AS ile
FROM (SELECT x.ev.value('(data[@name="reason"]/text)[1]', 'varchar(60)') AS powod_pominiecia_psp
      FROM (SELECT CAST(st.target_data AS xml) AS d
            FROM sys.dm_xe_sessions s JOIN sys.dm_xe_session_targets st ON st.event_session_address = s.address
            WHERE s.name = 'psp_diag' AND st.target_name = 'ring_buffer') q
      CROSS APPLY q.d.nodes('RingBufferTarget/event[@name="parameter_sensitive_plan_optimization_skipped_reason"]') x(ev)) z
GROUP BY powod_pominiecia_psp;
GO
