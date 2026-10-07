# Antywzorce (czego nie robić)

- Nie składaj SQL przez konkatenację ani interpolację wartości. Zawsze parametry Dappera. Powód: SQL injection.
- Nie używaj `SELECT *`. Powód: kruche mapowanie, zbędny transfer.
- Nie buduj connection stringów ręcznie. Użyj `AddNpgsqlDataSource("db")`. Powód: omija pulę, health check i telemetrię z Aspire.
- Nie uruchamiaj migracji w `Main` każdej repliki. Powód: wyścig przy wielu replikach.
- Nie trzymaj stanu w pamięci procesu, od którego zależy poprawność. Powód: wiele replik, restarty.
- Nie edytuj zastosowanych skryptów SQL. Dodaj nowy. Powód: SqlDeployer ich nie wykona ponownie.
- Nie pisz testów integracyjnych na SQLite ani mockach połączenia. Powód: nie wykryją błędów SQL i mapowania.
- Nie kieruj testów ani migracji na bazę inną niż testowa/lokalna.
- Nie zapisuj sekretów w repo, obrazie ani logach.
