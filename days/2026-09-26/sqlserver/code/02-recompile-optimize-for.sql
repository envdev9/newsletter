-- 02-recompile-optimize-for.sql
-- Cztery warianty tej samej procedury i to, jak każdy zachowuje się wobec sniffingu.
-- Dla każdego: czyścimy cache, wołamy najpierw klienta RZADKIEGO (4242), potem
-- HURTOWNIKA (1) i odwrotnie. STATISTICS IO pokazuje logical reads.
-- Uruchamiaj z sqlcmd -I.
USE PrasowkaQS;
GO

CREATE OR ALTER PROCEDURE dbo.usp_Plain @CustomerId INT AS
BEGIN
    SET NOCOUNT ON;
    SELECT COUNT(*) AS Orders, SUM(Amount) AS TotalAmount, MAX(OrderDate) AS LastOrder
    FROM dbo.Orders WHERE CustomerId = @CustomerId;
END
GO

CREATE OR ALTER PROCEDURE dbo.usp_Recompile @CustomerId INT AS
BEGIN
    SET NOCOUNT ON;
    SELECT COUNT(*) AS Orders, SUM(Amount) AS TotalAmount, MAX(OrderDate) AS LastOrder
    FROM dbo.Orders WHERE CustomerId = @CustomerId
    OPTION (RECOMPILE);
END
GO

CREATE OR ALTER PROCEDURE dbo.usp_OptForUnknown @CustomerId INT AS
BEGIN
    SET NOCOUNT ON;
    SELECT COUNT(*) AS Orders, SUM(Amount) AS TotalAmount, MAX(OrderDate) AS LastOrder
    FROM dbo.Orders WHERE CustomerId = @CustomerId
    OPTION (OPTIMIZE FOR UNKNOWN);
END
GO

CREATE OR ALTER PROCEDURE dbo.usp_OptForWhale @CustomerId INT AS
BEGIN
    SET NOCOUNT ON;
    SELECT COUNT(*) AS Orders, SUM(Amount) AS TotalAmount, MAX(OrderDate) AS LastOrder
    FROM dbo.Orders WHERE CustomerId = @CustomerId
    OPTION (OPTIMIZE FOR (@CustomerId = 1));
END
GO

-- Kontrola: bez leczenia, rzadki pierwszy
ALTER DATABASE SCOPED CONFIGURATION CLEAR PROCEDURE_CACHE;
GO
SET STATISTICS IO ON;
GO
PRINT '=== usp_Plain: rzadki (4242) pierwszy, potem hurtownik (1)';
EXEC dbo.usp_Plain @CustomerId = 4242;
GO
EXEC dbo.usp_Plain @CustomerId = 1;
GO
SET STATISTICS IO OFF;
GO

-- OPTION (RECOMPILE)
ALTER DATABASE SCOPED CONFIGURATION CLEAR PROCEDURE_CACHE;
GO
SET STATISTICS IO ON;
GO
PRINT '=== usp_Recompile: rzadki (4242), potem hurtownik (1)';
EXEC dbo.usp_Recompile @CustomerId = 4242;
GO
EXEC dbo.usp_Recompile @CustomerId = 1;
GO
SET STATISTICS IO OFF;
GO

-- OPTIMIZE FOR UNKNOWN: plan pod "przecietnego" klienta (gestosc), ignoruje wartosc
ALTER DATABASE SCOPED CONFIGURATION CLEAR PROCEDURE_CACHE;
GO
SET STATISTICS IO ON;
GO
PRINT '=== usp_OptForUnknown: rzadki (4242), potem hurtownik (1)';
EXEC dbo.usp_OptForUnknown @CustomerId = 4242;
GO
EXEC dbo.usp_OptForUnknown @CustomerId = 1;
GO
SET STATISTICS IO OFF;
GO

-- OPTIMIZE FOR (@CustomerId = 1): plan zawsze pod hurtownika
ALTER DATABASE SCOPED CONFIGURATION CLEAR PROCEDURE_CACHE;
GO
SET STATISTICS IO ON;
GO
PRINT '=== usp_OptForWhale: rzadki (4242), potem hurtownik (1)';
EXEC dbo.usp_OptForWhale @CustomerId = 4242;
GO
EXEC dbo.usp_OptForWhale @CustomerId = 1;
GO
SET STATISTICS IO OFF;
GO

-- Szacunek wierszy (EstimateRows) dla OPTIMIZE FOR UNKNOWN - dlaczego wybral taki plan.
SET STATISTICS PROFILE ON;
GO
EXEC dbo.usp_OptForUnknown @CustomerId = 4242;
GO
SET STATISTICS PROFILE OFF;
GO

-- Koszt kompilacji RECOMPILE: 2000 wywolan rzadkiego klienta, czas ogolny.
-- (wyniki zbieramy do #sink, zeby nie zalewac konsoli 4000 resultsetami)
SET NOCOUNT ON;
CREATE TABLE #sink (Orders INT, TotalAmount DECIMAL(18,2), LastOrder DATE);
DECLARE @t0 DATETIME2 = SYSDATETIME(), @i INT = 0;
WHILE @i < 2000 BEGIN INSERT #sink EXEC dbo.usp_Plain @CustomerId = 4242; SET @i += 1; END
PRINT 'usp_Plain      x2000: ' + CAST(DATEDIFF(MILLISECOND, @t0, SYSDATETIME()) AS VARCHAR(10)) + ' ms';
SET @t0 = SYSDATETIME(); SET @i = 0;
WHILE @i < 2000 BEGIN INSERT #sink EXEC dbo.usp_Recompile @CustomerId = 4242; SET @i += 1; END
PRINT 'usp_Recompile  x2000: ' + CAST(DATEDIFF(MILLISECOND, @t0, SYSDATETIME()) AS VARCHAR(10)) + ' ms';
GO
