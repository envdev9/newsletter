-- 13-apply-query-store-hint.sql - sp_query_store_set_hints: wstrzykujemy OPTION(RECOMPILE) do konkretnego
-- zapytania w Query Store, BEZ zmiany ani jednej linii dbo.GetEventsByTenant.
USE PrasowkaQueryHints;
GO
PRINT '--- query_id zapytania wewnatrz procedury (znalezione w Query Store) ---';
SELECT q.query_id, OBJECT_NAME(q.object_id) AS ObjName,
       CAST(qt.query_sql_text AS varchar(200)) AS SqlText
FROM sys.query_store_query q
JOIN sys.query_store_query_text qt ON qt.query_text_id = q.query_text_id
WHERE q.object_id = OBJECT_ID('dbo.GetEventsByTenant');
GO
-- query_id=6 na podstawie powyzszego wyniku (ustalone empirycznie, moze sie zmienic przy innym przebiegu -
-- jesli sie zmieni, podstaw prawidlowe query_id znalezione w zapytaniu powyzej).
EXEC sys.sp_query_store_set_hints @query_id = 6, @query_hints = N'OPTION(RECOMPILE)';
GO
PRINT '--- Hint zapisany w sys.query_store_query_hints ---';
SELECT query_hint_id, query_id, query_hint_text, source_desc, last_query_hint_failure_reason_desc
FROM sys.query_store_query_hints
WHERE query_id = 6;
GO
-- Hint dziala od NASTEPNEJ kompilacji - zeby nie czekac az plan wypadnie z cache sam, wymuszamy recompile.
EXEC sys.sp_recompile 'dbo.GetEventsByTenant';
GO
