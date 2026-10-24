-- 08-compare.sql - te same zapytania na trzech tabelach: rowstore, rowstore+covering, columnstore.
-- Kazde zapytanie jest opakowane w MAX(...), zeby nie wypisywac 50 wierszy wyniku (obciazenie takie samo).
-- Uruchom skrypt DWA razy; licz drugi przebieg (cieply cache).
USE PrasowkaCS;
SET NOCOUNT ON;
DBCC FREEPROCCACHE WITH NO_INFOMSGS;  -- tylko demo: czysty cache planow, zeby DMV na koncu pokazal swieze plany
SET STATISTICS IO ON;
SET STATISTICS TIME ON;
GO
PRINT '===== Q1: agregacja po calej tabeli (GROUP BY StoreId), MAXDOP 1 =====';
PRINT '--- rowstore';
SELECT MAX(revenue) AS max_revenue /*Q1_ROW*/ FROM (SELECT StoreId, COUNT(*) AS n, SUM(Quantity) AS qty, SUM(Amount) AS revenue FROM dbo.FactSales_Row GROUP BY StoreId) x OPTION (MAXDOP 1);
PRINT '--- rowstore, batch mode WYLACZONY hintem (izolujemy efekt batch mode na tej samej tabeli)';
SELECT MAX(revenue) AS max_revenue /*Q1_ROWNOBATCH*/ FROM (SELECT StoreId, COUNT(*) AS n, SUM(Quantity) AS qty, SUM(Amount) AS revenue FROM dbo.FactSales_Row GROUP BY StoreId) x OPTION (MAXDOP 1, USE HINT('DISALLOW_BATCH_MODE'));
PRINT '--- rowstore + covering index';
SELECT MAX(revenue) AS max_revenue /*Q1_IX*/ FROM (SELECT StoreId, COUNT(*) AS n, SUM(Quantity) AS qty, SUM(Amount) AS revenue FROM dbo.FactSales_RowIx GROUP BY StoreId) x OPTION (MAXDOP 1);
PRINT '--- columnstore';
SELECT MAX(revenue) AS max_revenue /*Q1_CCI*/ FROM (SELECT StoreId, COUNT(*) AS n, SUM(Quantity) AS qty, SUM(Amount) AS revenue FROM dbo.FactSales_CCI GROUP BY StoreId) x OPTION (MAXDOP 1);
GO
PRINT '===== Q2: agregacja z filtrem daty (Q1 2025 = 3 z 36 miesiecy), MAXDOP 1 =====';
PRINT '--- rowstore';
SELECT MAX(revenue) AS max_revenue /*Q2_ROW*/ FROM (SELECT StoreId, SUM(Amount) AS revenue FROM dbo.FactSales_Row WHERE SaleDate >= '2025-01-01' AND SaleDate < '2025-04-01' GROUP BY StoreId) x OPTION (MAXDOP 1);
PRINT '--- rowstore + covering index';
SELECT MAX(revenue) AS max_revenue /*Q2_IX*/ FROM (SELECT StoreId, SUM(Amount) AS revenue FROM dbo.FactSales_RowIx WHERE SaleDate >= '2025-01-01' AND SaleDate < '2025-04-01' GROUP BY StoreId) x OPTION (MAXDOP 1);
PRINT '--- columnstore';
SELECT MAX(revenue) AS max_revenue /*Q2_CCI*/ FROM (SELECT StoreId, SUM(Amount) AS revenue FROM dbo.FactSales_CCI WHERE SaleDate >= '2025-01-01' AND SaleDate < '2025-04-01' GROUP BY StoreId) x OPTION (MAXDOP 1);
GO
PRINT '===== Q3: punktowy odczyt jednego wiersza (typowy OLTP) =====';
PRINT '--- rowstore';
SELECT SaleId, Amount /*Q3_ROW*/ FROM dbo.FactSales_Row WHERE SaleId = 2500000;
PRINT '--- columnstore';
SELECT SaleId, Amount /*Q3_CCI*/ FROM dbo.FactSales_CCI WHERE SaleId = 2500000;
GO
SET STATISTICS IO OFF;
SET STATISTICS TIME OFF;
-- Tryb wykonania operatorow w cache'owanych planach (Row = po jednym wierszu, Batch = paczki ~900 wierszy)
WITH q AS
(
    SELECT SUBSTRING(st.text, qs.statement_start_offset / 2 + 1,
                     (CASE WHEN qs.statement_end_offset = -1 THEN DATALENGTH(st.text) ELSE qs.statement_end_offset END - qs.statement_start_offset) / 2 + 1) AS stmt,
           qs.plan_handle, qs.statement_start_offset, qs.statement_end_offset
    FROM sys.dm_exec_query_stats qs
    CROSS APPLY sys.dm_exec_sql_text(qs.sql_handle) st
)
SELECT CASE WHEN stmt LIKE '%Q1[_]ROWNOBATCH%' THEN 'Q1 rowstore, DISALLOW_BATCH'
            WHEN stmt LIKE '%Q1[_]ROW%' THEN 'Q1 rowstore'
            WHEN stmt LIKE '%Q1[_]IX%'  THEN 'Q1 rowstore+ix'
            WHEN stmt LIKE '%Q1[_]CCI%' THEN 'Q1 columnstore' END AS zapytanie,
       CAST(qp.query_plan AS xml).value('declare namespace p="http://schemas.microsoft.com/sqlserver/2004/07/showplan"; (//p:RelOp[contains(@PhysicalOp,"Scan")]/@EstimatedExecutionMode)[1]', 'varchar(10)') AS tryb_skanu,
       CAST(qp.query_plan AS xml).value('declare namespace p="http://schemas.microsoft.com/sqlserver/2004/07/showplan"; (//p:RelOp[@PhysicalOp="Hash Match"]/@EstimatedExecutionMode)[1]', 'varchar(10)') AS tryb_hash_agg,
       CAST(qp.query_plan AS xml).value('declare namespace p="http://schemas.microsoft.com/sqlserver/2004/07/showplan"; (//p:RelOp[@PhysicalOp="Stream Aggregate"]/@EstimatedExecutionMode)[1]', 'varchar(10)') AS tryb_stream_agg
FROM q
CROSS APPLY sys.dm_exec_text_query_plan(q.plan_handle, q.statement_start_offset, q.statement_end_offset) qp
WHERE (stmt LIKE '%Q1[_]ROW%' OR stmt LIKE '%Q1[_]ROWNOBATCH%' OR stmt LIKE '%Q1[_]IX%' OR stmt LIKE '%Q1[_]CCI%')
  AND stmt NOT LIKE '%dm_exec_query_stats%';
GO
