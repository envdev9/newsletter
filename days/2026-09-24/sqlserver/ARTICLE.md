<div align="center">

# 📰 TECH PRASÓWKA
### Wydanie #1 — 24 września 2026

![SQL Server](https://img.shields.io/badge/SQL_Server-CC2927?style=for-the-badge&logo=microsoftsqlserver&logoColor=white)

## Indeks to nie magia — to B-drzewo, które oszczędza SQL Serwerowi czytanie całej tabeli

</div>

---

> _"Bez indeksu SQL Server nie ma jak 'zgadnąć', gdzie leżą Twoje wiersze — musi
> przeczytać każdy jeden, żeby sprawdzić, czy pasuje. Indeks to jedyny sposób, żeby
> zamienić 'przeczytaj wszystko' na 'skocz od razu we właściwe miejsce'."_

Pierwsze wydanie tej rubryki — więc zaczynamy od absolutnych podstaw, ale od razu w
formie, którą można samemu uruchomić i zobaczyć na własne oczy: tabela z 500 000
wierszy, to samo zapytanie odpalone dwa razy — raz bez indeksu, raz z indeksem — i
porównanie liczby odczytów stron (`logical reads`) oraz planu wykonania między nimi.

---

## 1️⃣ Czym w ogóle jest indeks

### Problem, który rozwiązuje

Tabela `dbo.Orders` z 500 000 wierszy, bez żadnego indeksu poza kluczem głównym.
Szukasz zamówień konkretnego klienta: `WHERE CustomerId = 1`. SQL Server nie ma
żadnej mapy mówiącej "wiersze klienta 1 leżą tutaj" — jedyne, co może zrobić, to
przejść **wiersz po wierszu przez całą tabelę** i sprawdzić każdy. To się nazywa
**table scan** (a dokładniej, skoro tabela ma klucz klastrowany:
**Clustered Index Scan** — czytaj dalej, za chwilę to się wyjaśni). Im większa
tabela, tym drożej to kosztuje — liniowo.

### Jak działa indeks (B-drzewo)

Indeks nieklastrowany (`NONCLUSTERED INDEX`) to **osobna struktura danych** trzymana
obok tabeli — **B-drzewo** (B-tree). W dużym uproszczeniu:

- Węzły **liścia** B-drzewa trzymają posortowane wartości indeksowanej kolumny
  (tu: `CustomerId`) razem z **wskaźnikiem do właściwego wiersza** (przy tabeli
  z indeksem klastrowanym, jak nasza `Orders`, tym wskaźnikiem jest klucz
  klastrowany — `OrderId`).
- Węzły **wyższych poziomów** to skrócona "mapa drogowa" — dzięki niej SQL Server
  nie przegląda liści po kolei, tylko **schodzi w dół drzewa**, porównując wartość
  szukaną z wartościami w węzłach, aż trafi we właściwy liść.
- Efekt: znalezienie konkretnej wartości to nie N porównań (rozmiar tabeli), tylko
  ok. `log(N)` porównań — przy 500 000 wierszy to kilkanaście "skoków", nie pół
  miliona sprawdzeń.

To dokładnie odwzorowuje to, co widać w planie wykonania: bez indeksu SQL Server
robi **Clustered Index Scan** (skanuje całą tabelę), z indeksem robi
**Index Seek** na `IX_Orders_CustomerId` (skacze od razu do właściwych wierszy w
B-drzewie) + **Key Lookup** z powrotem do tabeli głównej — bo indeks nieklastrowany
trzyma tylko `CustomerId` i wskaźnik, nie resztę kolumn (`OrderDate`, `Amount`,
`Status`), więc po znalezieniu wskaźnika trzeba jeszcze "doskoczyć" po nie do
tabeli.

### Dlaczego to przyspiesza SELECT, a spowalnia INSERT/UPDATE

Indeks to **dodatkowa, utrzymywana na bieżąco kopia** części danych, posortowana
inaczej niż tabela główna. To ma cenę w obie strony:

- **SELECT szybszy** — bo zamiast czytać całą tabelę, SQL Server czyta tylko
  fragment B-drzewa + ewentualne trafienia (`Key Lookup`).
- **INSERT/UPDATE/DELETE wolniejszy** — bo każda zmiana wiersza, która dotyka
  zaindeksowanej kolumny, musi zaktualizować **i tabelę, i B-drzewo indeksu**.
  Czasem nowa wartość nie mieści się tam, gdzie "powinna" trafić w sortowaniu
  strony indeksu — wtedy SQL Server robi **page split** (dzieli stronę indeksu na
  dwie), co jest jeszcze droższe niż zwykły zapis.

Stąd klasyczna zasada: indeksuj kolumny, po których **często filtrujesz/łączysz**
(`WHERE`, `JOIN`, `ORDER BY`), ale nie dokładaj indeksów "na zapas" do tabel z
bardzo dużym ruchem zapisowym — każdy dodatkowy indeks to dodatkowy koszt przy
każdym `INSERT`.

---

## 2️⃣ Namacalny przykład — ten sam SELECT, dwa plany wykonania

Kod w [`code/`](code/) robi dokładnie to, co powyżej opisane teoretycznie, krok po
kroku, na prawdziwej instancji SQL Server 2022 (w kontenerze Dockera):

1. **`01-create-table-and-data.sql`** — tworzy bazę `PrasowkaDemo` i tabelę
   `dbo.Orders` (500 000 wierszy, generowanych bez pętli — klasycznym wzorcem
   T-SQL "krzyżowania" małej tabeli samą ze sobą, żeby dostać dowolną liczbę
   wierszy bez tabeli pomocniczej). Na tym etapie `CustomerId` **nie jest
   niczym zaindeksowany**.
2. **`02-query-no-index.sql`** — `SELECT ... WHERE CustomerId = 1`, z
   `SET STATISTICS IO/TIME/PROFILE ON` — realne liczby odczytanych stron
   (`logical reads`) i tekstowy plan wykonania. Oczekiwany operator:
   **Clustered Index Scan**.
3. **`03-create-index.sql`** — `CREATE NONCLUSTERED INDEX IX_Orders_CustomerId
   ON dbo.Orders (CustomerId)`.
4. **`04-query-with-index.sql`** — dokładnie to samo zapytanie co w kroku 2.
   Oczekiwany operator: **Index Seek** + **Key Lookup**, i wyraźnie mniej
   `logical reads`.
5. **`05-insert-cost-comparison.sql`** — druga strona medalu: ten sam batch
   20 000 nowych wierszy wstawiany do dwóch identycznych tabel, jednej bez
   indeksu na `CustomerId` i jednej z indeksem — z `SET STATISTICS TIME ON`,
   żeby zobaczyć koszt utrzymania indeksu przy zapisie.

**Pełny, uruchamialny kod + dokładne komendy:** [`code/README.md`](code/README.md).

---

## ⚠️ Ograniczenie środowiska przy weryfikacji tego wydania

Zgodnie z zasadą tej prasówki "zero fikcji" — uczciwie: **nie udało mi się
realnie uruchomić powyższych skryptów w tym środowisku** i wkleić prawdziwych
liczb `logical reads`/czasu, mimo próby. Powód jest czysto infrastrukturalny, nie
merytoryczny:

Maszyna, na której działa ten agent, ma dysk **40 GB, w praktyce pełny** (w trakcie
tej sesji spadło z 845 MB do 231 MB wolnego miejsca — inne procesy na tej samej
współdzielonej maszynie zużywają go równolegle). Obraz
`mcr.microsoft.com/mssql/server:2022-latest` (kilka GB po rozpakowaniu) nie mieści
się. Próba pobrania (`docker pull mcr.microsoft.com/mssql/server:2022-latest`)
zakończyła się realnym błędem:

```
failed to extract layer (application/vnd.docker.image.rootfs.diff.tar.gzip
sha256:cb5e374be662a562b8271158639e918b9c634aa4dfdc8b3aa31ccfc99cf8c077) to
overlayfs as "extract-903847685-KScw ...": mount callback failed on
/var/lib/containerd/tmpmounts/containerd-mount2254423097: write
/var/lib/containerd/tmpmounts/containerd-mount2254423097/usr/lib/locale/C.utf8/LC_CTYPE:
no space left on device
```

Sprzątanie nieużywanych obrazów Dockera (`docker system prune`) należących do
innych, równolegle działających projektów na tej maszynie zostało celowo
zablokowane (klasyfikator uprawnień) — słusznie, bo mogłoby to zepsuć pracę innych
zadań na tej samej maszynie. Lokalnego `sqlcmd` też nie ma na hoście.

**Co to oznacza dla czytelnika:** skrypty `.sql` w `code/` są kompletne, spójne
logicznie i gotowe do odpalenia (składnia i wzorce sprawdzone ręcznie — m.in.
generator wierszy przez `ROW_NUMBER()`/`CROSS JOIN`, `SET STATISTICS
IO/TIME/PROFILE`, `sys.dm_db_index_physical_stats`, wszystko to standardowe,
udokumentowane konstrukcje T-SQL), ale **nie mam realnych zmierzonych liczb do
pokazania** — i zgodnie z zasadą "zero fikcji" tej prasówki, żadnych nie zmyślam.
Opis "co powinieneś zobaczyć" w sekcji 1 i 2 powyżej opiera się na udokumentowanym
mechanizmie działania SQL Server (Clustered Index Scan → Index Seek + Key Lookup),
nie na wymyślonym pomiarze. Jeśli masz Dockera z wolnym miejscem na dysku — `cd
code && ./run-demo.sh` odpali cały przykład od zera i pokaże prawdziwe liczby.

---

<div align="center">

[← wróć do wydania #1 (wszystkie rubryki)](../README.md) · [spis wydań](../../README.md)

</div>
