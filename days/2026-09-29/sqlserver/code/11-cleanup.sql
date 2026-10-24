-- 11-cleanup.sql - usuniecie obu baz demo (opcjonalne - i tak kasujemy caly kontener po demie).
SET NOCOUNT ON;
IF DB_ID('PrasowkaNCCI') IS NOT NULL
BEGIN
    ALTER DATABASE PrasowkaNCCI SET SINGLE_USER WITH ROLLBACK IMMEDIATE;
    DROP DATABASE PrasowkaNCCI;
END
GO
IF DB_ID('PrasowkaSerial') IS NOT NULL
BEGIN
    ALTER DATABASE PrasowkaSerial SET SINGLE_USER WITH ROLLBACK IMMEDIATE;
    DROP DATABASE PrasowkaSerial;
END
GO
SELECT name FROM sys.databases WHERE name IN ('PrasowkaNCCI', 'PrasowkaSerial');  -- powinno zwrocic 0 wierszy
GO
