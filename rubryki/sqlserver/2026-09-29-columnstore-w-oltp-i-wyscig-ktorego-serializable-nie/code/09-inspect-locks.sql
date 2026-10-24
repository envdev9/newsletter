-- 09-inspect-locks.sql - podglad blokad zakresowych (key-range) w trakcie wyscigu SERIALIZABLE.
USE PrasowkaSerial;
GO
WAITFOR DELAY '00:00:02';
SELECT
    tl.request_session_id AS Spid,
    tl.resource_type       AS Typ,
    tl.resource_description AS Zasob,
    tl.request_mode         AS Tryb,
    tl.request_status       AS Status
FROM sys.dm_tran_locks tl
WHERE tl.resource_database_id = DB_ID('PrasowkaSerial')
  AND tl.request_mode LIKE '%Range%'
ORDER BY tl.request_session_id;
GO
