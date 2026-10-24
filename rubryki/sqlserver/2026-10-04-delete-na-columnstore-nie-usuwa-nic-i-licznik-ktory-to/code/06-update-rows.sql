-- 06-update-rows.sql - UPDATE na tabeli z NCCI: pokazujemy ze to w praktyce DELETE (stary wiersz) + INSERT (nowy wiersz).
USE PrasowkaNcciDml;
GO
PRINT '--- PRZED UPDATE: stan rowgroupow ---';
SELECT row_group_id, state_description, total_rows, deleted_rows, size_in_bytes
FROM sys.column_store_row_groups
WHERE object_id = OBJECT_ID('dbo.Orders')
ORDER BY row_group_id;
GO
SET STATISTICS IO ON;
SET STATISTICS TIME ON;
GO
-- UPDATE obejmujacy okolo 2000/40000 klientow z pozostalych statusow (0,1,2) - realny batch "oplacono zamowienia".
DECLARE @zaktualizowano int;
UPDATE dbo.Orders
    SET Status = 1
WHERE Status = 0
  AND CustomerId BETWEEN 1 AND 2000;
SET @zaktualizowano = @@ROWCOUNT;
SELECT @zaktualizowano AS WierszyZaktualizowanych;
GO
SET STATISTICS IO OFF;
SET STATISTICS TIME OFF;
GO
PRINT '--- PO UPDATE: stan rowgroupow (oczekujemy: deleted_rows wzrasta w starych compressed rowgroupach, NOWY rowgroup OPEN = delta store z wstawionymi "nowymi" wierszami) ---';
SELECT row_group_id, state_description, total_rows, deleted_rows, size_in_bytes
FROM sys.column_store_row_groups
WHERE object_id = OBJECT_ID('dbo.Orders')
ORDER BY row_group_id;
GO
