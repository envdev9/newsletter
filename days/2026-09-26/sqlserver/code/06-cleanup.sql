-- 06-cleanup.sql - opcjonalne usuniecie bazy PrasowkaQS (razem z Query Store).
USE master;
GO
IF DB_ID('PrasowkaQS') IS NOT NULL
BEGIN
    ALTER DATABASE PrasowkaQS SET SINGLE_USER WITH ROLLBACK IMMEDIATE;
    DROP DATABASE PrasowkaQS;
END
GO
