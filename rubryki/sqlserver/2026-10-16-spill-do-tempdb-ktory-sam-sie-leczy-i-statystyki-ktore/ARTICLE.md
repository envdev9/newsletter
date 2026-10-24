<div align="center">

# 📰 TECH PRASÓWKA
### Wydanie #23 — 16 października 2026

![SQL Server](https://img.shields.io/badge/SQL_Server-CC2927?style=for-the-badge&logo=microsoftsqlserver&logoColor=white)
![Poziom](https://img.shields.io/badge/poziom-zaawansowany-orange?style=for-the-badge)
![Zweryfikowane](https://img.shields.io/badge/kod-uruchomiony_na_SQL_Server_2022_CU27-brightgreen?style=for-the-badge)

## Spill do tempdb, który sam się leczy. I statystyki, które odświeżają się „po fakcie"
### Memory grant feedback kontra `AUTO_UPDATE_STATISTICS_ASYNC` — co naprawdę dzieje się z pierwszym zapytaniem

</div>

---

> _"Dosypałeś 600 tysięcy wierszy z nową wartością. Pierwsze zapytanie dostaje 1,4 MB pamięci na
> sortowanie, które potrzebuje 35 MB — i wylewa 4 000 stron do tempdb. Drugie zapytanie jest już
> w porządku. Nikt nic nie naprawiał."_

**🎣 Dlaczego to ważne:** w #16 pokazaliśmy, że nieaktualne statystyki dają zły plan, i
zostawiliśmy otwarte pytanie: czy dostaniemy **spill** (zbyt mały przydział pamięci) i co
zmienia `AUTO_UPDATE_STATISTICS_ASYNC`. Odpowiedzi są nieoczywiste: (1) spill da się
wywołać banalnie, (2) SQL Server 2022 **sam go leczy po jednym wykonaniu** — mechanizmem,
który nie ma nic wspólnego ze statystykami, więc łatwo go pomylić z ich „naprawą", (3) tryb
async oznacza, że **pierwsze zapytanie po zmianie danych zawsze jedzie na starej estymacie**,
a synchroniczny update płaci za świeżość w czasie *kompilacji*. Liczby poniżej są z realnego
uruchomienia.

Kod: [`code/`](code/), SQL Server 2022 RTM-CU27 (16.0.4295.3, Developer, Linux, Docker
`mcr.microsoft.com/mssql/server:2022-latest`, kontener z 2 CPU, compat 160).

---

## 1️⃣ Spill: co to jest i jak go wywołać

**Memory grant** to pamięć, którą silnik rezerwuje przed startem zapytania dla operatorów
sortujących i haszujących. Wielkość wynika z **estymaty liczby wierszy**. Jeśli estymata jest
za mała, a wierszy przyszło więcej, operator nie mieści się w przydziale i **przelewa
(spill) dane do tempdb** — czyli na dysk. Dla .NET-owca: to jak `List<T>` o pojemności
oszacowanej na 1 000 elementów, do którego ktoś wrzuca 600 000 — z tą różnicą, że tu
rezerwację robi się raz, z góry.

Tabela `dbo.Orders`: 1 000 000 wierszy (`Status` 0..3), statystyka kolumny `Status` powstaje
przy pierwszym zapytaniu. Potem **dosypujemy 600 000 wierszy ze `Status = 7`** — wartością,
której nie ma w histogramie. Procedura ([`01`](code/01-lab.sql)) sortuje te wiersze po tekście
(`ROW_NUMBER() OVER (ORDER BY Note)` i wybór wiersza 300 000):

| tryb statystyk | estymata `Status = 7` (faktycznie 600 000) | grant | użyty | spill (strony) |
|---|---:|---:|---:|---:|
| `AUTO_UPDATE_STATISTICS OFF`, wywołanie 1 | **1 264,91** | 1 440 KB | 1 440 KB | **3 980** |

Estymata 1 264,91 pochodzi z naszych danych; w #16 zauważyliśmy, że jest równa `SQRT(1 600 000)` —
tu też, ale mechanizmu nadal nie weryfikowaliśmy. Przydział 1,4 MB to niemal minimum.

---

## 2️⃣ Memory grant feedback: drugie wywołanie jest już zdrowe (bez ruszania statystyk)

W tym samym trybie `OFF` wywołujemy **tę samą procedurę** jeszcze raz. Statystyki są dalej
stare (estymata ta sama, `modification_counter = 600000`), a plan ten sam:

| tryb `OFF` | wywołanie | grant | użyty | spill (strony) | czas |
|---|---:|---:|---:|---:|---:|
| przed | 1 | 1 440 KB | 1 440 KB | **3 980** | 1 346 ms |
| przed | 2 (ten sam plan, `wykonan = 2`) | **62 832 KB** | 34 312 KB | **0** | 1 719 ms |

(w powtórce od zera: 3 980 → 0, grant 1 440 → 62 832 KB, czasy 1 301 / 1 634 ms.)

To **memory grant feedback** (MGF): silnik po wykonaniu zapamiętuje, że zapytanie wylewało
dane, i przy kolejnym użyciu *tego samego planu z cache* prosi o więcej pamięci. Od compat
150 działa również w trybie wierszowym (u nas plan jest wierszowy); w 2022 to
„percentile grant" i „persistence" (feedback zapisany w Query Store). Sprawdziliśmy, że w
bazie wszystkie cztery ustawienia `*_MEMORY_GRANT_FEEDBACK*` są `1`.

Dowód, że to MGF, a nie przypadek — kontrolowany eksperyment ([`03`](code/03-mgf.sql)), dwie
procedury z nowymi wartościami (`Status` 9 i 10, obie z nieaktualną statystyką), pięć
wywołań każda, `ROW_MODE_MEMORY_GRANT_FEEDBACK` raz `OFF`, raz `ON`:

| wywołanie | A: feedback **OFF** (spill / grant KB) | B: feedback **ON** (spill / grant KB) |
|---:|---|---|
| 1 | 4 250 / 1 504 | 4 275 / 1 504 |
| 2 | 4 250 / 1 504 | **0 / 61 600** |
| 3 | 4 250 / 1 504 | 0 / 61 600 |
| 4 | 4 242 / 1 504 | 0 / 61 600 |
| 5 | 4 246 / 1 504 | 0 / 61 600 |

Z wyłączonym feedbackiem spill powtarza się **w każdym wywołaniu**. Z włączonym znika od
drugiego. (Od zera drugi raz: te same wzorce, spille 4 211–4 251 vs 0.)

> ⚠️ **Uczciwa uwaga o czasie:** spill zniknął, ale **czas nie spadł** — w B wywołania
> 2–5 trwały ok. 1 730–2 000 ms vs ok. 1 470–1 600 ms w A. Na szybkim dysku kontenera
> 4 000 stron (ok. 32 MB) do tempdb kosztuje niewiele, a 60 MB grantu i sortowanie w pamięci
> wcale nie wyszło szybciej. To nie jest benchmark (2 CPU, jeden kontener). Wniosek: MGF
> chroni przed spillem, nie gwarantuje, że zapytanie przyspieszy. Nie mamy też pomiaru
> kosztu większego grantu dla współbieżnych zapytań — a to jest jego realny koszt.

> 💡 **Dla .NET-owca:** nie interpretuj poprawy „po drugim wywołaniu" jako dowodu, że
> statystyki są w porządku. W tym eksperymencie estymata nadal wynosiła 1 264,91 — zmienił się
> **tylko grant**. Zła estymata zostaje i dalej wpływa na wybór operatorów i DOP.

---

## 3️⃣ `AUTO_UPDATE_STATISTICS`: sync vs async — kto płaci za świeżość

Te same dane (1 mln + 600 000 wierszy ze `Status = 7`; po 600 000 modyfikacji próg
automatycznej aktualizacji jest przekroczony). Pomiar: **pierwsze** wywołanie po
dosypaniu, 10 s przerwy, **drugie** wywołanie:

| tryb | czas kompilacji w wywołaniu 1 | estymata w wywołaniu 1 | spill w wywołaniu 1 | estymata w wywołaniu 2 | spill w wywołaniu 2 |
|---|---:|---:|---:|---:|---:|
| `AUTO_UPDATE OFF` | 3 ms | 1 264,91 | **3 980** | 1 264,91 (stara) | 0 (MGF) |
| `AUTO_UPDATE ON`, sync | **460 ms** (396 ms w powtórce) | **604 027** | 0 | 604 027 | 0 |
| `AUTO_UPDATE ON`, **async** | 3 ms | **1 264,91** (stara!) | **3 964** | 604 027 | 0 |

- **Sync:** zapytanie, które wykryło nieaktualne statystyki, **czeka** w kompilacji na ich
  odświeżenie (tu ok. 0,4 s przy próbkowaniu 304 593 z 1 600 000 wierszy). Dostaje dobrą
  estymatę od razu, bez spilla. Koszt widać jako dłuższe „parse and compile time".
- **Async:** pierwsze zapytanie **nie czeka** i jedzie na starej estymacie (1 264,91, spill
  3 964 stron); statystyki aktualizuje wątek w tle, a następne wywołanie dostaje nowy plan
  (`wykonan = 1` w nowym wpisie plan cache, estymata 604 027, bez spilla). Po 10 s statystyka
  miała `rows = 1 600 000`, `modification_counter = 0`.
- Estymata po aktualizacji to 604 027, nie 600 000 — **sampling** (`rows_sampled = 304 593`),
  wyraźnie widać różnicę względem `FULLSCAN` z #16 (tam dokładnie 600 000).

> 💡 **Haczyk:** async nie jest „lepszy", jest *inny*. Wybierasz między: czekaniem
> pierwszego użytkownika (sync) a tym, że pierwszy użytkownik dostaje zły plan (async).
> Przy zapytaniach, które muszą mieć świetny plan od razu (raport o 9:00 po nocnym
> ładowaniu), async tego nie zagwarantuje. Przy OLTP z krótkimi zapytaniami często lepiej
> zapłacić ułamek sekundy kompilacji niż ryzykować złym planem. Sprawdziliśmy tylko jedno
> zapytanie na jednej tabeli — nie ekstrapoluj.

---

## 🧾 Ściąga na dziś

| Pojęcie | Jedno zdanie |
|---|---|
| Spill | zbyt mały grant → przelew do tempdb; u nas 3 980–4 275 stron na wywołanie |
| Przyczyna | estymata 1 264,91 zamiast 600 000 po dosypaniu nowej wartości |
| MGF (tryb wierszowy) | po spillu następne wykonanie tego samego planu dostaje większy grant (1,4 → 61–63 MB), spill 0 |
| MGF a statystyki | estymata w planie zostaje zła — feedback leczy objaw (grant), nie przyczynę |
| MGF a czas | spill zniknął, ale czasy nie spadły (1 730–2 000 vs 1 470–1 600 ms) |
| `AUTO_UPDATE` sync | pierwszy użytkownik czeka (kompilacja 460 ms), ale ma dobry plan |
| `AUTO_UPDATE` async | pierwszy użytkownik nie czeka i dostaje starą estymatę; drugi już nowy plan |

**Pełny, uruchamialny kod + komendy:** [`code/README.md`](code/README.md).

**Co dalej:** czy MGF działa też, gdy plan jest równoległy z wieloma operatorami
sortującymi; co robi feedback, gdy grant jest *za duży* (zmniejsza go — i czy oscyluje);
`MEMORY_GRANT_FEEDBACK_PERSISTENCE` po wyczyszczeniu cache; async update przy jednoczesnych
setkach zapytań; mechanizm czyszczenia `TOMBSTONE`.

---

## ✅ Status weryfikacji

**Zweryfikowane realnie:** skrypty `01` (we wszystkich trzech trybach) i `03` wykonane
ręcznie przez `docker exec … sqlcmd` na SQL Server 2022 RTM-CU27, każdy tryb z `01`
uruchomiony **dwa razy** na świeżo zbudowanej bazie, `03` także dwa razy — wzorce (spill,
grant, estymaty) identyczne, czasy z niewielkim rozrzutem (podane obok).

**Niezweryfikowane / uczciwe zastrzeżenia:**

1. `run-demo.sh` nie powstał — polecenia wykonywane ręcznie (Bash sandboksa blokuje `.sh`);
   w README pełna sekwencja komend do skopiowania.
2. Przyczyna zmiany grantu to wniosek z obserwacji (kontrola `ROW_MODE_MEMORY_GRANT_FEEDBACK`
   OFF/ON); nie zaglądaliśmy w wewnętrzne liczniki ani Extended Events MGF. Próba odczytu
   atrybutu `IsMemoryGrantFeedbackAdjusted` z planu z cache zwróciła `NULL` (usunięte ze skryptu).
3. Brak pomiaru wpływu większego grantu na współbieżność; brak testu feedbackiem „w dół"
   (grant za duży) i oscylacji.
4. Czasy z jednego, 2-rdzeniowego kontenera — rząd wielkości, nie benchmark. Tempdb na
   szybkim dysku nie pokazuje prawdziwego kosztu spilla.
5. Tryb async sprawdzony na jednym zapytaniu; nie testowano wielu równoległych sesji ani
   tego, co robi druga sesja w trakcie aktualizacji w tle.
6. Kontener usunięty (`docker rm -f -v`), `docker ps -a` zweryfikowane.

---

<div align="center">

[← wszystkie artykuły: 🗄️ SQL Server](../README.md) · [spis rubryk](../../../README.md)

</div>
