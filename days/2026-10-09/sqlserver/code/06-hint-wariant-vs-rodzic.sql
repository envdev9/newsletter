-- 06-hint-wariant-vs-rodzic.sql
-- Pierwszenstwo hintu Query Store: wariant PSP (dziecko) vs rodzic (dyspozytor), z uzyciem USE HINT.
-- Hinty celowo SPRZECZNE: FORCE_LEGACY_CARDINALITY_ESTIMATION vs FORCE_DEFAULT_CARDINALITY_ESTIMATION.
-- Wynik czytamy z PLANU W PLAN CACHE: atrybut CardinalityEstimationModelVersion ("70" = legacy CE, "160" = CE dla compat 160)
-- oraz QueryStoreStatementHintText / ...HintSource, ktore silnik dopisuje do planu, gdy hint zostal zastosowany.
-- (sys.query_store_plan nie dostaje nowego planu po dodaniu hintu - pierwsza proba odczytu stamtad pokazywala zawsze 160.)
-- Wymaga 01 (dbo.Ev, Query Store ON). Procedura osobna (dbo.SzukajH), zeby miec swieze query_id.
-- DBCC FREEPROCCACHE czysci cache calej INSTANCJI - uruchamiaj tylko na instancji testowej.
SET NOCOUNT ON;
USE PspMulti;
GO
CREATE OR ALTER PROCEDURE dbo.SzukajH @TenantId int
AS
    SELECT COUNT(*) AS n, MAX(Payload) AS maks FROM dbo.Ev WHERE TenantId = @TenantId;
GO
-- Pomocnicza: warianty PSP procedury SzukajH widoczne w plan cache + wersja CE i hint z planu.
CREATE OR ALTER PROCEDURE dbo.PokazWarianty
AS
BEGIN
    SET NOCOUNT ON;
    SELECT SUBSTRING(t.text, CHARINDEX('QueryVariantID = ', t.text), 18) AS wariant,
           CASE WHEN CHARINDEX('CardinalityEstimationModelVersion="70"', pl.x) > 0 THEN '70 (legacy)'
                WHEN CHARINDEX('CardinalityEstimationModelVersion="160"', pl.x) > 0 THEN '160' END AS ce,
           CASE WHEN CHARINDEX('QueryStoreStatementHintText="', pl.x) > 0 THEN
                SUBSTRING(pl.x, CHARINDEX('QueryStoreStatementHintText="', pl.x) + 29,
                          CHARINDEX('"', pl.x, CHARINDEX('QueryStoreStatementHintText="', pl.x) + 29)
                            - CHARINDEX('QueryStoreStatementHintText="', pl.x) - 29) END AS hint_z_planu,
           CASE WHEN CHARINDEX('QueryStoreStatementHintSource="User"', pl.x) > 0 THEN 'User' END AS zrodlo
    FROM sys.dm_exec_cached_plans cp
    CROSS APPLY sys.dm_exec_sql_text(cp.plan_handle) t
    CROSS APPLY (SELECT CAST(p.query_plan AS nvarchar(max)) AS x FROM sys.dm_exec_query_plan(cp.plan_handle) p) pl
    WHERE cp.objtype = 'Prepared' AND t.text LIKE N'%QueryVariantID%' AND CHARINDEX(N'@TenantId', t.text) > 0
      AND CHARINDEX(N'@Region', t.text) = 0
    ORDER BY wariant;
END
GO
-- Pomocnicza: wywolania procedury (duzy tenant pierwszy => kompilacja) po wyczyszczeniu cache.
CREATE OR ALTER PROCEDURE dbo.Wolaj
AS
BEGIN
    SET NOCOUNT ON;
    DBCC FREEPROCCACHE WITH NO_INFOMSGS;
    EXEC dbo.SzukajH @TenantId = 1;
    EXEC dbo.SzukajH @TenantId = 2;
END
GO
EXEC dbo.SzukajH @TenantId = 1;
EXEC dbo.SzukajH @TenantId = 2;
EXEC sys.sp_query_store_flush_db;
GO
DECLARE @parent int, @high int, @low int;
SELECT @parent = MAX(v.parent_query_id) FROM sys.query_store_query_variant v
  JOIN sys.query_store_query pq ON pq.query_id = v.parent_query_id
  WHERE pq.object_id = OBJECT_ID('dbo.SzukajH');
SELECT @high = v.query_variant_query_id FROM sys.query_store_query_variant v
  JOIN sys.query_store_query q ON q.query_id = v.query_variant_query_id JOIN sys.query_store_query_text qt ON qt.query_text_id = q.query_text_id
  WHERE v.parent_query_id = @parent AND qt.query_sql_text LIKE N'%QueryVariantID = 3,%';
SELECT @low = v.query_variant_query_id FROM sys.query_store_query_variant v
  JOIN sys.query_store_query q ON q.query_id = v.query_variant_query_id JOIN sys.query_store_query_text qt ON qt.query_text_id = q.query_text_id
  WHERE v.parent_query_id = @parent AND qt.query_sql_text LIKE N'%QueryVariantID = 1,%';
SELECT @parent AS rodzic, @high AS wariant_duzy_3, @low AS wariant_maly_1;

PRINT '=== S0: bez hintow ===';
EXEC dbo.Wolaj;
EXEC dbo.PokazWarianty;

PRINT '=== S1: LEGACY CE tylko na RODZICU ===';
EXEC sys.sp_query_store_set_hints @query_id = @parent, @query_hints = N'OPTION(USE HINT(''FORCE_LEGACY_CARDINALITY_ESTIMATION''))';
EXEC dbo.Wolaj;
EXEC dbo.PokazWarianty;

PRINT '=== S2: rodzic LEGACY CE + wariant DUZY (3) z DEFAULT CE (sprzeczne) ===';
EXEC sys.sp_query_store_set_hints @query_id = @high, @query_hints = N'OPTION(USE HINT(''FORCE_DEFAULT_CARDINALITY_ESTIMATION''))';
EXEC dbo.Wolaj;
EXEC dbo.PokazWarianty;
EXEC sys.sp_query_store_clear_hints @query_id = @high;
EXEC sys.sp_query_store_clear_hints @query_id = @parent;

PRINT '=== S3: odwrotnie - rodzic DEFAULT CE + wariant DUZY (3) z LEGACY CE ===';
EXEC sys.sp_query_store_set_hints @query_id = @parent, @query_hints = N'OPTION(USE HINT(''FORCE_DEFAULT_CARDINALITY_ESTIMATION''))';
EXEC sys.sp_query_store_set_hints @query_id = @high,   @query_hints = N'OPTION(USE HINT(''FORCE_LEGACY_CARDINALITY_ESTIMATION''))';
EXEC dbo.Wolaj;
EXEC dbo.PokazWarianty;
EXEC sys.sp_query_store_clear_hints @query_id = @high;
EXEC sys.sp_query_store_clear_hints @query_id = @parent;

PRINT '=== S4: tylko wariant DUZY (3) z LEGACY CE, rodzic bez hintu ===';
EXEC sys.sp_query_store_set_hints @query_id = @high, @query_hints = N'OPTION(USE HINT(''FORCE_LEGACY_CARDINALITY_ESTIMATION''))';
EXEC dbo.Wolaj;
EXEC dbo.PokazWarianty;
EXEC sys.sp_query_store_clear_hints @query_id = @high;
SELECT COUNT(*) AS pozostale_hinty FROM sys.query_store_query_hints;
GO
