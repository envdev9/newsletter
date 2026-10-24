<div align="center">

# 🗄️ SQL Server

### TECH PRASÓWKA — wszystkie artykuły rubryki, najnowsze na górze

</div>

---

Każdy artykuł to osobny folder `<data>-<tytuł>/` z `ARTICLE.md` i pełnym, uruchamialnym
kodem w `code/`. Kolejne artykuły podnoszą poziom — postęp rubryki jest w
[`STATE.md`](../../STATE.md).

| Data | Artykuł | W skrócie | Kod |
|------|---------|-----------|-----|
| 2026-10-16 | [Spill do tempdb, który sam się leczy. I statystyki, które odświeżają się „po fakcie"](2026-10-16-spill-do-tempdb-ktory-sam-sie-leczy-i-statystyki-ktore/ARTICLE.md) | Spill do tempdb leczy się sam po jednym wykonaniu (memory grant feedback), ale estymata zostaje zła, a `AUTO_UPDATE_STATISTICS_ASYNC` oznacza, że pierwsze zapytanie po zmianie danych zawsze jedzie na starych statystykach. | [Kod](2026-10-16-spill-do-tempdb-ktory-sam-sie-leczy-i-statystyki-ktore/code/) |
| 2026-10-09 | [PSP broni tylko jednego predykatu. Hint wariantu wygrywa z rodzicem. A statystyki „zamrożone" kosztują 2,3× czasu](2026-10-09-psp-broni-tylko-jednego-predykatu-hint-wariantu-wygrywa-z/ARTICLE.md) | PSP chroni w zapytaniu tylko jedną skośną kolumnę (wygrywa większy iloraz max:min), hint wariantu wygrywa z hintem rodzica, a wyłączone auto-update statystyk potrafi zjeść 2,3× czasu zapytania. | [Kod](2026-10-09-psp-broni-tylko-jednego-predykatu-hint-wariantu-wygrywa-z/code/) |
| 2026-10-07 | [PSP „nie działa", bo Twoje dane nie są dość skośne. Plus: columnstore sprząta się sam — po 4 minutach](2026-10-07-psp-nie-dziala-bo-twoje-dane-nie-sa-dosc-skosne-plus/ARTICLE.md) | Silnik sam mówi, czemu PSP odpuścił: nasze dane miały skośność 1 900×, a próg leży gdzieś przy 100 000× — po jego przekroczeniu mały tenant czyta 5 stron zamiast 5 166, a `OPTIMIZE FOR UNKNOWN` na złym wariancie podnosi koszt dużego do 582 215 reads. | [Kod](2026-10-07-psp-nie-dziala-bo-twoje-dane-nie-sa-dosc-skosne-plus/code/) |
| 2026-10-04 | [DELETE na columnstore nie usuwa nic. I licznik, który to powinien pokazać, też milczy](2026-10-04-delete-na-columnstore-nie-usuwa-nic-i-licznik-ktory-to/ARTICLE.md) | `DELETE`/`UPDATE` na tabeli z nonclustered columnstore: dane giną z zapytań natychmiast, ale licznik skasowanych wierszy w katalogu systemowym milczy, dopóki `REORGANIZE`/`REBUILD` nie dotknie indeksu — plus `sp_query_store_set_hints`, które wstrzykuje `OPTION(RECOMPILE)` bez zmiany kodu. | [Kod](2026-10-04-delete-na-columnstore-nie-usuwa-nic-i-licznik-ktory-to/code/) |
| 2026-09-29 | [Columnstore w OLTP i wyścig, którego SERIALIZABLE nie rozwiązuje elegancko](2026-09-29-columnstore-w-oltp-i-wyscig-ktorego-serializable-nie/ARTICLE.md) | Nonclustered columnstore obok zwykłego OLTP — optymalizator sam wybiera Index Seek albo skan kolumnowy — a osobno: `SERIALIZABLE` "naprawia" wyścig o numer faktury deadlockiem 1205, `sp_getapplock` tym samym problemem zajmuje się bez błędu. | [Kod](2026-09-29-columnstore-w-oltp-i-wyscig-ktorego-serializable-nie/code/) |
| 2026-09-27 | [Deadlock na żywo i columnstore: dwie rzeczy, które w produkcji bolą najbardziej](2026-09-27-deadlock-na-zywo-i-columnstore-dwie-rzeczy-ktore-w/ARTICLE.md) | Deadlock wywołany na żywo i odczytany z `system_health`, czytelnik czekający 4,7 s kontra 0 ms po `READ_COMMITTED_SNAPSHOT` oraz columnstore na 5 mln wierszy: agregacja w 27 ms zamiast 892 ms — prawdziwy output z SQL Server 2022. | [Kod](2026-09-27-deadlock-na-zywo-i-columnstore-dwie-rzeczy-ktore-w/code/) |
| 2026-09-26 | [Leczenie parameter sniffingu: RECOMPILE, OPTIMIZE FOR, Query Store i filtered index](2026-09-26-leczenie-parameter-sniffingu-recompile-optimize-for-query/ARTICLE.md) | Ten sam plan raz 21, raz 600 350 stron: cztery sposoby na parameter sniffing, a Query Store przypina dobry plan bez zmiany kodu, plus filtered index, który zamiast 1 051 stron ma 2 — zmierzone na SQL Server 2022. | [Kod](2026-09-26-leczenie-parameter-sniffingu-recompile-optimize-for-query/code/) |
| 2026-09-25 | [Ten sam plan, 241 razy drożej: statystyki, Key Lookup i parameter sniffing](2026-09-25-ten-sam-plan-241-razy-drozej-statystyki-key-lookup-i/ARTICLE.md) | Ten sam indeks, ta sama procedura, 241× różnicy w odczytach — statystyki, Key Lookup i parameter sniffing na prawdziwych planach SQL Server 2022, a covering index jako lekarstwo. | [Kod](2026-09-25-ten-sam-plan-241-razy-drozej-statystyki-key-lookup-i/code/) |
| 2026-09-24 | [Indeks to nie magia — to B-drzewo, które oszczędza SQL Serwerowi czytanie całej tabeli](2026-09-24-indeks-to-nie-magia-to-b-drzewo-ktore-oszczedza-sql/ARTICLE.md) | Plik wsadowy pokazujący różnicę w planie wykonania z indeksem i bez — kod gotowy, | [Kod](2026-09-24-indeks-to-nie-magia-to-b-drzewo-ktore-oszczedza-sql/code/) |
<!-- kolejne wiersze dopisywane automatycznie, najnowsze na górze -->

---

<div align="center">

[← spis rubryk](../../README.md)

</div>
