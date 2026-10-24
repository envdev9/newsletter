-- 06-cleanup.sql
-- Opcjonalne sprzątanie po całej demonstracji - usuwa bazę testową.
-- Uruchom na końcu, jeśli nie chcesz zostawiać PrasowkaDemo w instancji.

USE master;
GO

IF DB_ID('PrasowkaDemo') IS NOT NULL
BEGIN
    ALTER DATABASE PrasowkaDemo SET SINGLE_USER WITH ROLLBACK IMMEDIATE;
    DROP DATABASE PrasowkaDemo;
END
GO
