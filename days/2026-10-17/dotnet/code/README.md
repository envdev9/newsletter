# Kod do wydania #24 — `OrderedDictionary` z `out int index` i `SlhDsa` (.NET 10)

Pełny artykuł: [`../ARTICLE.md`](../ARTICLE.md).

Wymagania: **.NET 10 SDK** (sprawdzone na `10.0.400`); `reflect-overloads` wymaga też runtime 9.x
(`dotnet --list-runtimes`); `compat-check-*` wymagają **SDK 9.0.316** (przypięte `global.json`,
`rollForward: disable` — zmień wersję, jeśli masz inne 9.0.x). Brak NuGet, brak sieci.

## Fragment prasówki, którego dotyczy ten kod

> `OrderedDictionary<TKey,TValue>.TryAdd(key, value, out int index)` i
> `TryGetValue(key, out value, out int index)` (.NET 10): indeks bez drugiego wyszukiwania.
> Na SDK 9.0.316: `CS1501` ×2. Zmierzone licznikiem wywołań komparatora (1000 kluczy): stare
> `TryGetValue+IndexOf+SetAt` i `TryGetValue+indexer` = 2 hashe/klucz, nowe = 1. Haczyki: indeks to
> migawka (po `Insert` `SetAt` cicho nadpisuje zły wpis; po `RemoveAt` rzuca
> `ArgumentOutOfRangeException`); `TKey=int` miesza klucz z indeksem; `null` → `ArgumentNullException`;
> `RemoveAt(0)` O(n) (~1,2–1,4 s vs 0 ms dla końca, 2000 operacji na 50 000 elem.).
>
> `SlhDsa` (FIPS 205) w `System.Security.Cryptography`: typy tylko w .NET 10 (`CS0103` na net9.0),
> oznaczone `[Experimental]` (`SYSLIB5006` — wymaga `NoWarn`). Na tej maszynie (OpenSSL 3.0.2)
> `IsSupported=false`, `GenerateKey` → `PlatformNotSupportedException`. Sign/verify NIE zweryfikowane.

## 1. ordered-dictionary-index

```bash
dotnet run -c Release --project ordered-dictionary-index
```

Output (zweryfikowany, 2 przebiegi; liczniki identyczne, czasy z sekcji 7 się różnią):

```
--- 1. Podstawy: co dokladnie zwraca 'index' ---
TryAdd(alfa)   -> True, index=0
TryAdd(beta)   -> True, index=1
TryAdd(alfa*)  -> False, index=0  (indeks ISTNIEJACEGO wpisu), wartosc nadal 10
TryGetValue(beta) -> True, value=20, index=1
TryGetValue(brak) -> False, value=0, index=-1  (pudlo: -1)
--- 2. Po co: ile razy kolekcja liczy klucz (komparator-licznik, 1000 kluczy) ---
A) TryGetValue + IndexOf + SetAt : hash/klucz = 2.0, equals/klucz = 2.0
B) TryGetValue + indexer set     : hash/klucz = 2.0, equals/klucz = 2.0
C) TryGetValue(out, out) + SetAt : hash/klucz = 1.0, equals/klucz = 1.0
   wynik identyczny? A=1000, B=1000, C=1000 (oczekiwane 1000)
D) licznik slow, 3000 wejsc/500 unikalnych: stary hash=6000, nowy hash=3000; te same wyniki? True
--- 3. Haczyk: indeks to MIGAWKA - po RemoveAt/Insert wskazuje inny wpis ---
indeks 'c' = 2
po RemoveAt(0) (z 3 wpisow zostaly 2, stary indeks wyszedl poza zakres):
  SetAt(2) -> ArgumentOutOfRangeException
po Insert(0): SetAt(1, 777) -> z=0, a=777, b=2, c=3
  klucz pod indeksem 1 to teraz 'a', nie 'b' (indeks 'b' = 2)
--- 4. Haczyk: TKey = int - indexer to KLUCZ, GetAt to INDEKS ---
d[10]=dziesiec  GetAt(1)=dziesiec  TryGetValue(10) -> value=dziesiec, index=1
d[0] -> KeyNotFoundException (to klucz 0, nie pierwszy element)
d.GetAt(0)=30 (pierwszy element wg kolejnosci wstawienia)
--- 5. Przypadki brzegowe ---
TryAdd(null, out) -> ArgumentNullException
TryGetValue(null, out, out) -> ArgumentNullException
pusty slownik TryGetValue -> False, v=0, i=-1
po nieudanym TryAdd(x): x, y, z (index zwrocony: 0)
a:0 b:1 (usuniete) c:1  -> indeks 'c' zajmuje miejsce po 'b'
--- 6. Praktyka: unikalne zdarzenia w kolejnosci pierwszego wystapienia + licznik + indeks pozycji ---
  [0] login   x2  (pierwszy raz na pozycji 0)
  [1] view    x3  (pierwszy raz na pozycji 1)
  [2] buy     x2  (pierwszy raz na pozycji 3)
  [3] logout  x1  (pierwszy raz na pozycji 6)
--- 7. Koszt O(n) RemoveAt/Insert (bo indeksy sie przesuwaja) - zmierzone Stopwatch, 50 000 elem. ---
2000x RemoveAt(0)+Add: 1353 ms,  2000x RemoveAt(last)+Add: 0 ms  (czasy orientacyjne, zmienne miedzy uruchomieniami)
```

## 2. reflect-overloads (refleksja na dwóch runtime'ach)

```bash
dotnet run -f net9.0  --project reflect-overloads
dotnet run -f net10.0 --project reflect-overloads
```

Na 9.0.18 `TryAdd(key, value)` i `TryGetValue(key, out value)`; na 10.0.11 dodatkowo
`TryAdd(key, value, out int index)` i `TryGetValue(key, out value, out int index)`. Typy `SlhDsa*`:
brak na 9, `SlhDsa, SlhDsaAlgorithm, SlhDsaCng, SlhDsaOpenSsl` na 10.

## 3. slhdsa-probe

```bash
dotnet run --project slhdsa-probe
```

Output (skrót; pełna lista 12 wariantów i ~40 metod pojawia się w konsoli):

```
SlhDsaSha2_128s    SLH-DSA-SHA2-128s      podpis=  7856 B  klucz publ.=32 B  klucz pryw.=64 B
SlhDsaSha2_128f    SLH-DSA-SHA2-128f      podpis= 17088 B  klucz publ.=32 B  klucz pryw.=64 B
SlhDsaSha2_192s    SLH-DSA-SHA2-192s      podpis= 16224 B  klucz publ.=48 B  klucz pryw.=96 B
SlhDsaSha2_192f    SLH-DSA-SHA2-192f      podpis= 35664 B  klucz publ.=48 B  klucz pryw.=96 B
SlhDsaSha2_256s    SLH-DSA-SHA2-256s      podpis= 29792 B  klucz publ.=64 B  klucz pryw.=128 B
SlhDsaSha2_256f    SLH-DSA-SHA2-256f      podpis= 49856 B  klucz publ.=64 B  klucz pryw.=128 B
(warianty SHAKE mają identyczne rozmiary)
--- 3. Wsparcie platformy ---
SlhDsa.IsSupported = False
MLDsa.IsSupported  = False
MLKem.IsSupported  = False
--- 4. Proba GenerateKey ---
RZUCILO PlatformNotSupportedException: Algorithm 'SlhDsa' is not supported on this platform.
```

Na maszynie z OpenSSL ze wsparciem SLH-DSA program przejdzie do gałęzi sign/verify (podpis,
`VerifyData=True`, po zmianie bitu `False`) — **ta gałąź nie była tu uruchomiona**.

## 4. compat-check-ordered i compat-check-slhdsa (celowo NIE kompilują się na .NET 9)

```bash
dotnet build compat-check-ordered
dotnet build compat-check-slhdsa
```

Oczekiwane (zweryfikowane, SDK 9.0.316): `compat-check-ordered` → `CS1501` dla `TryAdd` i
`TryGetValue` (3 argumenty; wersje 2-argumentowe w tym samym pliku nie dają błędu);
`compat-check-slhdsa` → 3× `CS0103` (`SlhDsa` ×2, `SlhDsaAlgorithm`).

## Zweryfikowane / niezweryfikowane

- Zweryfikowane `dotnet run`: `ordered-dictionary-index` (`-c Release`), `slhdsa-probe`, `reflect-overloads` (oba TFM).
- Zweryfikowane `dotnet build` na SDK 9.0.316: błędy jak wyżej.
- Niezweryfikowane: realny podpis/weryfikacja `SlhDsa`, próg OpenSSL dla SLH-DSA, `SlhDsaCng`,
  `CompositeMLDsa`, wydajność w BenchmarkDotNet, .NET 11 (brak SDK), dokumentacja online.
