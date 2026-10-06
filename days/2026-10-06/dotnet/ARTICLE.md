<div align="center">

# 📰 TECH PRASÓWKA
### Wydanie #13 — 6 października 2026

![.NET](https://img.shields.io/badge/.NET-10-512BD4?style=for-the-badge&logo=dotnet&logoColor=white)
![BCL](https://img.shields.io/badge/System.Text.Json-runtime-blue?style=for-the-badge)

## JSON w kawałkach: 64 MB stringa za 24 KB alokacji — i pozycja właściwości za darmo

</div>

---

> _"Mixing UTF encodings in a single multi-segment JSON string is not supported."_
> — `System.InvalidOperationException`, zmierzone realnie w tej sesji. Nowe API do
> strumieniowego pisania stringów ma regułę, której nie zgadniesz z sygnatury — a do tego
> **cichą** pułapkę wydajnościową (sekcja 1️⃣, haczyk A), przez którą "streaming" potrafi
> zjeść 256 MB.

Wydanie #12 zostawiło otwarte tropy z diffu refleksyjnego `System.Text.Json.dll`
(runtime 9.0.18 vs 10.0.11): `Utf8JsonWriter.WriteStringValueSegment`/
`WriteBase64StringSegment` oraz `JsonObject.TryAdd`/`TryGetPropertyValue` z `out int`.
Dziś domykamy oba — i to jest ostatni nieopisany kawałek `System.Text.Json` z tamtego
diffu. SDK .NET 11 nie ma na tej maszynie (`dotnet --list-sdks`: 8.0.422, 8.0.425,
9.0.316, 10.0.400), więc zostajemy przy .NET 10. Kod w [`code/`](code/).

| # | Funkcja | Namespace | Status |
|---|---------|-----------|--------|
| 1️⃣ | `Utf8JsonWriter.WriteStringValueSegment` / `WriteBase64StringSegment` | `System.Text.Json` | ✅ w pełni zweryfikowane |
| 2️⃣ | `JsonObject.TryAdd` / `TryGetPropertyValue` z `out int index` | `System.Text.Json.Nodes` | ✅ w pełni zweryfikowane |

---

## 1️⃣ `Utf8JsonWriter.WriteStringValueSegment` — zapis ogromnego stringa/base64 w kawałkach

### 😤 Problem
`Utf8JsonWriter.WriteStringValue(string)` chce **całą** wartość naraz. Chcesz wpisać do
JSON-a 64 MB tekstu (log, dokument) albo plik w base64 — musisz najpierw zbudować w
pamięci cały `string` (u nas: **128 MB** na sam string, bo `char` = 2 bajty), a dopiero
potem go przekazać. Dla base64 jeszcze gorzej: `Convert.ToBase64String(bajty)` to kolejna
kopia ~4/3 rozmiaru. Streaming z pliku/sieci do wyjściowego JSON-a nie był możliwy bez
obejść (ręczne pisanie surowych bajtów z własnym escapingiem).

### ✨ Co się zmieniło
.NET 10 dodaje na `Utf8JsonWriter` trzy metody, które dopisują wartość stringa **po
kawałku**, a ostatni kawałek oznaczasz `isFinalSegment: true`:
- `WriteStringValueSegment(ReadOnlySpan<char>, bool isFinalSegment)` — UTF-16,
- `WriteStringValueSegment(ReadOnlySpan<byte>, bool isFinalSegment)` — UTF-8,
- `WriteBase64StringSegment(ReadOnlySpan<byte>, bool isFinalSegment)` — bajty → base64.

Escaping (cudzysłowy, znaki sterujące, non-ASCII) działa ponad granicami kawałków.
Sprawdzone empirycznie: **żadna z trzech nie istnieje w .NET 9** — `CS1061` na `net9.0`
(dowód niżej).

```csharp
using var w = new Utf8JsonWriter(strumienWyjsciowy);
w.WriteStartObject();
w.WritePropertyName("tresc");
foreach (var kawalek in CzytajKawalki())            // np. 8 KB z pliku
{
    w.WriteStringValueSegment(kawalek.Dane, isFinalSegment: kawalek.Ostatni);
    w.Flush();                                       // <- patrz haczyk A!
}
w.WriteEndObject();
```

### 🖥️ Prawdziwy output (`dotnet run -c Release --project utf8writer-segments`, ta maszyna)
```
--- 1. Segmenty daja ten sam JSON co jedno WriteStringValue (escaping dziala ponad granicami) ---
jednym:    "Zazolc "gesla" jazn\n\tend"
kawalkami: "Zazolc "gesla" jazn\n\tend"
rowne: True

--- 2. Base64: kawalki NIE musza byc wielokrotnoscia 3 bajtow ---
zgodne z Convert.ToBase64String: True (dlugosc 13338)

--- 3. Pomiar: 64 MB tekstu do strumienia - jeden string vs strumieniowo w kawalkach 8 KB ---
A) caly string: alokacje na zbudowanie stringa 128 MB, na sam zapis 1216 MB
B) segmenty 8 KB, BEZ Flush miedzy kawalkami: alokacje lacznie 256 MB
C) segmenty 8 KB, Flush po kazdym: alokacje lacznie 24 KB
```

### 🔬 Dowód „przed i po" (target `net9.0`)
```
error CS1061: 'Utf8JsonWriter' does not contain a definition for 'WriteStringValueSegment' ...
error CS1061: 'Utf8JsonWriter' does not contain a definition for 'WriteStringValueSegment' ...
error CS1061: 'Utf8JsonWriter' does not contain a definition for 'WriteBase64StringSegment' ...
```
(trzy błędy — po jednym na każde z trzech przeciążeń użytych w `compat-check`).

### 💡 Co to zmienia w praktyce
- Zapis dużych wartości (dokument, plik jako base64) prosto ze strumienia wejściowego
  do wyjściowego JSON-a, w stałej pamięci — bez `string`/`byte[]` na całość.
- Kawałki base64 **nie muszą** być wielokrotnością 3 bajtów: 10 000 bajtów pocięte
  na 1000-bajtowe porcje (1000 % 3 = 1) dało wynik identyczny z
  `Convert.ToBase64String` (sekcja 2) — writer sam pilnuje reszty.
- Cięcie w środku znaku też jest bezpieczne: UTF-8 cięte w środku `ż` oraz UTF-16 cięte
  w środku pary surrogatów dały poprawny, ten sam JSON co zapis jednym kawałkiem
  (`"zażółć"`, `"a😀b"`; sekcja 5).

### ⚠️ Haczyk A — bez `Flush()` "streaming" buforuje wszystko w pamięci (zmierzone: 256 MB)
To najważniejsza rzecz z dzisiejszego wydania. `Utf8JsonWriter` pisze do wewnętrznego
bufora, a do `Stream` oddaje dane dopiero przy `Flush()` (lub gdy sam uzna za stosowne —
u nas nie uznał). Wariant B (segmenty, ale bez `Flush`) zaalokował **256 MB** — więcej
niż sam string (128 MB), bo bufor rośnie przez podwajanie, a znak `"` w każdym kawałku
rozdyma wyjście do `"`. Wariant C (`Flush` po każdym kawałku) — **24 KB** łącznie
na 64 MB danych. Sam mechanizm segmentów NIE daje streamingu; daje go dopiero para
segment + `Flush`. (Wariant A: 1216 MB na sam zapis jednego 128-MB stringa — ta liczba
pokazuje skalę wzrostu bufora; jej dokładnej przyczyny wewnątrz writera nie badano.)

### ⚠️ Haczyk B — nie mieszaj `char` i `byte` w jednym stringu
```
char potem byte: RZUCILO InvalidOperationException: "Mixing UTF encodings in a single multi-segment JSON string is not supported. The previous segment's encoding was 'UTF-16' and the current segment's encoding is 'UTF-8'."
```
Pierwszy kawałek ustala kodowanie dla całego stringa. Wybierz jedno kodowanie i trzymaj
się go do `isFinalSegment: true`.

### ⚠️ Haczyk C — łatwo zostawić string niedomknięty, a writer tego nie wyłapie przy `Dispose`
Zmierzone: `WriteEndObject()` w środku niedokończonego stringa rzuca
`InvalidOperationException: '}' is invalid following a property name.` (komunikat
myli — nie mówi o niedomkniętym stringu). Gorzej: samo `Dispose()` po kawałku z
`isFinalSegment: false` **nie rzuca** i zostawia ucięty JSON `"abc` bez zamykającego
cudzysłowu. Pilnuj flagi końcowej sam. Bonus: samotny wysoki surrogat jako ostatni
kawałek nie rzuca, tylko jest cicho zamieniany na `�` (`"a�"`).

**Kod:** [`code/utf8writer-segments/`](code/utf8writer-segments/), dowód `CS1061`×3:
[`code/compat-check/`](code/compat-check/)

---

## 2️⃣ `JsonObject.TryAdd` / `TryGetPropertyValue` z `out int index` — pozycja właściwości w jednym wywołaniu

### 😤 Problem
`JsonObject` od .NET 9 zachowuje kolejność właściwości i ma dostęp indeksowy
(`IndexOf`, `GetAt`, `SetAt`, `Insert`, `RemoveAt` — sprawdzone: kompilują się na
`net9.0`, więc to NIE jest nowość .NET 10). Brakowało jednak tańszego sposobu, by
**dowiedzieć się, gdzie** właściwość jest. "Dodaj jeśli brak i podaj pozycję" znaczyło:
`ContainsKey` + `Add` + `IndexOf` — do trzech osobnych wyszukiwań po kluczu (ile faktycznie kosztuje
każde, nie mierzono).

### ✨ Co się zmieniło
.NET 10 dodaje dwa przeciążenia instancyjne:
- `bool TryAdd(string name, JsonNode? value, out int index)`,
- `bool TryGetPropertyValue(string name, out JsonNode? value, out int index)`.

Sprawdzone empirycznie: na `net9.0` oba dają `CS1501` (dowód niżej), a starsze wersje
(`TryAdd` bez indeksu, `TryGetPropertyValue` z jednym `out`) kompilują się dalej.

```csharp
var cfg = JsonNode.Parse("""{"host":"localhost","port":5432,"tls":false}""")!.AsObject();

// upsert z zachowaniem pozycji: dopisz, a jesli klucz jest - podmien w TYM SAMYM miejscu
if (!cfg.TryAdd("port", 6432, out int i)) cfg.SetAt(i, 6432);

// wstaw "user" tuz za "host" - pozycja z jednego wywolania
if (cfg.TryGetPropertyValue("host", out _, out int hostIdx))
    cfg.Insert(hostIdx + 1, "user", "app");
```

### 🖥️ Prawdziwy output (`dotnet run --project jsonobject-index`, ta maszyna)
```
--- 2. .NET 10: TryAdd(..., out int index) - jedno wywolanie ---
TryAdd(role)  -> True, index = 2, JSON: {"id":1,"name":"Ala","role":"admin"}
TryAdd(role)  -> False, index = 2 (indeks ISTNIEJACEJ wlasciwosci), JSON: {"id":1,"name":"Ala","role":"admin"}

--- 3. .NET 10: TryGetPropertyValue(..., out value, out int index) ---
name  -> True, value = Ala, index = 1
nope  -> False, value = null, index = -1

--- 4. Praktyka: upsert z zachowaniem kolejnosci + wstawienie 'za' istniejacym kluczem ---
  podmieniono 'port' na pozycji 1
  dopisano 'timeout' na pozycji 3
  wynik: {"host":"localhost","user":"app","port":6432,"tls":false,"timeout":30}
```

### 🔬 Dowód „przed i po" (target `net9.0`)
```
error CS1501: No overload for method 'TryAdd' takes 3 arguments
error CS1501: No overload for method 'TryGetPropertyValue' takes 3 arguments
```

### 💡 Co to zmienia w praktyce
- **Upsert z zachowaniem kolejności** to jedno wywołanie + ewentualne `SetAt`: gdy
  `TryAdd` zwraca `false`, `index` wskazuje **istniejącą** właściwość (zmierzone: 2 przy
  pierwszym i drugim wywołaniu) — nie trzeba osobnego `IndexOf`.
- Edycje konfiguracji/manifestów JSON, gdzie kolejność kluczy ma znaczenie dla diffów
  w repo (wstaw klucz zaraz za sąsiadem, nie na końcu).
- Konwencja "nie znaleziono" jest czytelna: `index == -1` (zmierzone), `value == null`.

### ⚠️ Haczyk A — indeks to migawka
Zmierzone: indeks `"c"` = 2, po `RemoveAt(0)` `IndexOf("c")` = 1, a `GetAt(2)` ze starym
indeksem rzuca `ArgumentOutOfRangeException`. Każdy `Insert`/`RemoveAt` przed użyciem
indeksu go unieważnia — pobieraj i używaj od razu.

### ⚠️ Haczyk B — `TryAdd` rzuca przy węźle z rodzicem i zostawia obiekt zmieniony
Zmierzone (sekcja 7 w kodzie): `TryAdd("nowy", dziecko, out _)`, gdzie `dziecko` należy
już do innego obiektu, rzuca `InvalidOperationException: "The node already has a
parent."` — a mimo to końcowy JSON obiektu docelowego **zawiera** `"nowy":{"v":1}`
(`{"x":1,"nowy":{"v":1}}`), podczas gdy obiekt-poprzednik nadal ma swoje dziecko. Czyli
wyjątek nie jest atomowy: nie łap go i nie zakładaj, że obiekt został nietknięty. Ten sam
węzeł przy kluczu, który już istnieje, daje `false` bez wyjątku. Skutek uboczny:
`DeepClone()` węzła przed dodaniem. (Dlaczego tak się dzieje wewnątrz — nie badano.)

### ⚠️ Haczyk C — z `PropertyNameCaseInsensitive` indeks dotyczy właściwości o INNEJ pisowni
Zmierzone: obiekt z `["Name"]` i opcją case-insensitive — `TryGetPropertyValue("NAME")`
→ `true`, index 0; `TryAdd("NAME", "Ola")` → `false` (nic nie dopisano, JSON bez zmian).

**Kod:** [`code/jsonobject-index/`](code/jsonobject-index/), dowód `CS1501`×2:
[`code/compat-check/`](code/compat-check/)

---

## 📎 Jak zweryfikowano
- Źródło tropów: diff refleksyjny z wydania #12 (runtime 9.0.18 vs 10.0.11); w tej
  sesji go nie powtarzano — każdą funkcję potwierdzono wprost kompilacją na `net9.0`
  (SDK 9.0.316): 5 błędów (`CS1501`×2, `CS1061`×3), a linie ze starym API (`IndexOf`,
  `GetAt`, `SetAt`, `Insert`, `RemoveAt`, `TryGetPropertyValue` z 1 `out`) w tym samym
  pliku kompilują się bez błędu.
- Oba programy uruchomione `dotnet run` na SDK 10.0.400 (liczby alokacji z
  `GC.GetAllocatedBytesForCurrentThread`, tryb Release; wartości mogą się różnić
  między uruchomieniami/maszynami, rząd wielkości — nie).
- **Niezweryfikowane:** wewnętrzna przyczyna wzrostu bufora i nieatomowości `TryAdd`,
  zachowanie w ASP.NET (`Response.BodyWriter`), wydajność wobec ręcznego zapisu surowych
  bajtów, .NET 11 (brak SDK). Nie korzystano z dokumentacji online.
- Zostaje: `MemoryExtensions.CountAny`/`ReplaceAny`/`ReplaceAnyExcept` z `SearchValues<T>`.

---

## 📎 Jak uruchomić
Zobacz [`code/README.md`](code/README.md).

---

<div align="center">

[← wróć do wydania #13 (wszystkie rubryki)](../README.md) · [spis wydań](../../../README.md)

</div>
