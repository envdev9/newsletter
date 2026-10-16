-- 04-cleanup.sql: usuwa baze demo i przywraca domyslne ustawienie feedbacku (konfiguracja jest na poziomie bazy, wiec i tak znika z baza)
IF DB_ID('StatLab') IS NOT NULL
BEGIN
    ALTER DATABASE StatLab SET SINGLE_USER WITH ROLLBACK IMMEDIATE;
    DROP DATABASE StatLab;
END
GO
