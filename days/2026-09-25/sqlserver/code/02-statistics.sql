-- 02-statistics.sql
-- Statystyki: skąd optymalizator wie, ile wierszy zwróci zapytanie ZANIM je wykona.
USE PrasowkaStats;
GO

-- Statystyka założona automatycznie razem z indeksem IX_Orders_CustomerId.
-- Kolumny: Rows (ile wierszy), Steps (ile kroków histogramu), Density (średnia selektywność).
DBCC SHOW_STATISTICS ('dbo.Orders', 'IX_Orders_CustomerId') WITH STAT_HEADER;
GO

-- Histogram: do 200 kroków. RANGE_HI_KEY = górna granica kroku,
-- EQ_ROWS = ile wierszy ma DOKŁADNIE tę wartość,
-- RANGE_ROWS / AVG_RANGE_ROWS = wiersze w przedziale POMIĘDZY krokami.
-- Pokazujemy: krok dla klienta 1 (hurtownik) i kilka pierwszych kroków.
DBCC SHOW_STATISTICS ('dbo.Orders', 'IX_Orders_CustomerId') WITH HISTOGRAM;
GO

-- Kiedy statystyki były ostatnio aktualizowane i ile zmian od tego czasu.
SELECT s.name AS Statystyka, sp.last_updated, sp.rows, sp.rows_sampled,
       sp.steps, sp.modification_counter
FROM sys.stats s
CROSS APPLY sys.dm_db_stats_properties(s.object_id, s.stats_id) sp
WHERE s.object_id = OBJECT_ID('dbo.Orders');
GO

-- Efekt w planie: szacunek (EstimateRows) vs rzeczywistość (Rows) dla dwóch klientów.
-- Sprawdź kolumny Rows i EstimateRows w wyniku PROFILE.
SET STATISTICS PROFILE ON;
GO
SELECT COUNT(*) AS Cnt FROM dbo.Orders WHERE CustomerId = 1;
GO
SELECT COUNT(*) AS Cnt FROM dbo.Orders WHERE CustomerId = 4242;
GO
SET STATISTICS PROFILE OFF;
GO
