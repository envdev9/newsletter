-- 03-warianty.sql
-- Warianty PSP w Query Store (po 02): ktory predykat wszedl do predicate_range i jakie sa granice (100.0 / 100000.0).
SET NOCOUNT ON;
USE PspMulti;
GO
EXEC sys.sp_query_store_flush_db;
GO
SELECT v.parent_query_id, v.query_variant_query_id AS wariant_query_id,
       SUBSTRING(qt.query_sql_text, CHARINDEX('option (PLAN PER', qt.query_sql_text), 600) AS wariant
FROM sys.query_store_query_variant v
JOIN sys.query_store_query q ON q.query_id = v.query_variant_query_id
JOIN sys.query_store_query_text qt ON qt.query_text_id = q.query_text_id
ORDER BY v.query_variant_query_id;
GO
