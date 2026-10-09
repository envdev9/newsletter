<div align="center">

# 📰 TECH PRASÓWKA
### Wydanie #16 — 9 października 2026

![SQL Server](https://img.shields.io/badge/SQL_Server-CC2927?style=for-the-badge&logo=microsoftsqlserver&logoColor=white)
![Poziom](https://img.shields.io/badge/poziom-zaawansowany-orange?style=for-the-badge)
![Zweryfikowane](https://img.shields.io/badge/kod-uruchomiony_na_SQL_Server_2022_CU27-brightgreen?style=for-the-badge)

## PSP broni tylko jednego predykatu. Hint wariantu wygrywa z rodzicem. A statystyki „zamrożone" kosztują 2,3× czasu

</div>

---

> _"Dwie skośne kolumny w jednym zapytaniu, PSP włączony, plany rozdzielone na warianty — i
> mimo to jedno z wywołań dalej robi pełny skan. Bo silnik wybrał do ochrony **jeden**
> predykat. Pytanie, który i jak to sprawdzić."_

**🎣 Dlaczego to ważne:** w #14 pokazaliśmy, że PSP ruszy dopiero przy ekstremalnej skośności
i że hint Query Store dziedziczą warianty. Zostały trzy pytania, na które odpowiedź
decyduje o tym, czy w produkcji PSP faktycznie Cię chroni: **(1)** co, gdy zapytanie ma
kilka skośnych predykatów (typowy multi-tenant: `TenantId` + `Region`)? **(2)** gdy hint
stoi i na rodzicu, i na wariancie, a są sprzeczne — kto wygrywa? **(3)** ile naprawdę
kosztuje wyłączone `AUTO_UPDATE_STATISTICS` na tabeli z columnstore, gdy ktoś „tylko"
dosypie dane? Wszystko poniżej to liczby z realnego uruchomienia.

Kod: [`code/`](code/), SQL Server 2022 RTM-CU27 (16.0.4295.3, Developer, Linux, Docker
`mcr.microsoft.com/mssql/server:2022-latest`, kontener z 2 CPU). Całość przeszła dwa razy
od zera (nowy kontener) z identycznymi liczbami; kilka rzeczy jest niezweryfikowanych —
lista na końcu.

---

## 1️⃣ PSP z wieloma predykatami: dostajesz ochronę jednego

Tabela `dbo.Ev` (200 000 wierszy), dwie skośne kolumny i jedna równomierna:

| kolumna | rozkład (najczęstsza : najrzadsza wartość) |
|---|---|
| `TenantId` | 1 → 190 000 wierszy, 2 → 1 wiersz |
| `Region` | 1 → 179 999, 2 → 1 |
| `Kind` | 20 wartości po ok. 10 000 |

Procedura filtruje po wszystkich trzech (`TenantId = @TenantId AND Region = @Region AND Kind = @Kind`),
każda kolumna ma własny indeks. Cztery wywołania, kolejność ma znaczenie (gigant pierwszy):

| wywołanie | logical reads | co się stało |
|---|---:|---|
| `(1, 1, 5)` gigant + dominujący region | 5 737 | skan (poprawnie) |
| `(2, 2, 5)` mały + mały | **5** | wariant „mały" — seek |
| `(2, 1, 5)` mały tenant + dominujący region | **5** | wariant „mały" |
| `(1, 2, 5)` gigant tenant + **mały region** | **5 737** | pełny skan, choć `Region = 2` to **1 wiersz** |

Ostatni wiersz to sedno. XE `query_with_parameter_sensitivity` zgłosił `max_skewness = 190000`,
a plan cache pokazuje dwa warianty z jednym predykatem:

```
option (PLAN PER VALUE(ObjectID = …, QueryVariantID = 1, predicate_range([PspMulti].[dbo].[Ev].[TenantId] = @TenantId, 100.0, 100000.0)))
option (PLAN PER VALUE(ObjectID = …, QueryVariantID = 3, predicate_range([PspMulti].[dbo].[Ev].[TenantId] = @TenantId, 100.0, 100000.0)))
```

Do `predicate_range` wszedł **tylko `TenantId`**, choć `Region` (iloraz 179 999) też przekracza
próg z #14. Cena: `(1, 2, 5)` kosztuje 5 737 reads, a ten sam `SELECT` skompilowany pod te
wartości (`OPTION (RECOMPILE)`) — **5 reads** (ok. 1 150× mniej).

### Który predykat wybiera PSP?

Zbudowaliśmy cztery tabele z tymi samymi 200 000 wierszami i różnymi rozkładami
([`04`](code/04-ktory-predykat.sql)), plus ta z `Ev`. Hipotezy: (H1) pierwszy w `WHERE`,
(H2) najbardziej skośny.

| tabela | `TenantId` (max:min) | `Region` | kolejność w `WHERE` | wybrany predykat |
|---|---:|---:|---|---|
| `Ev` | 190 000 | 179 999 | T, R, Kind | `TenantId` |
| `EvC` | 150 000 | 199 999 | T, R | **`Region`** |
| `EvE` | 150 000 | 199 999 | **R**, T | `Region` |
| `EvF` | 190 000 | 179 999 | R, T | **`TenantId`** |
| `EvD` | 190 000 | 190 000 (remis) | T, R | `Region` |

- **H1 odpada:** w `EvC` pierwszy w `WHERE` jest `TenantId`, a PSP wziął `Region`; w `EvF` odwrotnie.
- **Pasuje H2:** wygrywa kolumna o większym ilorazie. Raportowane `max_skewness` to
  maksimum po predykatach: 199 999, 190 000, 199 999, 190 000 dla kolejnych tabel (`EvC`, `EvD`, `EvE`, `EvF`).
- **Remis (`EvD`)** rozstrzygnął się na korzyść `Region` (drugiej w `WHERE`, drugiej w
  tabeli) — jeden punkt pomiarowy, reguły rozstrzygania remisu **nie znamy**.
- We wszystkich pięciu tabelach wariant miał **jeden** predykat, mimo że oba były powyżej
  progu. Dokumentacja mówi o możliwości kilku predykatów; my takiego przypadku nie wywołaliśmy.

> 💡 **Dla .NET-owca:** PSP nie jest „ochroną zapytania", tylko ochroną jednej kolumny
> w zapytaniu. Jeśli masz wzorzec `TenantId` + `Region`, sprawdź w Query Store
> (`sys.query_store_query_variant` + tekst z `predicate_range`), **którą** kolumnę zabezpieczył.
> Druga nadal jest narażona na parameter sniffing. Hint `RECOMPILE` na rodzicu to nie
> lekarstwo — wyłącza PSP w całości (#14).

---

## 2️⃣ Hint na wariancie vs hint na rodzicu: wariant wygrywa

W #14 sprawdziliśmy dziedziczenie z rodzica. Teraz konflikt: dwa **sprzeczne** hinty
`USE HINT`, [`06`](code/06-hint-wariant-vs-rodzic.sql):

- `FORCE_LEGACY_CARDINALITY_ESTIMATION` → plan z `CardinalityEstimationModelVersion="70"`,
- `FORCE_DEFAULT_CARDINALITY_ESTIMATION` → `"160"` (compat 160).

Wersja CE to jednoznaczny sygnał, który hint zadziałał. Czytamy ją z planu **w plan cache**,
razem z atrybutami `QueryStoreStatementHintText` i `QueryStoreStatementHintSource="User"`,
które silnik dopisuje do planu zastosowanego hintu. Przed każdym scenariuszem
`DBCC FREEPROCCACHE` (tylko instancja testowa!).

| scenariusz | wariant 1 (mały) | wariant 3 (duży) |
|---|---|---|
| S0: bez hintów | 160 | 160 |
| S1: `LEGACY` tylko na rodzicu | **70** (dziedziczy) | **70** (dziedziczy) |
| S2: rodzic `LEGACY`, wariant 3 `DEFAULT` | 70 | **160** — wygrał hint wariantu |
| S3: rodzic `DEFAULT`, wariant 3 `LEGACY` | 160 | **70** — wygrał hint wariantu |
| S4: tylko wariant 3 `LEGACY` | 160 | 70 |

Pierwszeństwo: **hint wariantu nadpisuje hint rodzica**, w obu kierunkach (S2 i S3, więc
to nie kwestia tego, który CE jest „nowszy"). Wariant bez własnego hintu dziedziczy
rodzica (S1, S2: wariant 1 ma 70). Uwaga: w S2 i S3 hint wariantu był ustawiany **po**
hincie rodzica, więc nie rozróżniliśmy „wariant wygrywa" od „ostatnio ustawiony wygrywa"
— odwrotnej kolejności ustawiania (wariant, potem rodzic) nie testowaliśmy.

> ⚠️ **Pułapka diagnostyczna:** próba odczytu wersji CE z `sys.query_store_plan` pokazywała
> w każdym scenariuszu `160` — po ustawieniu hintu Query Store **nie dopisał nowego planu**
> (jedno `plan_id` na wariant). Hint widać w `sys.query_store_query_hints` i w planie z plan
> cache, nie w katalogu planów QS. Sprawdzaj efekt tam, gdzie plan naprawdę siedzi.

---

## 3️⃣ `AUTO_UPDATE_STATISTICS OFF` na tabeli z NCCI: cena nieaktualnych statystyk

W #14 pokazaliśmy, że `REORGANIZE`/`REBUILD` nie odświeżają statystyk. Tu skrajny
przypadek: baza z `AUTO_UPDATE_STATISTICS = OFF` (`AUTO_CREATE` zostaje `ON`; w produkcji
bywa wyłączane, żeby uniknąć nieprzewidzianych aktualizacji w godzinach szczytu).

[`07`](code/07-stale-setup.sql): `dbo.Orders` 1 000 000 wierszy (klucz klastrowy + NCCI na
`CustomerId, Status, Amount`), pierwsze zapytania tworzą auto-statystyki, potem **dosypujemy
600 000 wierszy z nową wartością `Status = 7`**. Stan statystyki: `rows = 1 000 000`,
`modification_counter = 600 000`, tabela ma 1 600 000.

Zapytanie ([`08`](code/08-stale-pomiar.sql)): join z `dbo.Customers` (500 000), filtr
`Status = 7`, `GROUP BY` imienia + `ORDER BY SUM`. `DBCC DROPCLEANBUFFERS` i czyszczenie
cache przed każdym pomiarem:

| | nieaktualne | po `UPDATE STATISTICS … FULLSCAN` |
|---|---:|---:|
| estymata wierszy dla `Status = 7` (faktycznie 600 000) | **1 264,91** | **600 000** |
| join | Adaptive Join, tryb **Row** | Adaptive Join, tryb **Batch** |
| DOP | **1** (plan szeregowy) | **2** |
| przydział pamięci (grant) | 245 040 KB (użyto 82 952) | 435 416 KB (użyto 200 704) |
| spille do tempdb | 0 | 0 |
| czas | **1 651 ms** (1 643 ms w powtórce) | **701 ms** |

Czyli **2,3× wolniej** przez estymatę zaniżoną ok. 474-krotnie. Efekt widać w kształcie
planu: szeregowy zamiast równoległego i adaptive join w trybie wierszowym zamiast wsadowego.
Estymata 1 264,91 jest liczbowo równa `SQRT(1 600 000)` — obserwacja arytmetyczna, mechanizmu
nie sprawdzaliśmy.

Uczciwe zastrzeżenia: (a) **nie** wystąpił spill (grant zbyt mały to częsty skutek
nieaktualnych statystyk, ale tu go nie wywołaliśmy — przy nieaktualnych statystykach grant był
w ogóle niższy, 245 MB vs 435 MB, a mimo to wystarczył), (b) wynik to różnica **całego planu**
(równoległość + tryb batch), nie jednej decyzji; część zysku to po prostu drugi rdzeń,
(c) po jednym pomiarze na etap (nieaktualne powtórzone, swieże zmierzone w dwóch
niezależnych kontenerach: 727 i 701 ms), kontener ma 2 CPU, więc to rząd wielkości, nie benchmark.

> 💡 **Dla .NET-owca:** przy `AUTO_UPDATE_STATISTICS = OFF` każdy job ładujący dane to
> zadanie `UPDATE STATISTICS` na końcu. Najgorszy scenariusz nie dotyczy zmiany *rozkładu*
> znanych wartości, tylko **nowych wartości poza histogramem** (nowy tenant, nowy status,
> nowa data) — optymalizator zakłada, że to garstka wierszy.

---

## 🧾 Ściąga na dziś

| Pojęcie | Jedno zdanie |
|---|---|
| PSP z kilkoma predykatami | w każdej z 5 tabel w wariantach był **jeden** predykat, choć dwa przekraczały próg |
| Wybór predykatu | wygrywa o większym ilorazie max:min (nie pierwszy w `WHERE`); remis: nieznana reguła |
| Cena niechronionego predykatu | gigant + `Region = 2`: 5 737 vs 5 reads (`RECOMPILE`) |
| Hint wariantu vs rodzica | wariant nadpisuje rodzica (S2, S3; hint wariantu ustawiany zawsze po rodzicu); bez własnego hintu wariant dziedziczy |
| Gdzie widać hint | `sys.query_store_query_hints` i plan w plan cache (`QueryStoreStatementHint*`); QS nie dopisuje planu |
| `AUTO_UPDATE_STATISTICS OFF` + nowa wartość | estymata 1 265 vs 600 000, plan szeregowy, 1 651 vs 701 ms (2,3×) |
| Naprawa | `UPDATE STATISTICS … WITH FULLSCAN` po każdym dużym ładowaniu |

**Pełny, uruchamialny kod + komendy:** [`code/README.md`](code/README.md).

**Co dalej:** PSP z dwoma predykatami **w jednym wariancie** (czy da się go wywołać),
reguła rozstrzygania remisu, mechanizm w tle czyszczący `TOMBSTONE`, prawdziwy spill z
`AUTO_UPDATE_STATISTICS OFF` (zbyt mały grant), `AUTO_UPDATE_STATISTICS_ASYNC` vs
synchroniczny update, `OPTIMIZE FOR` w hintach QS na wariancie.

---

## ✅ Status weryfikacji

Pełna sekwencja `01`→`10` wykonana **dwa razy od zera** (kontenery `prasowka16-` i
`prasowka16b-sqlserver`): pierwszy raz z iteracjami skryptów, drugi raz po poprawkach;
liczby (reads, `max_skewness`, wybór predykatu, wersje CE, estymaty, grant) powtórzyły się
identycznie, czasy: 1 664/1 651 ms vs 727/701 ms.

Uczciwe uwagi:

1. `run-demo.sh` **nie został odpalony** (Bash sandboksa blokuje `.sh`); kroki wykonane
   ręcznie przez `docker exec … sqlcmd` w kolejności ze skryptu. Skrypt niezweryfikowany jako plik.
2. Nie wywołaliśmy przypadku z **dwoma predykatami w jednym wariancie**; wniosek „jeden predykat"
   dotyczy tylko naszych pięciu tabel (dwie skośne kolumny, w `Ev` trzecia równomierna).
   Reguła remisu (`EvD`) — jeden punkt pomiarowy.
3. Wniosek „wygrywa większy iloraz" to hipoteza z czterech tabel (plus `Ev`), nie z dokumentacji.
4. Pierwszeństwo hintu wariantu sprawdzone tylko na `USE HINT` (`FORCE_LEGACY/DEFAULT_CARDINALITY_ESTIMATION`),
   tylko w kolejności „rodzic, potem wariant"; inne hinty (`OPTION(…)` bez `USE HINT`) nie testowane.
5. W części 3 plan z `Status = 7` porównaliśmy wskaźnikami z `dm_exec_query_stats` i planem
   z cache (estymaty); faktycznych liczb wierszy z planu wykonania nie zbieraliśmy (znamy
   je z `COUNT`).
6. Mechanizm i harmonogram czyszczenia `TOMBSTONE` — **nie badane** w tym wydaniu.
7. Dokładny próg skośności między 95 000 a 100 000 — **nie badany**.
8. Kontenery (z wolumenami) usunięte po testach; obraz pozostawiono.

---

<div align="center">

[← wróć do wydania #16 (wszystkie rubryki)](../README.md) · [spis wydań](../../README.md)

</div>
