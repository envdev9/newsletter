# Kod do wydania #13 — `Utf8JsonWriter.WriteStringValueSegment`/`WriteBase64StringSegment` i `JsonObject.TryAdd`/`TryGetPropertyValue` z `out int` (.NET 10)

Pełny artykuł: [`../ARTICLE.md`](../ARTICLE.md).

Wymagania: **.NET 10 SDK** (sprawdzone na `10.0.400`). `utf8writer-segments` i
`jsonobject-index` celują w `net10.0`; `compat-check` celowo w `net9.0` (potrzebuje
SDK 9.x obok; sprawdzone na `9.0.316`). Brak zależności NuGet.

## Fragment prasówki, którego dotyczy ten kod

> `Utf8JsonWriter.WriteStringValueSegment` (UTF-16 i UTF-8) oraz
> `WriteBase64StringSegment` — zapis dużego stringa/base64 w kawałkach, z
> `isFinalSegment`. Nie istnieją w .NET 9 (`CS1061`×3). Zmierzone: 64 MB tekstu —
> cały string 128 MB + 1216 MB na zapis; segmenty BEZ `Flush()` 256 MB; segmenty z
> `Flush()` po każdym kawałku 24 KB. Haczyki: segmenty bez `Flush` nie streamują;
> mieszanie `char`/`byte` rzuca `InvalidOperationException`; `Dispose` po kawałku
> niefinalnym nie rzuca i zostawia ucięty JSON.
>
> `JsonObject.TryAdd(name, value, out int index)` i
> `TryGetPropertyValue(name, out value, out int index)` — pozycja właściwości w
> jednym wywołaniu (przy nieudanym `TryAdd` — indeks istniejącej; przy braku
> właściwości `-1`). Nie istnieją w .NET 9 (`CS1501`×2); dostęp indeksowy
> (`IndexOf`/`GetAt`/`SetAt`/`Insert`/`RemoveAt`) jest starszy i kompiluje się na .NET 9.
> Haczyki: indeks to migawka; `TryAdd` węzła z rodzicem rzuca, ale zostawia obiekt
> zmieniony; z `PropertyNameCaseInsensitive` indeks dotyczy właściwości o innej pisowni.

## 1. utf8writer-segments

```bash
dotnet run -c Release --project utf8writer-segments
```

Output (liczby alokacji zależą od maszyny/uruchomienia, reszta deterministyczna;
sekcja 2 używa losowych bajtów, ale wynik porównania jest stały):

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

--- 4. HACZYK A: nie mozna mieszac kodowan w jednym stringu (UTF-16 vs UTF-8) ---
char potem byte: RZUCILO InvalidOperationException: "Mixing UTF encodings in a single multi-segment JSON string is not supported. The previous segment's encoding was 'UTF-16' and the current segment's encoding is 'UTF-8'."

--- 5. HACZYK B: cięcie wielobajtowego znaku miedzy kawalkami ---
   -> "zażółć"
UTF-8: ciecie w srodku 'ż' (po 3 bajtach): NIE rzucilo
   -> "a😀b"
UTF-16: ciecie pary surrogatow: NIE rzucilo
   -> "a�"
UTF-16: samotny wysoki surrogat jako OSTATNI kawalek: NIE rzucilo

--- 6. HACZYK C: niezakonczony string (brak isFinalSegment: true) ---
zamkniecie obiektu w trakcie stringa: RZUCILO InvalidOperationException: "'}' is invalid following a property name."
   -> "abc
Dispose bez finalnego kawalka: NIE rzucilo
```

## 2. jsonobject-index

```bash
dotnet run --project jsonobject-index
```

```
--- 1. Problem: 'dodaj jesli brak, a potem znajdz pozycje' = 2-3 wyszukiwania ---
{"id":1,"name":"Ala","role":"admin"}  pozycja 'role' = 2

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

--- 5. HACZYK A: indeks to MIGAWKA - Insert/RemoveAt przesuwa pozycje ---
indeks 'c' sprzed RemoveAt(0): 2, aktualny IndexOf("c"): 1
GetAt(2) po usunieciu: RZUCILO ArgumentOutOfRangeException: "Specified argument was out of the range of valid values. (Parameter 'index')"

--- 6. HACZYK B: wielkosc liter (PropertyNameCaseInsensitive) ---
TryGetPropertyValue("NAME") -> True, value = Ala, index = 0
TryAdd("NAME") -> False, index = 0, JSON: {"Name":"Ala"}

--- 7. HACZYK C: wezel z rodzicem - czy TryAdd zwroci false, czy rzuci? ---
TryAdd nowego klucza z wezlem majacym rodzica: RZUCILO InvalidOperationException: "The node already has a parent."
TryAdd ISTNIEJACEGO klucza z wezlem majacym rodzica: NIE rzucilo
   zajeta: {"dziecko":{"v":1}}, rodzic: {"x":1,"nowy":{"v":1}}
```

(W artykule haczyki tej sekcji są oznaczone A/B/C w innej kolejności niż numery sekcji
w kodzie: A = sekcja 5, C = sekcja 6, B = sekcja 7 — rozbieżność tylko w nazewnictwie.)

## 3. compat-check (celowo NIE kompiluje się na .NET 9)

```bash
dotnet build compat-check
```

Oczekiwany wynik — dokładnie 5 błędów (zweryfikowane): `CS1501` dla `TryAdd` i
`TryGetPropertyValue` (3 argumenty), `CS1061` dla `WriteStringValueSegment`×2 i
`WriteBase64StringSegment`. Linie "STARE" w pliku (`IndexOf`, `GetAt`, `Insert`,
`SetAt`, `RemoveAt`, `TryGetPropertyValue` z 1 `out`) kompilują się bez błędu.

## Zweryfikowane / niezweryfikowane

- Zweryfikowane `dotnet run` (SDK 10.0.400): oba programy, wszystkie sekcje.
- Zweryfikowane `dotnet build` (net9.0, SDK 9.0.316): 5 błędów jak wyżej.
- Niezweryfikowane: wewnętrzne przyczyny (wzrost bufora writera, nieatomowość
  `TryAdd`), użycie w ASP.NET, .NET 11 (brak SDK), dokumentacja online.
