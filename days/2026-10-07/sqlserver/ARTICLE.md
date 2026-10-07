<div align="center">

# 📰 TECH PRASÓWKA
### Wydanie #14 — 7 października 2026

![SQL Server](https://img.shields.io/badge/SQL_Server-CC2927?style=for-the-badge&logo=microsoftsqlserver&logoColor=white)
![Poziom](https://img.shields.io/badge/poziom-zaawansowany-orange?style=for-the-badge)
![Zweryfikowane](https://img.shields.io/badge/kod-uruchomiony_na_SQL_Server_2022_CU27-brightgreen?style=for-the-badge)

## PSP „nie działa", bo Twoje dane nie są dość skośne. Plus: columnstore sprząta się sam — po 4 minutach

</div>

---

> _"Włączony compat 160, włączona opcja PSP, skośne dane jak na obrazku z dokumentacji —
> a plan i tak jeden dla wszystkich. Okazuje się, że silnik **potrafi powiedzieć, dlaczego
> odpuścił**. Wystarczy go zapytać."_

**🎣 Dlaczego to ważne:** w #3 i #8 PSP (Parameter Sensitive Plan) „nie zadziałał" i
zostawiliśmy to jako otwartą zagadkę. Dziś ją zamykamy — bez zgadywania, bo istnieje
Extended Event, który wprost loguje **powód pominięcia** optymalizacji. Okazało się, że
nasze dane (95% wierszy u jednego tenanta, reszta po 100) były za mało skośne dla
progu, który ustala silnik. Druga część: co się dzieje z columnstore **po** `REORGANIZE`
i `REBUILD` — kiedy znikają rowgroupy `TOMBSTONE` (po ok. 4 minutach, sami nic nie robiąc)
i czy trzeba ręcznie aktualizować statystyki (po `DELETE` nie, po `REBUILD` — `REBUILD` ich
**nie rusza**).

Wszystkie liczby pochodzą z realnego uruchomienia kodu z [`code/`](code/) na
`mcr.microsoft.com/mssql/server:2022-latest` (SQL Server 2022 RTM-CU27, 16.0.4295.3,
Developer Edition on Linux, Docker). Całość przeszła **dwa razy od zera** (nowy kontener
za drugim razem) z tymi samymi wynikami — z wyjątkiem czasu z punktu 4, gdzie widać
niewielki rozrzut (opisany uczciwie).

---

## 1️⃣ Zamknięcie wątku z #3/#8: dlaczego PSP nie ruszył

### Najpierw: sprawdźmy, jak to wyglądało u nas

Procedura z #8 (`SELECT … FROM dbo.Events WHERE TenantId = @TenantId`), tabela 200 000
wierszy, `TenantId = 1` ma 190 000, 100 innych tenantów po 100. Compat 160, PSP `ON`,
Query Store włączony. Duży tenant kompiluje plan, mały dostaje ten sam:

```
EXEC … @TenantId = 1;  -- Table 'Events'. Scan count 1, logical reads 5427
EXEC … @TenantId = 2;  -- Table 'Events'. Scan count 1, logical reads 5427   <- 100 wierszy, pełny skan
psp_w_planie: NIE - zwykly plan, execution_count 2
```

(Tabela ma tu szerszy wiersz niż w #8, stąd 5427 zamiast 3141 reads — ta sama historia.)

### Zamiast zgadywać: zapytajmy silnik

Dokumentacja wymienia Extended Event `parameter_sensitive_plan_optimization_skipped_reason`.
Jego słownik (`sys.dm_xe_map_values`, `psp_skipped_reason_enum`) ma **40 powodów** — m.in.
`WithRecompileFlag`, `QueryHint`, `HasLocalVar`, `ParamSniffDisabled`, `AutoParameterized`,
`CompatLevelBelow160`, `UnsupportedStatementType` i ten, który nas dotyczył:
**`SkewnessThresholdNotMet`**. Sesja z [`03-psp-diagnoza.sql`](code/03-psp-diagnoza.sql):

```sql
CREATE EVENT SESSION psp_diag ON SERVER
    ADD EVENT sqlserver.parameter_sensitive_plan_optimization_skipped_reason (ACTION (sqlserver.sql_text)),
    ADD EVENT sqlserver.query_with_parameter_sensitivity                     (ACTION (sqlserver.sql_text))
    ADD TARGET package0.ring_buffer WITH (MAX_DISPATCH_LATENCY = 1 SECONDS);
```

Wynik dla naszej procedury (`INSERT … EXEC` na zewnątrz daje dodatkowo
`UnsupportedStatementType` — to osobna sprawa, patrz niżej):

```
parameter_sensitive_plan_optimization_skipped_reason   SkewnessThresholdNotMet
```

**Prawdziwa przyczyna z #3/#8: dane za mało skośne.** Compat level i opcja PSP były
w porządku od początku — dlatego ich sprawdzanie niczego nie wyjaśniało.

### Jaki jest próg? Bisekcja na danych

Drugi event, `query_with_parameter_sensitivity`, raportuje `max_skewness` dla zapytań,
które PSP uznał za kandydatów. Zbudowaliśmy tabele o różnych rozkładach
([`04`](code/04-psp-rozklady.sql), [`05`](code/05-psp-prog-skosnosci.sql),
[`06`](code/06-psp-prog-ratio.sql)); gigant ma `g` wierszy, „mali" tenanci po `k`:

| gigant `g` | mali tenanci `k` | iloraz `g/k` | wynik |
|---:|---:|---:|---|
| 190 000 | 100 (nasze dane z #8) | 1 900 | `SkewnessThresholdNotMet` |
| 190 000 | 10 / 5 / 3 | 19 000 / 38 000 / 63 333 | `SkewnessThresholdNotMet` |
| 1 000, 10 000, 50 000 | 1 | 1 000 – 50 000 | `SkewnessThresholdNotMet` |
| 190 000 | 2 | 95 000 | `SkewnessThresholdNotMet` |
| 100 000 (+ 10 średnich po 5 000 i ok. 50 000 unikalnych) | 1 | 100 000 | **kandydat PSP**, `max_skewness = 100000` |
| 190 000 | 1 | 190 000 | **kandydat PSP**, `max_skewness = 190000` |

Zgadza się to z hipotezą „skośność = największy `EQ_ROWS` w histogramie podzielony przez
najmniejszy" — raportowane `100000` i `190000` to dokładnie te ilorazy — a próg leży
**między 95 000 a 100 000**. Uwaga: to **wniosek z eksperymentu**, nie z dokumentacji;
dokumentacja nie podaje progu ani wzoru (zweryfikowaliśmy tylko, że tabela powyżej tak
wygląda na tej wersji silnika). Praktyczny sens: **PSP chroni przed skrajną skośnością
(rząd 10⁵×), nie przed „zwykłą" 2000-krotną** — taką, jaka w realnych bazach multi-tenant
jest bardzo częsta.

### Kiedy próg jest spełniony — efekt

[`07-psp-dziala.sql`](code/07-psp-dziala.sql): dwie tabele, ta sama procedura, ta sama
kolejność wywołań (duży tenant pierwszy). `Ev_k2` — iloraz 95 000; `Ev_k1` — iloraz 190 000:

| | duży tenant (190 000 wierszy) | mały tenant (1–2 wiersze) |
|---|---:|---:|
| bez PSP (`Ev_k2`) | 5 166 reads | **5 166 reads** (cudzy plan: pełny skan) |
| z PSP (`Ev_k1`) | 5 161 reads | **5 reads** (≈ 1000× mniej) |

Plan cache pokazuje dwa warianty z `option (PLAN PER VALUE(… QueryVariantID = 1 …))` i
`QueryVariantID = 3`. W Query Store `sys.query_store_query_variant` mapuje rodzica
(`query_id = 2`) na dwa dzieci (`query_id` 4 = wariant 1, `query_id` 3 = wariant 3).

> ⚠️ **Jedna pułapka z diagnozy:** `INSERT #t EXEC proc` i `INSERT … SELECT` dają powód
> `UnsupportedStatementType` — w SQL Server 2022 PSP nie obsługuje DML (dopiero 2025 z
> compat 170, tak twierdzi dokumentacja; nie sprawdzaliśmy). Wniosek praktyczny: **jeśli
> mierzysz PSP, nie owijaj wywołania w `INSERT … EXEC`** — dostaniesz fałszywy negatyw.
> Nasz pierwszy pomiar w tej sesji zrobił dokładnie ten błąd.

---

## 2️⃣ Query Store hint na zapytaniu z PSP: per-wariant, i dziedziczony z rodzica

Pytanie z #8: gdy jedno zapytanie ma dwa różne `plan_id`/`query_id` — do czego przypina
się hint? Odpowiedź (z uruchomienia [`08`](code/08-psp-query-store-hints.sql)):
**do `query_id`, więc do wariantu, jeśli wskażesz wariant; a hint z rodzica dostają
dzieci.**

Użyliśmy `OPTION(OPTIMIZE FOR UNKNOWN)`, bo ma wyraźny efekt w reads. Najpierw jedna
niespodzianka: `sp_query_store_set_hints` odrzuca `OPTION(TABLE HINT(...))` i
`OPTION(OPTIMIZE FOR (@p = 1))` błędem 12455 „not supported" — z hintów obiecujących
widoczny efekt zostaje `OPTIMIZE FOR UNKNOWN`, `RECOMPILE`, `USE HINT` itp. (nie
testowaliśmy całej listy).

| scenariusz | duży tenant | mały tenant |
|---|---:|---:|
| bez hintów | 5 161 | 5 |
| `OPTIMIZE FOR UNKNOWN` **tylko na wariancie 3** (duży) | **582 215** (113× gorzej) | 5 (bez zmian) |
| ten sam hint **na rodzicu** (żaden wariant nie ma własnego) | **582 215** | 6 |

- Hint na wariancie 3 zepsuł **tylko** ten wariant: reads dużego tenanta skoczyły z 5 161
  do 582 215, mały wariant został nietknięty. Planu nie oglądaliśmy; skala (ok. 3 reads
  na wiersz) wskazuje na seek + lookupy zaplanowane z gęstości średniej zamiast ze
  skośnej wartości parametru — to interpretacja, nie zweryfikowany fakt.
- Hint ustawiony **tylko na rodzicu** (`sys.query_store_query_hints` ma wiersz tylko dla
  `query_id = 2`) ma ten sam skutek dla dużego tenanta — czyli dzieci go odziedziczyły.
  Mały tenant: 5 → 6 reads (drobna zmiana planu; nie rozstrzygamy dlaczego).
- To zgadza się z dokumentacją (dziecko dziedziczy, własny hint wariantu ma pierwszeństwo)
  — ale my zweryfikowaliśmy tylko dziedziczenie z rodzica; **pierwszeństwa hintu wariantu
  nad hintem rodzica nie testowaliśmy**.
- **`OPTION(RECOMPILE)` na rodzicu wyłącza PSP**: XE pokazuje powód `WithRecompileFlag`
  (6 zdarzeń w sesji), a reads wracają do 5 161 / 5, bo każde wywołanie dostaje własną
  kompilację. Czyli hint z #8 „na bogato" **wycina PSP** — nie ma co ich łączyć.

> 💡 **Dla .NET-owca:** nie zakładaj, że hint z Query Store zadziała „na zapytanie". Przy
> PSP musisz wybrać poziom (rodzic czy wariant), a źle dobrany `OPTIMIZE FOR UNKNOWN` na
> wariancie z gigantem kosztuje 113× więcej reads. Zawsze mierz `STATISTICS IO` po
> `sp_query_store_set_hints` + `sp_recompile`.

---

## 3️⃣ Columnstore po `REORGANIZE`/`REBUILD`: `TOMBSTONE` i statystyki

Tabela `dbo.Orders` jak w #7/#8 (1 200 000 wierszy, klucz klastrowany + NCCI na czterech
kolumnach), `DELETE … WHERE Status = 3` kasuje 300 000 wierszy (25%) — plik
[`10`–`19`](code/).

### `TOMBSTONE` znikają same — po ok. 3,5–4 minutach

Po `REORGANIZE WITH (COMPRESS_ALL_ROW_GROUPS = ON)`:

```
rg  stan        total_rows  deleted_rows
0   COMPRESSED  1048576     262144       <- duży rowgroup, 25% martwych, REORGANIZE go nie ruszył
1   TOMBSTONE   85519       21380
2   TOMBSTONE   65905       16476
3   COMPRESSED  113568      0            <- scalenie 1+2 bez martwych: (85519-21380)+(65905-16476)=113568
```

[`17-tombstone-watch.sql`](code/17-tombstone-watch.sql) odpytuje stan co 15 s. Rowgroupy
`TOMBSTONE` zniknęły **bez żadnej naszej interwencji**: w pierwszym przebiegu między
t+225 s a t+255 s (najpierw jeden, potem drugi), w drugim (nowy kontener) między
t+195 s a t+210 s (oba naraz). Czyli rząd **3,5–4 minut** — z rozrzutem; mechanizmu w tle
(które zadanie to robi i jaki ma harmonogram) **nie zbadaliśmy**, więc nie nazywamy go.
Rowgroup 0 z 262 144 martwymi wierszami **został** — to nadal robota dla `REBUILD`.

`REBUILD` bez czekania: wszystkie `TOMBSTONE` znikają natychmiast, zostaje jeden rowgroup
`COMPRESSED` z `total_rows = 900000`, `deleted_rows = 0`.

> 💡 **Praktycznie:** jeśli skrypt konserwacyjny po `REORGANIZE` alarmuje o
> „rowgroupach TOMBSTONE", odczekaj kilka minut — to stan przejściowy. Alarm ma sens
> dopiero na `deleted_rows` dużych rowgroupów.

### Statystyki: `DELETE` ich nie psuje, `REBUILD` ich nie odświeża

Obiekt statystyk NCCI (`NCCI_Orders`) **nie ma histogramu** (`dm_db_stats_properties` →
`NULL`); estymaty biorą się z auto-utworzonej statystyki kolumny `Status`
(`_WA_Sys_…`). Co się z nią dzieje ([`11`](code/11-stats-snapshot.sql), [`16`](code/16-stats-only.sql)):

| etap | `rows` w stat | `modification_counter` | estymata dla `Status = 3` (faktycznie: 0) |
|---|---:|---:|---:|
| po buildzie | 1 200 000 | 0 | 299 297 / 299 321 (faktycznie 300 000) |
| po `DELETE` 300 000, przed zapytaniem | 1 200 000 | **300 000** | — |
| po pierwszym zapytaniu | **900 000** | 0 | **948,683** |

Auto-update zadziałał przy kompilacji następnego zapytania (próg `300 000 > ok. 34 641`
dla 1,2 mln wierszy — wzór `SQRT(1000 · N)` z dokumentacji, nie weryfikowaliśmy go
osobno). Estymata 948,683 dla pustego wyniku liczbowo równa się `SQRT(900000)` — tyle
podstawia optymalizator, gdy wartości nie ma w histogramie (to obserwacja liczbowa, nie
zbadany mechanizm). **Wniosek: po dużym `DELETE` nie trzeba ręcznie robić `UPDATE STATISTICS`
— o ile `AUTO_UPDATE_STATISTICS` jest włączone (domyślnie jest).**

`REORGANIZE` ani `REBUILD` **nie zmieniają statystyk**: `last_updated` bez zmian
(03:01:20), `modification_counter` bez zmian. Dowód na przypadku poniżej progu: po
`DELETE TOP (20000)` licznik = 20 000, tabela 880 000 wierszy, a statystyka dalej mówi
`rows = 900000`; po kolejnym `REBUILD` identycznie (`rows = 900000`, `zmian = 20000`).
Dopiero `UPDATE STATISTICS … WITH FULLSCAN` daje `rows = 880000`, `rows_sampled = 880000`,
licznik 0 (przy okazji zapełnia też statystykę `PK_Orders`, która była pusta od
utworzenia tabeli).

> ⚠️ **Czego nie pokazaliśmy:** realnego wpływu tej 2-procentowej nieaktualności
> statystyki na plan — przy 20 000/900 000 różnica jest pomijalna i nie robiliśmy dla niej
> pomiaru czasu/reads. Kolejność „REBUILD, potem UPDATE STATISTICS" ma sens, gdy po drodze
> kasujesz dużo mniej niż próg auto-update, a mimo to zależy Ci na świeżym histogramie.

---

## 🧾 Ściąga na dziś

| Pojęcie | Jedno zdanie |
|---|---|
| Dlaczego PSP nie ruszył w #3/#8 | `SkewnessThresholdNotMet` — dane za mało skośne (iloraz 1 900); compat 160 i opcja ON były OK |
| Jak to sprawdzić | XE `parameter_sensitive_plan_optimization_skipped_reason` (40 powodów w `psp_skipped_reason_enum`) |
| Próg skośności (empirycznie, nie z dokumentacji) | spełniony przy ilorazie 100 000, niespełniony przy 95 000 |
| Efekt, gdy PSP ruszy | mały tenant: 5 166 → **5** reads |
| Pułapka pomiaru | `INSERT … EXEC` ⇒ `UnsupportedStatementType` ⇒ fałszywy negatyw |
| Query Store hint przy PSP | przypięty do `query_id`; hint z rodzica dziedziczą warianty |
| Szkodliwy hint | `OPTIMIZE FOR UNKNOWN` na wariancie z gigantem: 5 161 → **582 215** reads |
| `RECOMPILE` na rodzicu | wyłącza PSP (`WithRecompileFlag`) |
| Nieobsługiwane w QS hints | `TABLE HINT`, `OPTIMIZE FOR (@p=…)` — błąd 12455 |
| `TOMBSTONE` po `REORGANIZE` | znikają same po ok. 3,5–4 min; `REBUILD` czyści od razu |
| Statystyki po dużym `DELETE` | auto-update przy następnym zapytaniu (300 000 zmian → `rows` 900 000) |
| Statystyki po `REBUILD` | **nietknięte** — `UPDATE STATISTICS` ręcznie, jeśli zależy Ci na świeżości |

**Pełny, uruchamialny kod + komendy:** [`code/README.md`](code/README.md).

**Co dalej:** PSP z więcej niż jednym predykatem (które z trzech?), `sp_query_store_set_hints`
z `USE HINT` na wariancie (pierwszeństwo nad rodzicem), mechanizm w tle czyszczący
`TOMBSTONE`, plan z `AUTO_UPDATE_STATISTICS OFF` i realny koszt nieaktualnych statystyk NCCI.

---

## ✅ Status weryfikacji

Kod uruchomiony realnie na `mcr.microsoft.com/mssql/server:2022-latest` (SQL Server 2022
RTM-CU27, 16.0.4295.3). Pełna sekwencja `01`→`19` przepuszczona **dwa razy od zera**:
pierwszy przebieg w kontenerze, w którym powstawały skrypty (z eksperymentami
diagnostycznymi), drugi — na nowym kontenerze, czystymi plikami. Kluczowe liczby
(5 166 vs 5, 582 215, rozkłady skośności, estymaty, stan statystyk) powtórzyły się
identycznie (z wyjątkiem estymaty 299 297 vs 299 321 po buildzie — drobna zmienność próbki
auto-statystyki i czasu `TOMBSTONE`).

Uczciwe uwagi:

1. `run-demo.sh` jako całość **nie został odpalony** (uruchomienie `.sh` odrzucone przez
   uprawnienia sandboksa — znany problem z poprzednich wydań); wszystkie kroki wykonano ręcznie
   przez `docker exec … sqlcmd`, dokładnie w kolejności ze skryptu. Skrypt jest więc
   **niezweryfikowany jako plik**.
2. **Wzór skośności i próg PSP** to hipoteza z danych (6 punktów pomiarowych), nie z
   dokumentacji. Nie sprawdzaliśmy wartości między 95 000 a 100 000 ani zależności od
   rozmiaru tabeli.
3. Zdarzenia XE w [`04`](code/04-psp-rozklady.sql) mają tę samą treść `sql_text` (cały batch),
   więc przypisanie do tabeli A/B/C wynika z kolejności zdarzeń i z zgodności `max_skewness`
   (100000/190000) z danymi — rozsądne, ale nie z etykiet.
4. Mechanizm i harmonogram usuwania `TOMBSTONE` w tle: tylko dwa pomiary czasu (granularność
   15 s), mechanizm niezbadany.
5. Hintu wariantu vs rodzica (pierwszeństwo), innych hintów QS niż `OPTIMIZE FOR UNKNOWN` /
   `RECOMPILE` i PSP z wieloma predykatami nie testowaliśmy.
6. Próg auto-update statystyk (`SQRT(1000·N)`) przyjęty z dokumentacji, niezmierzony.
7. Kontener (i jego anonimowe wolumeny) usunięty po testach; obraz pozostawiono.

---

<div align="center">

[← wróć do wydania #14 (wszystkie rubryki)](../README.md) · [spis wydań](../../README.md)

</div>
