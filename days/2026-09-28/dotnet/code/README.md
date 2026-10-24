# Kod do wydania #5 — kryptografia postkwantowa i generyczne GCHandle (.NET 10 BCL)

Pełny artykuł: [`../ARTICLE.md`](../ARTICLE.md).

Wymagania: **.NET 10 SDK** (`dotnet --version` → `10.x`). Sprawdzone na `10.0.400`.
Projekty `pq-crypto` i `typed-gchandle` celują w `net10.0`; `compat-check` celowo
celuje w `net9.0` (wymaga zainstalowanego SDK 9.x obok — sprawdzone na `9.0.316`), żeby
pokazać realny błąd kompilatora "przed". Brak zależności NuGet.

## Fragment prasówki, którego dotyczy ten kod

> .NET 10 dodaje `System.Security.Cryptography.MLDsa`/`MLKem` (FIPS 204/203,
> kryptografia postkwantowa) — sprawdzone: nie istnieją w .NET 9 (`CS0103`). Kształt API
> jak `RSA`/`ECDsa`. Na tej maszynie `IsSupported=false` (OpenSSL 3.0.2, potrzeba 3.5+),
> więc `GenerateKey` rzuca `PlatformNotSupportedException` — pokazane uczciwie, bez
> zmyślania podpisu.
>
> `System.Runtime.InteropServices.GCHandle<T>`/`PinnedGCHandle<T>`/`WeakGCHandle<T>` —
> generyczne, typowane odpowiedniki starego niegenerycznego `GCHandle` (bez boksowania,
> bez rzutowania). Sprawdzone: nie istnieją w .NET 9 (`CS0308`). Haczyk zmierzony
> realnie: `PinnedGCHandle<string[]>` nie rzuca `ArgumentException "Object contains
> references"`, w przeciwieństwie do starego `GCHandle.Alloc(..., GCHandleType.Pinned)`.

## 1. pq-crypto (ML-DSA / ML-KEM)

```bash
dotnet run --project pq-crypto
```

```
--- Wsparcie platformy dla kryptografii postkwantowej (.NET 10) ---
MLDsa.IsSupported = False
MLKem.IsSupported = False

--- ML-DSA (FIPS 204) - podpis cyfrowy odporny na atak kwantowy ---
MLDsa.GenerateKey rzucil: System.PlatformNotSupportedException
Komunikat: Algorithm 'MLDsa' is not supported on this platform.

--- ML-KEM (FIPS 203) - uzgadnianie kluczy odporne na atak kwantowy ---
MLKem.GenerateKey rzucil: System.PlatformNotSupportedException
Komunikat: Algorithm 'MLKem' is not supported on this platform.
```

Jeśli uruchomisz to na maszynie z OpenSSL 3.5+ (Linux) albo Windows 11 24H2+/Server
2025 (CNG), `MLDsa.IsSupported`/`MLKem.IsSupported` powinny zwrócić `true` i kod
przejdzie realną ścieżkę: podpisz/zweryfikuj (`SignData`/`VerifyData`) oraz
encapsulate/decapsulate (`Encapsulate`/`Decapsulate`) — ta ścieżka **nie została
zweryfikowana uruchomieniem** na żadnej maszynie w tej sesji, tylko skompilowana
(sygnatury potwierdzone refleksją nad prawdziwym `System.Security.Cryptography.dll`
z .NET 10).

## 2. typed-gchandle (GCHandle&lt;T&gt; / PinnedGCHandle&lt;T&gt; / WeakGCHandle&lt;T&gt;)

```bash
dotnet run --project typed-gchandle -c Release
```

Uwaga: uruchom w `-c Release`. W `Debug` sekcja 4 (`WeakGCHandle<T>`) może pokazać
`obiekt zyje = True` nawet po `GC.Collect()`, bo niezoptymalizowany JIT wydłuża czas
życia lokalnej zmiennej — to efekt uboczny trybu Debug, nie błąd API.

```
--- 1. stary GCHandle (non-generic, boxing) ---
typ Target: System.Int32, wartosc: 42
--- 2. GCHandle<T> generyczny, bez boxingu, bez rzutowania ---
target.ToString() = hello
--- 3. PinnedGCHandle<T> - przypiecie tablicy i surowy wskaznik ---
buffer po zapisie przez wskaznik: 999,2,3,4,5
--- 4. WeakGCHandle<T> - typowany slaby uchwyt ---
przed GC: obiekt zyje = True
po GC: obiekt zyje = False
--- 5. Haczyk: PinnedGCHandle<T> na tablicy typow referencyjnych ---
Stary GCHandle.Alloc(string[], Pinned):
  rzucil: ArgumentException: Object contains references. (Parameter 'value')
Nowy PinnedGCHandle<string[]>:
  brak wyjatku; wskaznik = 128549423946240; ptr[0] == refArr2[0]: True
```

(Wartość adresu wskaźnika w sekcji 5 będzie inna przy każdym uruchomieniu — to
normalne, adres zależy od aktualnego layoutu sterty.)

## 3. compat-check (celowo NIE kompiluje się na .NET 9)

Projekt celuje w `net9.0` i domyślnie ma aktywny **Dowód 1** (`GCHandle<T>`):

```bash
dotnet build compat-check
```

Oczekiwany wynik: `error CS0308: The non-generic type 'GCHandle' cannot be used with type arguments`.

Żeby zobaczyć **Dowód 2** (`MLDsa`), zakomentuj blok "Dowod 1" w
`compat-check/Program.cs`, odkomentuj blok "Dowod 2" (i `using
System.Security.Cryptography;`), i zbuduj ponownie. Oczekiwany wynik:
`error CS0103: The name 'MLDsa' does not exist in the current context`. Oba błędy
zostały realnie zweryfikowane w tej sesji (SDK 9.0.316) — output wklejony powyżej
1:1, bez zmyślania.

## Jak zweryfikowano „co jest nowe w .NET 10"

Zamiast zgadywać z pamięci, które API są nowe, w tej sesji porównano realną
powierzchnię API `System.Private.CoreLib`/`System.Security.Cryptography` między
zainstalowanym SDK **9.0.316** a **10.0.400** przez refleksję (`Assembly.Load` +
`GetExportedTypes`/`GetMembers`, dopasowanie po pełnej nazwie typu bez nazwy
assembly, żeby nie dać się zmylić przeniesieniom typu między assembly jak
`ReadOnlySet<T>`, który już istniał w .NET 9 w innym assembly). Dopiero na tej
podstawie wybrano `MLDsa`/`MLKem`/`SlhDsa` oraz `GCHandle<T>`/`PinnedGCHandle<T>`/
`WeakGCHandle<T>` jako kandydatów, i każdy z nich potwierdzono osobno realną
kompilacją `error CS0103`/`CS0308` na `net9.0`. Skrypt weryfikacyjny nie wszedł do
repo (był w `/tmp`, poza katalogiem tego wydania) — powyższe błędy kompilatora są
jego bezpośrednim, wklejonym efektem.

## Zweryfikowane / niezweryfikowane — podsumowanie

- Zweryfikowane realnym `dotnet build`/`dotnet run` (SDK 10.0.400): `pq-crypto`
  (ścieżka `IsSupported=false` + `PlatformNotSupportedException`), `typed-gchandle`
  (wszystkie 5 sekcji, w tym haczyk z sekcji 5), `compat-check` (oba błędy, SDK
  9.0.316).
- Niezweryfikowane: pełna ścieżka `MLDsa`/`MLKem` z `IsSupported=true` (podpis,
  weryfikacja, encapsulate/decapsulate) — brak maszyny z OpenSSL 3.5+ lub Windows
  11 24H2+/CNG w tej sesji. Przyczyna rozluźnienia reguły "Object contains
  references" w `PinnedGCHandle<T>` względem starego `GCHandle` — obserwacja
  opisana wprost, nie wyjaśniona.
