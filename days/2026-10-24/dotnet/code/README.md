# Kod do wydania #29 — async `System.IO.Compression` (.NET 10)

Pełny artykuł: [`../ARTICLE.md`](../ARTICLE.md).

Wymagania: **.NET 10 SDK** (sprawdzone na `10.0.400`) oraz runtime 9.x (`dotnet --list-runtimes`) dla
`zip-reflect` (dwa TFM); `compat-check-zip` wymaga **SDK 9.0.316** (przypięte `global.json`,
`rollForward: disable` — zmień wersję, jeśli masz inne 9.0.x). Brak NuGet i sieci; `zip-async` pracuje w
katalogu tymczasowym i sprząta po sobie.

## Fragment prasówki, którego dotyczy ten kod

> **Async ZIP w .NET 10.** `ZipFile.CreateFromDirectoryAsync`/`ExtractToDirectoryAsync`/`OpenAsync`/`OpenReadAsync`,
> `ZipArchive.CreateAsync` (fabryka zamiast konstruktora) + `DisposeAsync`, `ZipArchiveEntry.OpenAsync`,
> `ZipFileExtensions.ExtractToFileAsync`/`CreateEntryFromFileAsync`. Na .NET 9 refleksja: brak jakichkolwiek
> metod `*Async` w tych typach; SDK 9.0.316 → `CS0117`. Zmierzone na strumieniu docelowym liczącym zapisy:
> stare API 25 zapisów synchronicznych; nowe async 11 synchronicznych + 14 asynchronicznych (`NoCompression`:
> 3 + 16). Czyli „async" ≠ „zero synchronicznego I/O" — strumień wpisu zamykany przez `await using` kończy
> deflate synchronicznie (stos: `Stream.DisposeAsync` → `DeflateStream.Dispose` → `PurgeBuffers` → sync `Write`).
> Anulowanie w trakcie zostawia częściowy, otwieralny plik zip. Zip-slip (`../evil.txt`) blokowany `IOException`.

## 1. zip-reflect (refleksja na dwóch runtime'ach)

```bash
dotnet run -f net9.0  --project zip-reflect
dotnet run -f net10.0 --project zip-reflect
```

Zweryfikowany output: na 9.0.18 wszędzie `(brak)`; na 10.0.11 lista metod z artykułu (m.in.
`static Task CreateFromDirectoryAsync(String, String, CancellationToken)`, `static Task`1 CreateAsync(Stream,
ZipArchiveMode, Boolean, Encoding, CancellationToken)`, `ValueTask DisposeAsync()`, `Task`1 OpenAsync(CancellationToken)`).

## 2. zip-async

```bash
dotnet run -c Release --project zip-async
```

Output (zweryfikowany, 2 przebiegi; sekcja 4, anulowanie w trakcie, zależy od czasu):

```
Runtime: .NET 10.0.11
--- 1. Round-trip CreateFromDirectoryAsync -> ExtractToDirectoryAsync ---
rozmiar zip: 50377 B (zrodlo: 60026 B)
a.txt: hash zgodny = True
sub/b.txt: hash zgodny = True
sub/rnd.bin: hash zgodny = True
--- 2. Sync vs async zapisy na strumieniu docelowym ---
scenariusz                                                 sync Write  async Write    bajty  poprawny zip
sync  ZipFile.CreateFromDirectory(dir, Stream), Optimal            25            0    50425  tak (3 wpisy)
async ZipFile.CreateFromDirectoryAsync(dir, Stream), Optimal         11           14    50425  tak (3 wpisy)
async ZipFile.CreateFromDirectoryAsync(dir, Stream), NoCompr.          3           16    60374  tak (3 wpisy)
async reczne CreateAsync+OpenAsync+DisposeAsync, Optimal           11           14    50425  tak (3 wpisy)
jw. + await entryStream.FlushAsync() przed Dispose                  6           22    50445  tak (3 wpisy)
async reczne CreateAsync+OpenAsync+DisposeAsync, NoCompr.           3           16    60374  tak (3 wpisy)
--- 3. Odczyt: OpenReadAsync + entry.OpenAsync ---
a.txt: 10000 B -> skompresowane 28 B
sub/b.txt: 26 B -> skompresowane 29 B
sub/rnd.bin: 50000 B -> skompresowane 50020 B
--- 4. CancellationToken ---
zawczasu anulowany token: OperationCanceledException
plik po anulowaniu istnieje: False
anulowanie w trakcie: TaskCanceledException
plik po anulowaniu istnieje: True, rozmiar 592301 B
da sie otworzyc, wpisow: 3 z 200
--- 5. Zip-slip: wpis '../evil.txt' ---
IOException: Extracting Zip entry would have resulted in a file outside the specified destination directory.
evil.txt poza katalogiem docelowym istnieje: False
```

(W pierwszym przebiegu sekcja 4 dała 392144 B i 2 wpisy.)

## 3. compat-check-zip (celowo NIE kompiluje się na .NET 9)

```bash
dotnet build compat-check-zip
```

Zweryfikowane (SDK 9.0.316): 3×`error CS0117` (`ZipFile.CreateFromDirectoryAsync`, `ZipFile.ExtractToDirectoryAsync`,
`ZipArchive.CreateAsync`); linia ze starym `ZipFile.CreateFromDirectory` błędu nie daje.

## Zweryfikowane / niezweryfikowane

- Zweryfikowane `dotnet run`: `zip-reflect` (oba TFM), `zip-async`. Zweryfikowane `dotnet build`: `compat-check-zip` (CS0117, SDK 9.0.316).
- Niezweryfikowane: Kestrel/`Response.Body` z `AllowSynchronousIO=false`, strumienie sieciowe, tryb `Update`, zip64,
  zwolnienie wątków z puli, czasy/wydajność, przyczyna pozostałych sync zapisów w źródłach biblioteki, .NET 11 (brak SDK).
