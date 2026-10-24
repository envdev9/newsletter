-- 08-stale-pomiar.sql
-- Ten sam pomiar uruchamiany dwa razy: ETAP=nieaktualne (stat z 1 mln wierszy) i ETAP=swieze (po UPDATE STATISTICS).
-- Zapytanie: join z dbo.Customers i agregacja dla Status = 7 (600 000 wierszy, ktorych nie ma w histogramie), sortowanie po sumie.
-- Mierzymy: estymate wierszy w kazdym operatorze planu, przydzial pamieci (grant), spille do tempdb i czas.
-- Uruchamiaj z: sqlcmd -v ETAP=nieaktualne
SET NOCOUNT ON;
USE StaleLab;
GO
DBCC FREEPROCCACHE WITH NO_INFOMSGS;
DBCC DROPCLEANBUFFERS WITH NO_INFOMSGS;
GO
PRINT '=== pomiar: $(ETAP) ===';
SET STATISTICS TIME ON;
SET STATISTICS IO ON;
SELECT /*pomiar*/ TOP (5) c.Name, SUM(o.Amount) AS suma
FROM dbo.Orders o JOIN dbo.Customers c ON c.CustomerId = o.CustomerId
WHERE o.Status = 7
GROUP BY c.Name ORDER BY SUM(o.Amount) DESC, c.Name;
SET STATISTICS IO OFF;
SET STATISTICS TIME OFF;
GO
SELECT qs.last_grant_kb AS grant_kb, qs.last_used_grant_kb AS uzyty_grant_kb,
       qs.last_spills AS spille_stron, qs.last_elapsed_time / 1000 AS czas_ms, qs.last_dop AS dop
FROM sys.dm_exec_query_stats qs CROSS APPLY sys.dm_exec_sql_text(qs.sql_handle) t
WHERE t.text LIKE N'%/*pomiar*/%' AND t.text NOT LIKE N'%dm_exec_query_stats%';
GO
;WITH XMLNAMESPACES (DEFAULT 'http://schemas.microsoft.com/sqlserver/2004/07/showplan')
SELECT '$(ETAP)' AS etap, r.o.value('@PhysicalOp', 'varchar(60)') AS operator,
       r.o.value('@EstimateRows', 'varchar(30)') AS estymata_wierszy,
       r.o.value('@EstimatedExecutionMode', 'varchar(10)') AS tryb
FROM (SELECT TOP (1) CAST(p.query_plan AS xml) AS pl
      FROM sys.dm_exec_query_stats qs CROSS APPLY sys.dm_exec_sql_text(qs.sql_handle) t CROSS APPLY sys.dm_exec_query_plan(qs.plan_handle) p
      WHERE t.text LIKE N'%/*pomiar*/%' AND t.text NOT LIKE N'%dm_exec_query_stats%') x
CROSS APPLY x.pl.nodes('//RelOp') r(o);
GO
