-- 04-parameter-sniffing.sql
-- Parameter sniffing + plan cache: procedura kompilowana RAZ dla pierwszej
-- wartości parametru, plan trafia do cache i jest reużywany dla KOLEJNYCH.
-- (Uruchamiaj sqlcmd z flagą -I - QUOTED_IDENTIFIER ON - bo zapytanie o XML
-- planu w cache tego wymaga.)
--
-- Procedura zwraca PODSUMOWANIE klienta (1 wiersz), a nie listę zamówień -
-- dzięki temu output konsoli jest mały, a plan nadal musi sięgnąć po kolumny
-- Amount i OrderDate, których nie ma w wąskim indeksie (=> Key Lookup).
USE PrasowkaStats;
GO

CREATE OR ALTER PROCEDURE dbo.usp_CustomerSummary @CustomerId INT
AS
BEGIN
    SET NOCOUNT ON;
    SELECT COUNT(*) AS Orders, SUM(Amount) AS TotalAmount, MAX(OrderDate) AS LastOrder
    FROM dbo.Orders
    WHERE CustomerId = @CustomerId;
END
GO

CREATE OR ALTER PROCEDURE dbo.usp_CustomerSummary_Recompile @CustomerId INT
AS
BEGIN
    SET NOCOUNT ON;
    SELECT COUNT(*) AS Orders, SUM(Amount) AS TotalAmount, MAX(OrderDate) AS LastOrder
    FROM dbo.Orders
    WHERE CustomerId = @CustomerId
    OPTION (RECOMPILE);
END
GO

-- Zaczynamy od pustego cache planów (na demo-kontenerze OK).
ALTER DATABASE SCOPED CONFIGURATION CLEAR PROCEDURE_CACHE;
GO

SET STATISTICS IO ON;
GO

-- ---- Scenariusz A: pierwsze wywołanie z wartością RZADKĄ -------------------
PRINT '--- A1: pierwsze wywolanie, klient 4242 (rzadki) -> kompilacja pod Seek+Lookup';
EXEC dbo.usp_CustomerSummary @CustomerId = 4242;
GO
PRINT '--- A2: drugie wywolanie, klient 1 (hurtownik) -> REUZYCIE planu z cache';
EXEC dbo.usp_CustomerSummary @CustomerId = 1;
GO

SET STATISTICS IO OFF;
GO

-- Co siedzi w plan cache dla tej procedury: 1 plan, 2 wykonania,
-- last_logical_reads to koszt OSTATNIEGO (hurtowniczego) wywołania.
SELECT OBJECT_NAME(ps.object_id) AS Procedura, ps.execution_count,
       ps.last_logical_reads, ps.total_logical_reads
FROM sys.dm_exec_procedure_stats ps
WHERE ps.database_id = DB_ID() AND ps.object_id = OBJECT_ID('dbo.usp_CustomerSummary');
GO

-- Wartość parametru, dla której plan został SKOMPILOWANY (z XML-a planu w cache).
;WITH XMLNAMESPACES (DEFAULT 'http://schemas.microsoft.com/sqlserver/2004/07/showplan')
SELECT qp.query_plan.value('(//ParameterList/ColumnReference/@ParameterCompiledValue)[1]', 'varchar(20)') AS ParameterCompiledValue
FROM sys.dm_exec_procedure_stats ps
CROSS APPLY sys.dm_exec_query_plan(ps.plan_handle) qp
WHERE ps.database_id = DB_ID() AND ps.object_id = OBJECT_ID('dbo.usp_CustomerSummary');
GO

-- ---- Scenariusz B: odwrotnie - cache czyścimy, pierwszy jest hurtownik ----
ALTER DATABASE SCOPED CONFIGURATION CLEAR PROCEDURE_CACHE;
GO
SET STATISTICS IO ON;
GO
PRINT '--- B1: pierwsze wywolanie, klient 1 (hurtownik) -> kompilacja pod skan tabeli';
EXEC dbo.usp_CustomerSummary @CustomerId = 1;
GO
PRINT '--- B2: drugie wywolanie, klient 4242 (rzadki) -> REUZYCIE skanu calej tabeli';
EXEC dbo.usp_CustomerSummary @CustomerId = 4242;
GO
SET STATISTICS IO OFF;
GO

-- ---- Naprawa: OPTION (RECOMPILE) - plan liczony za każdym razem -----------
ALTER DATABASE SCOPED CONFIGURATION CLEAR PROCEDURE_CACHE;
GO
SET STATISTICS IO ON;
GO
PRINT '--- Fix RECOMPILE: hurtownik pierwszy, potem rzadki - kazdy dostaje wlasny plan';
EXEC dbo.usp_CustomerSummary_Recompile @CustomerId = 1;
GO
EXEC dbo.usp_CustomerSummary_Recompile @CustomerId = 4242;
GO
SET STATISTICS IO OFF;
GO
