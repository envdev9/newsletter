-- 05-rcsi-on.sql - wlacza READ_COMMITTED_SNAPSHOT (czytelnicy czytaja ostatnia zatwierdzona wersje wiersza, bez blokad S).
-- WITH ROLLBACK IMMEDIATE: zmiana wymaga braku innych polaczen do bazy.
ALTER DATABASE PrasowkaLock SET READ_COMMITTED_SNAPSHOT ON WITH ROLLBACK IMMEDIATE;
GO
