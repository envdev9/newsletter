-- 17-tombstone-watch.sql
-- Po samym REORGANIZE zostaja rowgroupy TOMBSTONE. Kiedy znikaja "same"? Odpytujemy co 15 s przez 5 minut (20 prob).
-- Wymaga stanu: po 10-setup, 12-delete, 13-reorganize (BEZ 14-rebuild).
SET NOCOUNT ON;
USE NcciClean;
GO
DECLARE @i int = 0, @t int, @all int, @msg nvarchar(200);
WHILE @i <= 20
BEGIN
    SELECT @t = SUM(CASE WHEN state_desc = 'TOMBSTONE' THEN 1 ELSE 0 END), @all = COUNT(*)
    FROM sys.dm_db_column_store_row_group_physical_stats WHERE object_id = OBJECT_ID('dbo.Orders');
    SET @msg = CONCAT('t+', @i * 15, 's: rowgroupow=', @all, ', TOMBSTONE=', @t);
    RAISERROR(@msg, 0, 1) WITH NOWAIT;
    IF @i = 20 BREAK;
    WAITFOR DELAY '00:00:15';
    SET @i += 1;
END
GO
SELECT row_group_id AS rg, state_desc AS stan, total_rows, deleted_rows
FROM sys.dm_db_column_store_row_group_physical_stats WHERE object_id = OBJECT_ID('dbo.Orders') ORDER BY row_group_id;
GO
