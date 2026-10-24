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

## ✅ Weryfikacja — prawdziwe liczby (dopisane 2026-09-29)

Wydanie #1 pierwotnie nie miało realnie zmierzonych liczb (na maszynie brakowało
miejsca na dysku pod obraz SQL Server 2022). Pięć dni później, gdy dysk miał już
43 GB wolnego, przykład został odpalony naprawdę — na SQL Server 2022 w Dockerze,
ręcznie przez `docker exec ... sqlcmd` (identycznie jak sekwencja komend w
`run-demo.sh`). Wynik:

| Krok | Operator w planie | `logical reads` | Czas (CPU / elapsed) |
|---|---|---|---|
| **02** — `SELECT` bez indeksu | **Clustered Index Scan** (cała tabela) | **2495** | 49 ms / 48 ms |
| **04** — `SELECT` z indeksem | **Index Seek** + **Key Lookup** | **30** | 2 ms / 2 ms |

Dokładnie tak, jak przewidywała teoria: bez indeksu SQL Server musiał przejrzeć
całą tabelę (2495 stron po 8 KB), z indeksem — **83× mniej odczytów** (2495 → 30),
bo B-drzewo pozwoliło od razu "skoczyć" do 9 wierszy klienta `CustomerId = 1`
(`Index Seek`), a resztę kolumn dociągnąć pojedynczym `Clustered Index Seek
... LOOKUP` na każdy trafiony wiersz (`Key Lookup`).

Druga strona medalu — koszt zapisu (krok **05**, 20 000 nowych wierszy):

| Tabela | Czas INSERT (CPU / elapsed) |
|---|---|
| bez indeksu na `CustomerId` | 179 ms / 186 ms |
| z indeksem na `CustomerId` | 464 ms / 477 ms |

Ten sam batch wstawiania jest **2,6× wolniejszy**, gdy trzeba dodatkowo
zaktualizować B-drzewo indeksu przy każdym wierszu — dokładnie ten kompromis
"szybszy SELECT, wolniejszy INSERT" opisany w sekcji 1.

**Napotkany i naprawiony błąd:** `03-create-index.sql` nie miał na początku `USE
PrasowkaDemo;` — każde wywołanie `docker exec ... sqlcmd -i plik.sql` to osobna
sesja, więc kontekst bazy ustawiony w poprzednim pliku (`02-...`) się nie
przenosi. Bez tej poprawki `CREATE INDEX` kończył się błędem `Cannot find the
object "dbo.Orders"`. Plik w repo jest już poprawiony.

Indeks `IX_Orders_CustomerId` zajął **869 stron** (866 liść + 2 pośredni + 1
root = 3 poziomy B-drzewa), czyli ok. 6,77 MB dla 500 000 wierszy.

Kontener po weryfikacji usunięty (`docker rm -f`), zero śladów na dysku.

---

<div align="center">

[← wróć do wydania #1 (wszystkie rubryki)](../README.md) · [spis wydań](../../README.md)

</div>
