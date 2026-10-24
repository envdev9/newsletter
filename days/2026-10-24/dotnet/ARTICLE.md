<div align="center">

# 📰 TECH PRASÓWKA
### Wydanie #29 — 24 października 2026

![.NET](https://img.shields.io/badge/.NET-10-512BD4?style=for-the-badge&logo=dotnet&logoColor=white)
![BCL](https://img.shields.io/badge/BCL-async%20System.IO.Compression-blue?style=for-the-badge)

## Async ZIP w .NET 10: `CreateFromDirectoryAsync`, `ZipArchive.CreateAsync` — i dlaczego „async" nie znaczy jeszcze „zero synchronicznego I/O"

</div>

---

> _„Zliczyliśmy zapisy na strumieniu docelowym: 25 synchronicznych w starym API. W nowym async: 11 synchronicznych i 14 asynchronicznych."_
> — wynik eksperymentu poniżej, .NET 10.0.11.

Z listy „zostało z diffu" (wydanie #25) zostały async API `System.IO.Compression` — do tej pory były tylko
potwierdzone refleksją, bez kodu. Dziś kod: pełne round-trip'y, anulowanie, zip-slip, a przede wszystkim
**pomiar, ile synchronicznego I/O zostaje w „asynchronicznym" API**. SDK .NET 11 nadal niedostępne
(`dotnet --list-sdks`: 8.0.422, 8.0.425, 9.0.316, 10.0.400). Kod w [`code/`](code/).

| # | Funkcja | Namespace | Status |
|---|---------|-----------|--------|
| 1️⃣ | Async `ZipFile` / `ZipArchive` / `ZipArchiveEntry` (`CreateFromDirectoryAsync`, `ExtractToDirectoryAsync`, `CreateAsync`, `OpenAsync`, `DisposeAsync`) | `System.IO.Compression` | ✅ `dotnet run` (net10.0), `CS0117` na SDK 9.0.316 |

---

## 1️⃣ Async ZIP — co dokładnie doszło

### 😤 Problem
Do .NET 9 cały `ZipFile`/`ZipArchive` był synchroniczny. W serwerze (ASP.NET, worker) pakowanie katalogu albo
rozpakowanie uploadu blokuje wątek z puli na czas I/O dysku lub sieci. Obejście `Task.Run(() => ZipFile...)`
nie oddaje wątku — tylko go przenosi.

### 🔬 Dowód: refleksja na dwóch runtime'ach (`zip-reflect`)
Ten sam program, `dotnet run -f net9.0` i `-f net10.0`, szuka publicznych metod kończących się na `Async`:
```
.NET 9.0.18  : ZipFile / ZipFileExtensions / ZipArchive / ZipArchiveEntry -> (brak) we wszystkich czterech
.NET 10.0.11 : ZipFile:           CreateFromDirectoryAsync (6 przeciążeń, ścieżka lub Stream),
                                  ExtractToDirectoryAsync (8), OpenAsync (2), OpenReadAsync (1)
               ZipFileExtensions: ExtractToDirectoryAsync (2), ExtractToFileAsync (2), CreateEntryFromFileAsync (2)
               ZipArchive:        CreateAsync(Stream, ZipArchiveMode, bool, Encoding, CancellationToken), DisposeAsync()
               ZipArchiveEntry:   OpenAsync(CancellationToken)
```
Na prawdziwym SDK 9.0.316 (`global.json`, `rollForward: disable`; `compat-check-zip`):
```
error CS0117: 'ZipFile' does not contain a definition for 'CreateFromDirectoryAsync'
error CS0117: 'ZipFile' does not contain a definition for 'ExtractToDirectoryAsync'
error CS0117: 'ZipArchive' does not contain a definition for 'CreateAsync'
```
Zwróć uwagę na kształt: **`ZipArchive` nie ma publicznego konstruktora async**, więc jest fabryka `CreateAsync`
(konstruktor nie może być `await`-owany), a `ZipArchiveEntry.OpenAsync` zwraca `Task<Stream>`.

### 🖥️ Prawdziwy output: round-trip i odczyt (`zip-async`, `dotnet run -c Release`)
```
rozmiar zip: 50377 B (zrodlo: 60026 B)
a.txt: hash zgodny = True
sub/b.txt: hash zgodny = True
sub/rnd.bin: hash zgodny = True
--- Odczyt: OpenReadAsync + entry.OpenAsync ---
a.txt: 10000 B -> skompresowane 28 B
sub/b.txt: 26 B -> skompresowane 29 B
sub/rnd.bin: 50000 B -> skompresowane 50020 B
```
(Dane losowe się nie kompresują: 50 000 → 50 020 B, nawet nieco rosną.)

### ⚠️ Haczyk A (główny) — „async" to nie „zero synchronicznego I/O"
Wstrzyknęliśmy do wszystkich scenariuszy nieseekowalny strumień docelowy, który **liczy** zapisy synchroniczne
i asynchroniczne (nic nie rzuca; dane trafiają do pamięci i są weryfikowane jako poprawny zip):
```
scenariusz                                                 sync Write  async Write    bajty  poprawny zip
sync  ZipFile.CreateFromDirectory(dir, Stream), Optimal            25            0    50425  tak (3 wpisy)
async ZipFile.CreateFromDirectoryAsync(dir, Stream), Optimal         11           14    50425  tak (3 wpisy)
async ZipFile.CreateFromDirectoryAsync(dir, Stream), NoCompr.          3           16    60374  tak (3 wpisy)
async reczne CreateAsync+OpenAsync+DisposeAsync, Optimal           11           14    50425  tak (3 wpisy)
jw. + await entryStream.FlushAsync() przed Dispose                  6           22    50445  tak (3 wpisy)
async reczne CreateAsync+OpenAsync+DisposeAsync, NoCompr.           3           16    60374  tak (3 wpisy)
```
Wynik identyczny w dwóch przebiegach. Wnioski, które są **zmierzone**:
- Nowe API robi zdecydowaną większość zapisów asynchronicznie, ale **nie wszystkie**: 11 z 25 zapisów (Optimal)
  nadal jest synchronicznych, 3 przy `NoCompression`.
- Pierwsza wersja eksperymentu używała strumienia, który *rzuca* na synchroniczny `Write`. `await using` na
  strumieniu wpisu wywalił się w stosie `Stream.DisposeAsync` → `Stream.Close` → `DeflateStream.Dispose` →
  `PurgeBuffers` → sync `Write`. Czyli przynajmniej w tej ścieżce zamknięcie strumienia wpisu w trybie
  kompresji domykało skompresowany strumień synchronicznie. Z tego stosu pochodzi nasza (nie potwierdzona w
  źródłach) hipoteza: końcówka strumienia deflate jest zapisywana przy `Dispose`, a nie przez ścieżkę async.
- Dodanie `await entryStream.FlushAsync()` przed zamknięciem zmniejszyło liczbę synchronicznych zapisów
  z 11 do 6 (i zwiększyło asynchroniczne z 14 do 22), ale ich nie wyeliminowało i dodało 20 B danych
  (50445 vs 50425 — to dodatkowe bloki sync-flush deflate).
- **Konsekwencja:** jeśli piszesz do strumienia, który *zabrania* synchronicznego I/O (np. `Response.Body`
  w Kestrelu z `AllowSynchronousIO = false`), samo przejście na `...Async` **może nadal rzucić**. Nie
  sprawdzaliśmy tego na Kestrelu — to wniosek z naszego strumienia testowego, nie z realnego serwera.

### ⚠️ Haczyk B — anulowanie zostawia plik
```
zawczasu anulowany token: OperationCanceledException
plik po anulowaniu istnieje: False
anulowanie w trakcie: TaskCanceledException
plik po anulowaniu istnieje: True, rozmiar 592301 B
da sie otworzyc, wpisow: 3 z 200
```
Token anulowany *przed* startem: wyjątek, brak pliku. Anulowanie *w trakcie* (200 plików po 200 kB,
`SmallestSize`): `TaskCanceledException` (podklasa `OperationCanceledException`) i **na dysku zostaje częściowy,
ale otwieralny zip** z kilkoma wpisami. Liczba wpisów i rozmiar zależą od czasu (w dwóch przebiegach:
2 wpisy/392144 B i 3 wpisy/592301 B). Jeśli anulujesz pakowanie, **sam usuń plik wyjściowy** — biblioteka tego nie zrobi.

### ⚠️ Haczyk C — zip-slip jest blokowany także w async
Archiwum z wpisem `../evil.txt`:
```
IOException: Extracting Zip entry would have resulted in a file outside the specified destination directory.
evil.txt poza katalogiem docelowym istnieje: False
```
Zweryfikowane tylko dla `ExtractToDirectoryAsync` z ścieżką; inne warianty (dowiązania symboliczne, wpisy
absolutne) nie były testowane.

### 💡 Co to zmienia w praktyce
- Endpoint „pobierz katalog jako zip" czy worker rozpakowujący uploady może wreszcie nie blokować wątków na
  I/O pliku — ale **mierz**, nie zakładaj: jak widać, kompresja i część zapisów nadal są synchroniczne.
- Dla zapisów do plików lokalnych (`ZipFile.CreateFromDirectoryAsync(src, "out.zip")`) wystarczy zamiana nazwy
  metody. Dla strumieni sieciowych o ścisłym async-only przetestuj własny scenariusz, zanim uwierzysz w nazwę.
- `await using var archive = await ZipArchive.CreateAsync(...)` — w trybie `Create` sam `Dispose` zapisuje
  katalog centralny, więc `DisposeAsync` jest właściwym zamknięciem w kodzie async.

### ⚠️ Czego NIE zweryfikowaliśmy
Kestrel/`Response.Body`, strumienie sieciowe, tryb `Update`, duże archiwa (zip64), faktyczne uwolnienie wątku
(nie mierzyliśmy zajętości puli — tylko typ wywołań na strumieniu docelowym), wydajność/czasy, przyczynę
pozostałych synchronicznych zapisów w kodzie biblioteki (nie czytaliśmy źródeł), zachowanie `ZipArchive.Dispose()`
(sync) po użyciu ścieżek async, .NET 11 (brak SDK).

**Kod:** [`code/zip-async/`](code/zip-async/), [`code/zip-reflect/`](code/zip-reflect/),
dowód `CS0117`: [`code/compat-check-zip/`](code/compat-check-zip/)

---

## 📎 Jak zweryfikowano
- `zip-reflect`: `dotnet run -f net9.0` i `-f net10.0` (SDK 10.0.400, runtime 9.0.18 / 10.0.11).
- `zip-async`: `dotnet run -c Release`, dwa przebiegi; sekcje 1, 2, 3 i 5 identyczne, sekcja 4 (anulowanie w trakcie) zależna od czasu.
- `compat-check-zip`: `dotnet build` na SDK 9.0.316 → 3×`CS0117`.
- **Niezweryfikowane:** patrz wyżej; dokumentacja online nie była używana.
- **Zostało z diffu (nieopisane):** `ProcessStartInfo.CreateNewProcessGroup`, `CompositeMLDsa`.

---

## 📎 Jak uruchomić
Zobacz [`code/README.md`](code/README.md).

---

<div align="center">

[← wróć do wydania #29 (wszystkie rubryki)](../README.md) · [spis wydań](../../../README.md)

</div>
