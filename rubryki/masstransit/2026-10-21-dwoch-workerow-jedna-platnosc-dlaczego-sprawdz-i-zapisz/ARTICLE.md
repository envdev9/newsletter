<div align="center">

# 📰 TECH PRASÓWKA
### Wydanie #28 — 21 października 2026

![MassTransit](https://img.shields.io/badge/MassTransit-FF6600?style=for-the-badge)
![Poziom](https://img.shields.io/badge/poziom-zaawansowany-red?style=for-the-badge)
![Status](https://img.shields.io/badge/uruchomienie-ZWERYFIKOWANE_(z_haczykiem)-orange?style=for-the-badge)

## 📨 Dwóch workerów, jedna płatność: dlaczego „sprawdź i zapisz” zawsze zaksięguje dwa razy

</div>

---

> **Uczciwie na wstępie.** Plan z poprzedniego wydania zakładał własny obraz RabbitMQ z wtyczką
> `delayed-message` i pomiar `UseDelayedRedelivery`. Do pobrania wtyczki potrzebny jest dostęp do sieci
> z poziomu powłoki, a środowisko go odrzuca (`curl` zablokowany przez uprawnienia; nie obchodziłem tego). Ten
> punkt **zostaje otwarty**. Zamiast niego wziąłem kolejny z listy: **atomowy klucz idempotentności przy 2
> workerach**. Wszystko poniżej: MassTransit + MassTransit.RabbitMQ 8.5.10, RabbitMQ `4.3-management` (Docker),
> .NET SDK 10.0.400, `dotnet build` 0 błędów (2 ostrzeżenia NU1903 z SQLite - patrz na końcu).

## 🎯 Dlaczego to ważne

RabbitMQ (jak większość brokerów) gwarantuje dostarczenie **co najmniej raz**. Producent po timeoucie
publikuje drugi raz, retry dubluje wiadomość - i ta sama płatność trafia do kolejki dwa razy. Standardowa
rada: „zapisz klucz przetworzonej wiadomości i sprawdzaj go na wejściu”. Problem: **ta rada, napisana
naturalnie, zawodzi dokładnie wtedy, gdy masz więcej niż jednego workera** - a po to jest kolejka, żeby
workerów było wielu. Kod przechodzi wszystkie testy na jednym procesie, a na produkcji księguje podwójnie.

## 🧩 1. Zestaw doświadczalny

Dwa **osobne procesy** (`worker A`, `worker B`) słuchają jednej kolejki `idem-pay` (`PrefetchCount=1`),
RabbitMQ rozdziela wiadomości między nich. Producent publikuje 5 płatności, **każdą dwa razy** (ten sam
`PaymentId`, dwa różne `MessageId` - jak retry po timeoucie). „Skutek uboczny” (np. wywołanie bramki
płatniczej) trwa 300 ms i jest zapisywany w tabeli `effects`. Wspólny stan: plik SQLite. Dwie strategie:

| Strategia | Co robi konsument |
|---|---|
| `naive` | `SELECT` czy klucz był -> jeśli nie: efekt (300 ms) -> `INSERT OR IGNORE` klucza |
| `atomic` | `INSERT OR IGNORE` klucza **najpierw**; efekt tylko gdy wstawiono 1 wiersz |

## 🪤 2. Wynik: `naive` - 5 płatności, 10 efektów

```
[A] start strategy=naive pracuje 25s
00:32:17.587 [A] pay-1 EFEKT (naive)
00:32:18.043 [A] pay-2 EFEKT (naive)
...
[B] start strategy=naive pracuje 25s
00:32:17.728 [B] pay-1 EFEKT (naive)
00:32:18.135 [B] pay-2 EFEKT (naive)
...
pay-1: efektow=2 (A,B)  <-- DUPLIKAT
pay-2: efektow=2 (A,B)  <-- DUPLIKAT
pay-3: efektow=2 (A,B)  <-- DUPLIKAT
pay-4: efektow=2 (A,B)  <-- DUPLIKAT
pay-5: efektow=2 (A,B)  <-- DUPLIKAT
razem efektow=10, platnosci z duplikatem=5
```

(Output skrócony; w przebiegu `naive` linia startowa miała jeszcze zbędny dopisek, usunięty potem z kodu.)
Oba duplikaty `pay-1` trafiły do różnych workerów, a ich efekty zakończyły się w odstępie **141 ms** - krócej
niż 300 ms trwania efektu, więc ich okna się nakładały. Worker B zrobił `SELECT`, zanim A zdążył zapisać klucz
(to wniosek z nakładania się okien, nie z osobnego pomiaru momentu `SELECT`). Co ważne: tabela `processed` ma klucz główny i
`INSERT OR IGNORE` na końcu go „obronił” - w bazie klucz jest tylko raz, **a pieniądze już poszły dwa
razy**. Unikalny indeks wstawiony *po* skutku nic nie chroni. W żadnym z 5 przypadków nie zadziałał
`SKIP` - sprawdzenie na wejściu ani razu nie pomogło.

## ✅ 3. Poprawka: `atomic` - 5 płatności, 5 efektów

```
[A] start strategy=atomic pracuje 20s
00:32:56.887 [A] pay-1 SKIP (klucz zajety)
00:32:57.059 [A] pay-2 EFEKT (atomic)
00:32:57.394 [A] pay-3 SKIP (klucz zajety)
00:32:57.397 [A] pay-4 EFEKT (atomic)
00:32:57.717 [A] pay-5 SKIP (klucz zajety)
[B] start strategy=atomic pracuje 20s
00:32:56.741 [B] pay-1 EFEKT (atomic)
00:32:57.226 [B] pay-2 SKIP (klucz zajety)
...
pay-1: efektow=1 (B)
pay-2: efektow=1 (A)
pay-3: efektow=1 (B)
pay-4: efektow=1 (A)
pay-5: efektow=1 (B)
razem efektow=5, platnosci z duplikatem=0
```

Zmiana to jedna linijka logiki: **sprawdzenie i zajęcie klucza to jedna operacja bazy**
(`INSERT OR IGNORE`, wynik = liczba wstawionych wierszy). Baza serializuje dwa jednoczesne `INSERT`-y z tym
samym kluczem - jeden wygrywa, drugi dostaje 0. Przy PostgreSQL/SQL Server odpowiednikiem jest
`INSERT ... ON CONFLICT DO NOTHING` / złapanie naruszenia unikalnego klucza. Reguła ogólna:
**„czy już było?” nie może być osobnym zapytaniem przed pracą.**

## 🧯 4. Czego ta poprawka NIE rozwiązuje (nie zmierzone)

- **Awaria po zajęciu klucza, przed skutkiem.** W `atomic` klucz jest zajęty *przed* efektem, więc jeśli proces
  padnie w środku, broker dostarczy wiadomość ponownie, a ona dostanie `SKIP` - skutek **nigdy** się nie wykona
  (semantyka at-most-once). Naprawa to stan klucza (`started` -> `done`) z limitem czasu - **nie zaimplementowałem
  i nie testowałem**. Courier z #19/#20 pokazał odwrotny kierunek (podwójny skutek po awarii); tu mamy ryzyko
  zgubienia. Idempotentność ze 100% gwarancją wymaga idempotentnego skutku po stronie odbiorcy (np. klucz w
  wywołaniu bramki).
- Klucz jest z danych biznesowych (`PaymentId`), nie z `MessageId` - bo `MessageId` dubletu jest inny.
- Test zrobiony dla 5 płatności, raz na strategię; wyścig jest deterministyczny przy tym odstępie, ale to nie statystyka.
- MassTransit ma własne mechanizmy (`UseMessageRetry` + outbox z bazą), których w tym wydaniu **nie** użyłem.

## ✅ Checklista

- Test idempotentności zawsze na **dwóch procesach**, nie dwóch wywołaniach w jednym teście.
- Klucz z biznesu (`PaymentId`), nie `MessageId`.
- Zajmij klucz atomowo (jedno `INSERT` + sprawdź liczbę wierszy / złap naruszenie unikalności) **przed** skutkiem.
- Zaplanuj, co się stanie z kluczem po awarii w środku (`started`/`done`).

## 🚧 Czego NIE zweryfikowałem

- **`UseDelayedRedelivery` z wtyczką** - pobranie wtyczki zablokowane, punkt nadal otwarty.
- Awarię po zajęciu klucza (powyżej), więcej niż 2 workery, SQL Server/PostgreSQL zamiast SQLite
  (SQLite blokuje cały plik przy zapisie - serializacja jest tam silniejsza niż w serwerowych bazach), `dotnet test`.
- Ostrzeżenie NU1903 (`SQLitePCLRaw.lib.e_sqlite3` 2.1.11, znana podatność) - tylko do demo, nie do produkcji.

## ▶️ Następny krok

Kod: [`code/README.md`](code/README.md). Następny poziom: stan klucza `started`/`done` z wygasaniem (odzysk po
awarii), wtyczka delayed-message w obrazie (gdy da się ją dostarczyć), `UseMessageRetry` + Courier,
`ReviseItinerary`, saga na RabbitMQ.

---

<div align="center">

[← wszystkie artykuły: 📨 Messaging .NET z MassTransit](../README.md) · [spis rubryk](../../../README.md)

</div>
