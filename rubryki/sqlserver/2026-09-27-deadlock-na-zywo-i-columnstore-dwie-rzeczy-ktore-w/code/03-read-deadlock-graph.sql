-- 03-read-deadlock-graph.sql - odczyt deadlock graph z sesji XE system_health (dziala domyslnie, nic nie wlaczasz).
-- Uwaga: plik .xel jest zapisywany z opoznieniem; jesli wynik pusty, odczekaj chwile i powtorz.
-- Uruchamiaj z sqlcmd -I (QUOTED_IDENTIFIER ON, wymagane przez metody XML).
SET NOCOUNT ON;
GO
-- (1) Surowy graf (XML). Uwaga: zawiera dlugie <stackFrames> - w SSMS kliknij w komorke.
--     Zapisany jako .xdl otwiera sie w SSMS jako graficzny deadlock graph.
SELECT TOP (1)
       CAST(event_data AS xml).value('(event/@timestamp)[1]', 'datetime2') AS utc_time,
       CAST(event_data AS xml).query('(event/data[@name="xml_report"]/value/deadlock)[1]') AS deadlock_graph
FROM sys.fn_xe_file_target_read_file(N'system_health*.xel', NULL, NULL, NULL)
WHERE object_name = N'xml_deadlock_report'
ORDER BY 1 DESC;
GO
-- (2) Ten sam graf splaszczony do czytelnej tabeli: kto kogo blokuje.
WITH last_dl AS
(
    SELECT TOP (1) CAST(event_data AS xml).query('(event/data[@name="xml_report"]/value/deadlock)[1]') AS dl
    FROM sys.fn_xe_file_target_read_file(N'system_health*.xel', NULL, NULL, NULL)
    WHERE object_name = N'xml_deadlock_report'
    ORDER BY CAST(event_data AS xml).value('(event/@timestamp)[1]', 'datetime2') DESC
)
SELECT p.n.value('@spid', 'int')                          AS spid,
       IIF(p.n.value('@id', 'varchar(50)') = d.dl.value('(deadlock/victim-list/victimProcess/@id)[1]', 'varchar(50)'),
           'OFIARA', 'przezyl')                           AS rola,
       p.n.value('@waitresource', 'varchar(100)')         AS czeka_na,
       p.n.value('@lockMode', 'varchar(5)')               AS tryb,
       p.n.value('@isolationlevel', 'varchar(50)')        AS izolacja,
       LEFT(LTRIM(p.n.value('(inputbuf)[1]', 'nvarchar(max)')), 45) AS poczatek_batcha
FROM last_dl d
CROSS APPLY d.dl.nodes('deadlock/process-list/process') AS p(n);
GO
