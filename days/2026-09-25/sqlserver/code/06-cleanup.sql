-- 06-cleanup.sql - usuwa bazę demo.
USE master;
GO
IF DB_ID('PrasowkaStats') IS NOT NULL
BEGIN
    ALTER DATABASE PrasowkaStats SET SINGLE_USER WITH ROLLBACK IMMEDIATE;
    DROP DATABASE PrasowkaStats;
END
GO
