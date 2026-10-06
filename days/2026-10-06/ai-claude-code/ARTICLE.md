<div align="center">

# 📰 TECH PRASÓWKA
### Wydanie #13 — 6 października 2026

![AI](https://img.shields.io/badge/AI_%2F_Claude_Code-D97757?style=for-the-badge&logo=anthropic&logoColor=white)
![Poziom](https://img.shields.io/badge/poziom-zaawansowany-red?style=for-the-badge)
![SQL Server](https://img.shields.io/badge/SQL_Server_2022-CC2927?style=for-the-badge&logo=microsoftsqlserver&logoColor=white)
![Testy](https://img.shields.io/badge/run__tests.py-15%2F15%20na%20realnych%20planach-brightgreen?style=for-the-badge)

## Cztery reguły skanera, które czekały na prawdziwy plan — i dwa błędy, które się przy okazji ujawniły

</div>

---

> _"Test, który przechodzi, mówi tylko tyle, że oczekiwanie zgadza się z wynikiem. Dopiero
> realne dane mówią, czy to oczekiwanie było dobre. W #10 test `keylookup.xml` przechodził
> od trzech dni — i pilnował fałszywego alarmu."_

W wydaniu #10 skaner planów `scan_plan.py` (skill `sql-plan-review`) przeszedł egzamin na
prawdziwym SQL Serverze, ale cztery reguły zostały "na później": `SPILL`, `MEMORY-GRANT`,
`NO-STATISTICS`, `NO-JOIN-PREDICATE`. Dziś je domykamy — na planach nagranych z SQL Server
2022 w **własnym, jednorazowym kontenerze** (żaden działający kontener w środowisku nie miał
SQL Servera, więc postawiłem swój, bez publikowania portów, i usunąłem go po teście).

---

## 1️⃣ 🎯 Dlaczego to ważne: plan, który "działa", a kosztuje

Zapytanie zwraca poprawny wynik, testy zielone, a mimo to: sort wylewa 500 000 wierszy do
`tempdb`, inne zapytanie rezerwuje 268 MB RAM-u, żeby użyć 5 MB, trzecie robi iloczyn
kartezjański po zapomnianym `ON`. Żadnego wyjątku. Jedyny ślad to ostrzeżenia w planie —
a plan czyta się rzadko. Skill, który robi to deterministycznie przy każdym code review,
ma sens tylko wtedy, gdy **wiemy, kiedy ostrzeżenia się pojawiają, a kiedy ich nie ma**.
Dziś pierwsza połowa tego pytania jest zmierzona, druga zaskoczyła.

## 2️⃣ 🔬 Wyniki: cztery reguły na żywo

| Reguła | Jak wywołana (`sql/`) | Co pokazał realny plan |
|---|---|---|
| `SPILL` | zmienna tabelowa + `QUERY_OPTIMIZER_COMPATIBILITY_LEVEL_140`, 500 000 wierszy, `ROW_NUMBER() OVER (ORDER BY ...)` | estymata 1 wiersz, rzeczywiście 500 000; `SpillLevel="2"`, **7841 stron** zapisanych do `tempdb`; grant sortu 1024 KB |
| `MEMORY-GRANT` | kolumna `varchar(4000)` z krótkimi wartościami, 100 000 wierszy | przyznano **268 152 KB**, użyto **5 400 KB** (x50) |
| `NO-JOIN-PREDICATE` | `FROM Tiny a, Tiny b` + `MAX(a.Label + b.Label)` | `<Warnings NoJoinPredicate="1">` na `Nested Loops`, 90 000 wierszy z 300 x 300 |
| `NO-STATISTICS` | baza z `AUTO_CREATE_STATISTICS OFF`, `GROUP BY` / `ORDER BY` / klucz joina po kolumnie bez statystyk | `<ColumnsWithNoStatistics>` z nazwą kolumny — **3 z 3 wariantów** |

Wszystkie cztery warunki wykrywania (nazwy elementów i atrybutów zapisane "z pamięci" w #4)
okazały się trafne — ta sama historia co w #10. Ale dwa realne plany pokazały, że **reszta
logiki wokół nich miała błędy**.

```
$ python3 run_tests.py
...
OK    spill.xml                      oczekiwano: ESTIMATE-SKEW, SCAN, SPILL                 otrzymano: ESTIMATE-SKEW, SCAN, SPILL
OK    memory_grant.xml               oczekiwano: MEMORY-GRANT, SCAN                         otrzymano: MEMORY-GRANT, SCAN
OK    no_join_predicate.xml          oczekiwano: NO-JOIN-PREDICATE, SCAN                    otrzymano: NO-JOIN-PREDICATE, SCAN
...
WYNIK: 15/15 sprawdzen zgodnych (realne plany z SQL Server 2022, Docker)
```

---

## 3️⃣ 🐛 Błąd #1: ten sam spill zgłoszony dwa razy

Silnik zapisuje spill w planie **dwukrotnie**: jako `<SpillToTempDb SpillLevel="2">` oraz
jako `<SortSpillDetails GrantedMemoryKb="1024" UsedMemoryKb="1024" WritesToTempDb="7841"
ReadsFromTempDb="7841">`. Skaner z #4 traktował je jak dwa niezależne zdarzenia i drukował
dwa `WARN SPILL` na jeden operator. Fixtury pisane ręcznie zawierały tylko jedną z form,
więc to się nie ujawniło. Teraz jest jedna pozycja na operator, a bonusem jest informacja,
której wcześniej nie było — ile stron poszło do `tempdb`:

```
WARN | SPILL | NodeId=3 Sort: spill do tempdb (poziom 2, SortSpillDetails, 7841 stron zapisanych do tempdb) - ...
```

Test pilnuje tego liczbowo (`spill.xml` → dokładnie 1 wpis `SPILL`).

## 4️⃣ 🐛 Błąd #2: `ESTIMATE-SKEW` porównywał jabłka z sumą jabłek

To ciekawsze, bo dotyczy testu z poprzedniego wydania. `EstimateRows` w planie to estymata
**na jedno wykonanie** operatora, a `ActualRows` w `RunTimeCountersPerThread` to **suma po
wszystkich wykonaniach** (`ActualExecutions`). Po wewnętrznej stronie `Nested Loops` operator
wykonuje się wiele razy. Realny plan z #10: Key Lookup z `EstimateRows="1"`,
`ActualExecutions="10"`, `ActualRows="10"` — czyli idealna estymata (1 wiersz na wykonanie),
a skaner widział "estymowano 1, rzeczywiście 10, rozjazd x10" i alarmował. Podobnie `Table
Spool` w cross joinie: "estymowano 300, rzeczywiście 90 000" przy 300 wykonaniach po 300
wierszy. Poprawka to jedna linijka logiki (`actual / executions`), a skutek: oczekiwanie
w `run_tests.py` dla `keylookup.xml` zmieniło się z `{KEY-LOOKUP, ESTIMATE-SKEW}` na samo
`{KEY-LOOKUP}`. Test z #10 przechodził, bo pilnował błędu.

> 💡 **Wniosek ogólny:** zielony test na danych nagranych "jak jest" utrwala też błędy
> narzędzia. Realny plan to dopiero połowa weryfikacji — drugą połową jest zadanie sobie
> pytania, czy każdy alarm w wyniku jest *prawdziwy*.

---

## 5️⃣ 🪤 Dwie ślepe plamki silnika (nie skanera)

Tak jak w #10 `TRIVIAL` ukrywał `MISSING-INDEX`, tak dziś znalazły się dwie kolejne
sytuacje, w których **brak ostrzeżenia nie znaczy "wszystko w porządku"**.

**`NO-STATISTICS` a plan `TRIVIAL`.** `SELECT COUNT(*) FROM Plain WHERE Category = 7` na
kolumnie bez statystyk (auto-create wyłączone) dał plan `TRIVIAL`: estymata 316.228
(= pierwiastek z 100 000, heurystyka "nic nie wiem") przy rzeczywistych 2 000 — i **zero**
ostrzeżeń. Dopiero `GROUP BY`, `ORDER BY` i klucz joina (plany `FULL`) niosą
`ColumnsWithNoStatistics`. Co zmierzyłem dodatkowo: nawet plan `FULL` z samym
`WHERE Category = 7` w joinie z drugą tabelą **nie** miał tego ostrzeżenia (próbka
`no_statistics.xml`) — mechanizmu wewnętrznego nie znam, tylko wynik.

**`NO-JOIN-PREDICATE` a `COUNT(*)`.** Pierwsza wersja zapytania to `SELECT COUNT(*) FROM
Tiny a, Tiny b` — bez ostrzeżenia, bo optymalizator spycha agregat pod join i po stronie
wewnętrznej zostaje jeden wiersz. Ostrzeżenie pojawiło się dopiero dla `MAX(a.Label +
b.Label)`, agregatu zależnego od obu stron. Praktyczny wniosek dla reviewera: brak
`NoJoinPredicate` przy `COUNT(*)` niczego nie dowodzi — tekstowy skaner `scan_sql.py`
(wykrywanie `FROM a, b` w kodzie) uzupełnia tu skaner planów, a nie jest jego duplikatem.

Obie plamki mają swoje próbki w `samples/` i wpisy w `run_tests.py` jako udokumentowane
zachowanie ("oczekujemy ciszy").

## 6️⃣ 🧭 Pułapka do pamiętania: `GENERATE_SERIES` i hint 140

Dwa triki, które ułatwiły całe demo, warto znać:

- `GENERATE_SERIES(1, 500000)` (SQL Server 2022, compat 160) generuje dane bez pętli.
- Zmienna tabelowa dostaje estymatę 1 wiersza tylko bez *deferred compilation*. W compat
  160 SQL Server odracza kompilację i widzi prawdziwą liczbę wierszy, więc spillu by nie
  było. `OPTION (USE HINT('QUERY_OPTIMIZER_COMPATIBILITY_LEVEL_140'))` przywraca stare
  zachowanie — to jednocześnie realny sposób, w jaki spill pojawia się na produkcji po
  migracji ze starszego poziomu kompatybilności w drugą stronę.

---

## 📎 Co zweryfikowano, a czego nie

| ✅ Uruchomione naprawdę | ⚠️ Niezweryfikowane |
|---|---|
| SQL Server 2022 RTM-CU27 (16.0.4295.3) Developer w **własnym** kontenerze `prasowka-ai-mssql-1006`, baza `PrasowkaAiSpill1006`; plany z `SET STATISTICS XML ON` | Spill typu **Hash** (`HashSpillDetails`) — kod go obsługuje, ale realnego planu nie nagrano; tylko Sort |
| `run_tests.py` **15/15**: 14 realnych planów (5 z #10 + 9 nowych) + 2 asercje licznościowe | Mechanizm, dla którego `WHERE Category = 7` w joinie nie daje `ColumnsWithNoStatistics`, a `GROUP BY`/`ORDER BY`/klucz joina dają |
| `SPILL`, `MEMORY-GRANT`, `NO-STATISTICS`, `NO-JOIN-PREDICATE` — nazwy atrybutów potwierdzone w realnym XML | Progi (`g/u >= 10`, `SKEW_FACTOR = 10`) — arbitralne, sprawdzone na jednym przypadku |
| Dwa błędy skanera znalezione na realnych planach i naprawione (podwójny SPILL, fałszywy ESTIMATE-SKEW) | Inne wersje/edycje SQL Server; auto-aktywacja skilla i działanie w żywej sesji `claude` |
| Sprzątanie: baza usunięta (`COUNT = 0`), kontener usunięty (`docker ps -a` pokazuje tylko wcześniej istniejące) | Oczekiwane zestawy w `run_tests.py` ustalono po obejrzeniu wyników — to test regresji, nie test "w ciemno" |

Środowisko: Docker, obraz `mcr.microsoft.com/mssql/server:2022-latest` (już lokalnie
obecny), Python 3.10 (tylko stdlib). Nie dotknięto cudzych kontenerów, obrazów ani baz.
Następny krok w rubryce: realny plan z **Hash Match spill**, albo skill do code-review
kodu C# dostępu do danych (EF Core: `ToList()` przed `Where`, N+1) z tym samym podejściem
"deterministyczny skaner + realne dane".

---

<div align="center">

[← wróć do wydania #13 (wszystkie rubryki)](../README.md) · [spis wydań](../../README.md)

</div>
