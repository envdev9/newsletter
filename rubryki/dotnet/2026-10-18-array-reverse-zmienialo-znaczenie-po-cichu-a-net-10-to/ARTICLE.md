<div align="center">

# 📰 TECH PRASÓWKA
### Wydanie #25 — 18 października 2026

![.NET](https://img.shields.io/badge/.NET-10-512BD4?style=for-the-badge&logo=dotnet&logoColor=white)
![BCL](https://img.shields.io/badge/BCL-Enumerable.Reverse(T%5B%5D)%20%2B%20HttpMethod.Query-blue?style=for-the-badge)

## `array.Reverse()` zmieniało znaczenie po cichu — a .NET 10 to naprawia. Plus: HTTP `QUERY` w `HttpClient`

</div>

---

> _"Ten sam zapis, `a.Reverse();`, w trzech konfiguracjach daje: nic, odwrócenie w miejscu i znowu nic."_
> — wynik naszego eksperymentu poniżej. Żadna z tych zmian nie wywołała ostrzeżenia kompilatora.

Z listy „zostało z diffu" został tylko `CompositeMLDsa` — a ten byłby znowu „tylko API" (OpenSSL 3.0.2 na tej
maszynie nie wspiera nawet `MLDsa`). Zamiast tego **powtórzyliśmy diff refleksyjny** (runtime 9.0.18 vs 10.0.11,
tym razem po wielu zestawach naraz: CoreLib, Linq, Http, Process, Collections...) i znaleźliśmy dwie rzeczy,
których jeszcze nie było: **`Enumerable.Reverse(TSource[])`** i **`HttpMethod.Query`**. Obie w pełni
zweryfikowane `dotnet run`. SDK .NET 11 nadal niedostępne (`dotnet --list-sdks`: 8.0.422, 8.0.425, 9.0.316,
10.0.400). Kod w [`code/`](code/).

| # | Funkcja | Namespace | Status |
|---|---------|-----------|--------|
| 1️⃣ | `Enumerable.Reverse<TSource>(TSource[])` — łata pułapkę C# 14 first-class Span | `System.Linq` | ✅ `dotnet run` na net9.0 i net10.0 |
| 2️⃣ | `HttpMethod.Query` — metoda HTTP `QUERY` (GET z ciałem) | `System.Net.Http` | ✅ `dotnet run` (serwer `HttpListener` na loopbacku) |

---

## 1️⃣ `Enumerable.Reverse(TSource[])` — cichy breaking change i jego łata

### 😤 Problem
W wydaniu #4 omówiliśmy *first-class Span* z C# 14: tablica konwersuje się niejawnie na `Span<T>`, a metody
rozszerzające na spanach działają na tablicach. Ukryty skutek: w `MemoryExtensions` istnieje
`Reverse<T>(this Span<T>)` — **odwracanie w miejscu, zwraca `void`**. Przez lata `array.Reverse()` znaczyło
LINQ (`IEnumerable<T>`, leniwe, tablica nietknięta). Po przejściu na C# 14 ta sama linijka zaczyna wiązać się do
wersji spanowej — i **mutuje Twoją tablicę**.

### ✨ Co zrobiło .NET 10
Dodało przeciążenie `Enumerable.Reverse<TSource>(TSource[] source)`. Jest dokładniejsze (tablica = tablica, bez
konwersji), więc wygrywa rozstrzyganie przeciążeń i **przywraca stare znaczenie LINQ**.

### 🔬 Dowód: diff refleksyjny (`reflect-diff`, `dotnet run -f net9.0` / `-f net10.0`)
```
Runtime: .NET 9.0.18                       Runtime: .NET 10.0.11
IEnumerable`1 Reverse(IEnumerable`1)       IEnumerable`1 Reverse(IEnumerable`1)
                                           IEnumerable`1 Reverse(TSource[])   <- nowe
Void Reverse(Span`1)  (MemoryExtensions)   Void Reverse(Span`1)  (MemoryExtensions)
```

### 🖥️ Prawdziwy output: ten sam kod, `LangVersion 14`, dwa TFM (`reverse-array`)
```
Runtime: .NET 9.0.18, TFM-define: NET9_0
--- 1. Instrukcja `a.Reverse();` (wynik wyrzucony) ---
po a.Reverse(): [5, 4, 3, 2, 1]  -> ODWROCONA w miejscu (Span)

Runtime: .NET 10.0.11, TFM-define: NET10_0_OR_GREATER
--- 1. Instrukcja `a.Reverse();` (wynik wyrzucony) ---
po a.Reverse(): [1, 2, 3, 4, 5]  -> bez zmian (LINQ, wynik wyrzucony)
```
Trzy konfiguracje, jedna linijka `a.Reverse();`:

| Konfiguracja | Co się wiąże | Skutek |
|---|---|---|
| C# 13 (dowolny TFM) | `Enumerable.Reverse(IEnumerable<T>)` | **nic** (leniwy wynik wyrzucony) |
| C# 14 + `net9.0` | `MemoryExtensions.Reverse(Span<T>)` | **odwraca w miejscu** |
| C# 14 + `net10.0` | `Enumerable.Reverse(TSource[])` | **nic** (LINQ znowu) |

### 💡 Co to zmienia w praktyce
- Podbijasz tylko `LangVersion` na `14` w projekcie wciąż celującym w .NET 9 — kod, który „nic nie robił",
  nagle **zmienia dane**. Jeśli ktoś pisał `arr.Reverse();` omyłkowo (zamiast `Array.Reverse`), po cichu
  zacznie „działać". Groźniejsze: kod, który liczył na to, że tablica po `Reverse()` zostaje nietknięta
  (wynik wyrzucony lub nieużyty), mutuje współdzieloną tablicę.
- Na .NET 10 wracasz do semantyki LINQ — **ale tylko dla zmiennych typu tablicowego**. Nigdy nie zakładaj,
  która wersja wygrała; pisz jawnie: `Enumerable.Reverse(a)` (kopia leniwa), `a.AsSpan().Reverse()` albo
  `Array.Reverse(a)` (w miejscu). Wszystkie trzy zweryfikowane w sekcji 2 programu.

### ⚠️ Haczyk A — użycie wyniku rozróżnia światy na etapie kompilacji
`foreach (var x in a.Reverse())` na `net9.0` + C# 14 to prawdziwy błąd kompilatora (`compat-check-reverse`):
```
Program.cs(4,19): error CS1579: foreach statement cannot operate on variables of type 'void' because
'void' does not contain a public instance or extension definition for 'GetEnumerator'
```
Ten sam plik z `-p:LangVersion=13` kompiluje się i drukuje `30 20 10`. Czyli podbicie C# do 14 *bez* zmiany TFM
może wywalić build — to dobra wiadomość (głośny błąd), zła jest tylko wersja z „wyrzuconym wynikiem" powyżej.

### ⚠️ Haczyk B — statyczny typ decyduje; `IEnumerable<T>` zawsze LINQ
Ta sama tablica rzutowana na `IEnumerable<int>`: `asEnumerable.Reverse()` zawsze LINQ, tablica nietknięta,
nawet na net9.0 + C# 14 (sekcja 3 outputu). Dopiero zmienna *typu tablicowego* uruchamia konwersję do spana.

### ⚠️ Czego NIE zweryfikowaliśmy
`List<T>` (tam `Reverse()` jest metodą instancyjną — wygrywa zawsze, nie testowaliśmy), `ReadOnlySpan`, wariancję
tablic referencyjnych (`string[]` → `object[]`), analizatorów, które mogłyby to ostrzegać. Kompilacja net9.0
poszła przez SDK 10.0.400 z pakietem referencyjnym net9 (SDK 9.0.316 z C# 14 nie próbowaliśmy).

**Kod:** [`code/reverse-array/`](code/reverse-array/), [`code/compat-check-reverse/`](code/compat-check-reverse/),
[`code/reflect-diff/`](code/reflect-diff/)

---

## 2️⃣ `HttpMethod.Query` — GET z ciałem, ale uczciwie

### 😤 Problem
Chcesz przesłać złożone zapytanie (filtry, długa lista id, struktura JSON). `GET` nie ma standardowo ciała,
więc kończysz z tym w `POST` (traci semantykę „bezpieczne i idempotentne", cache i retry nie wiedzą, że to
odczyt) albo w gigantycznym query stringu (limity długości, logi z danymi). Metoda `QUERY` (draft IETF
httpbis) jest właśnie tym: bezpieczna, idempotentna, **z ciałem**.

### ✨ Co jest w .NET 10
Statyczna właściwość `HttpMethod.Query` (obok `Get`, `Post`...). Dowód refleksyjny:
```
.NET 9.0.18: Connect Delete Get Head Options Patch Post Put Trace
.NET 10.0.11: ... Post Put Query -> "QUERY" Trace
```
Na prawdziwym SDK 9.0.316 (`global.json` z `rollForward: disable`, `compat-check-query`):
`error CS0117: 'HttpMethod' does not contain a definition for 'Query'`.

### 🖥️ Prawdziwy output (`http-query-method`, serwer `HttpListener` na loopbacku, bez NuGet)
```
--- 1. Round-trip: HttpMethod.Query z cialem JSON ---
status=200, odpowiedz=["alfa","alfabet"]
serwer zobaczyl: QUERY /search body={"prefix":"al"}
--- 2. Rownosc i tekst ---
HttpMethod.Query.Method = "QUERY", ToString = "QUERY"
Query == new HttpMethod("QUERY") : True
Query == new HttpMethod("query") : True
ReferenceEquals(Query, new HttpMethod("QUERY")) : False
HttpMethod.Parse("QUERY") jest singletonem Query : True
--- 3. Dla porownania: GET z cialem ---
GET z cialem -> status=200; serwer zobaczyl: GET /search body={"prefix":"al"}
```
Wniosek praktyczny: **do .NET 9 i tak dało się wysłać QUERY** (`new HttpMethod("QUERY")`) — nowość to wygodna,
nazwana stała i singleton z `Parse`. Równość jest nieczuła na wielkość liter, ale `new` to inna referencja,
więc `ReferenceEquals(req.Method, HttpMethod.Query)` jest kruche; porównuj przez `==`.

### ⚠️ Haczyk A — przekierowania: `QUERY` zachowuje metodę tam, gdzie `POST` ją gubi
Wszystkie pary zmierzone (`AllowAutoRedirect = true`, serwer zwraca kod i `Location`, cel loguje metodę):
```
POST  + 301 -> GET /landed body=<pusto>        QUERY + 301 -> QUERY /landed body=tresc
POST  + 302 -> GET /landed body=<pusto>        QUERY + 302 -> QUERY /landed body=tresc
POST  + 303 -> GET /landed body=<pusto>        QUERY + 303 -> GET /landed body=<pusto>
POST  + 307 -> POST /landed body=tresc         QUERY + 307 -> QUERY /landed body=tresc
POST  + 308 -> POST /landed body=tresc         QUERY + 308 -> QUERY /landed body=tresc
```
(Układ tabeli złożony z dwóch kolumn outputu; surowy output jest w `code/README.md`.) `HttpClient` degraduje do
`GET` tylko `POST` po 301/302 i wszystko po 303. Dla `QUERY` 301/302 zachowują metodę **i ciało**. To rozsądne
(zapytanie jest bezpieczne), ale różni się od intuicji z `POST` — a *dlaczego* tak działa w SocketsHttpHandler,
nie badaliśmy (nie czytaliśmy jego kodu).

### ⚠️ Haczyk B — `GET` z ciałem też „działa", i to jest pułapka
`HttpClient` bez słowa wysłał `GET` z ciałem JSON, serwer je przeczytał. Czyli *technicznie* stara droga działa,
ale pośrednicy (proxy, CDN, WAF) mogą takie ciało obciąć lub odrzucić — `QUERY` jest tu jawnym kontraktem.
Nie sprawdzaliśmy żadnego pośrednika.

### ⚠️ Haczyk C — wsparcie po stronie serwera to osobna sprawa
Nowa stała dotyczy **klienta**. Nasz `HttpListener` przyjął `QUERY` bez problemu, ale nie sprawdzaliśmy
Kestrela, routingu minimal API (`MapMethods`), CORS (preflight dla nietypowej metody), ani cache. Nie zakładaj
ich zachowania na podstawie tego eksperymentu.

**Kod:** [`code/http-query-method/`](code/http-query-method/), dowód `CS0117`:
[`code/compat-check-query/`](code/compat-check-query/)

---

## 📎 Jak zweryfikowano
- `reflect-diff` uruchomione na runtime 9.0.18 i 10.0.11 (`dotnet run -f ...`); wskazał oba znaleziska. Diff
  szerszy (CoreLib, Linq, Http, Process, Collections, Pipelines, Tar, Channels, Regex...) zrobiono jednorazowym
  narzędziem poza repo, bez zapisu wyniku tutaj — lista „zostało" niżej pochodzi z niego.
- `reverse-array`: `dotnet run -f net9.0` i `-f net10.0` (SDK 10.0.400, `LangVersion 14`).
  `compat-check-reverse`: `CS1579`, a z `-p:LangVersion=13` poprawny `30 20 10`.
- `http-query-method`: `dotnet run -c Release`, dwa przebiegi, identyczny output. `compat-check-query`: `CS0117` na SDK 9.0.316.
- **Niezweryfikowane:** `List<T>`/`ReadOnlySpan` przy `Reverse`, Kestrel/minimal API/CORS/cache dla `QUERY`,
  pośrednicy HTTP, przyczyna zachowania przy 301/302, status RFC (to wciąż draft IETF wg naszej wiedzy, nie
  sprawdzaliśmy online), .NET 11 (brak SDK), dokumentacja online (nie korzystano).
- **Zostało z diffu (nieopisane):** `ZipFile`/`ZipArchive`/`ZipArchiveEntry` async (`CreateFromDirectoryAsync`,
  `ExtractToDirectoryAsync`, `ZipArchive.CreateAsync`, `OpenAsync`, `DisposeAsync`) — widoczne w refleksji, brak
  jeszcze kodu; `CompositeMLDsa`.

---

## 📎 Jak uruchomić
Zobacz [`code/README.md`](code/README.md).

---

<div align="center">

[← wszystkie artykuły: 🔷 .NET — nowości w wersji](../README.md) · [spis rubryk](../../../README.md)

</div>
