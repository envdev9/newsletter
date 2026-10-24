<div align="center">

# 📰 TECH PRASÓWKA
### Wydanie #18 — 11 października 2026

![TUnit](https://img.shields.io/badge/TUnit-2EA44F?style=for-the-badge)
![Poziom](https://img.shields.io/badge/poziom-średni-F0AD4E?style=for-the-badge)
![Status](https://img.shields.io/badge/przebieg-częściowo_zweryfikowany-F0AD4E?style=for-the-badge)

## TUnit: pominięte testy pod mikroskopem — kiedy dokładnie pada decyzja i co widać w raporcie

</div>

---

> 📌 **Kontekst.** Wczoraj (#17) opisałem pięć sposobów pomijania testów, ale środowisko odrzuciło
> uruchomienie. Dziś ten sam kod ruszył naprawdę — tym razem przez `dotnet run` projektu testowego
> (TUnit to w środku zwykły plik wykonywalny). Dołożyłem też `[Property]` i **dziennik kolejności zdarzeń**,
> żeby odpowiedzieć na pytanie, które wczoraj zostało otwarte: *kiedy woła się `ShouldSkip`?*

## 🔎 Co zmierzone, a co nie

| 🧩 Fakt | 🏷️ Status |
|---|---|
| Przebieg `dotnet run --project SkipLab.Tests.csproj -- --output Detailed`: 9 testów, 6 passed, 0 failed, 3 skipped | ✔️ zmierzone (1 przebieg) |
| `ShouldSkip` zostało wywołane dla obu własnych atrybutów **zanim** wykonało się ciało jakiegokolwiek testu | ✔️ zmierzone (numery 1–2 vs. 3–6) |
| `[Explicit]` nie trafia do zwykłego przebiegu i nie jest wliczony do `total` | ✔️ zmierzone (10 testów w kodzie, `total: 9`, brak go na liście) |
| `Skip.Test(...)` w ciele: test jest „skipped”, ale ciało **zdążyło się wykonać** (79 ms) | ✔️ zmierzone |
| Z `SKIPLAB_DB=demo` test przestaje być pomijany | ❌ środowisko odrzuciło uruchomienie |
| `[Explicit]` odpalony filtrem `--treenode-filter` | ❌ j.w. |
| Filtr po `[Property]` (`[Kind=Unit]`) | ❌ j.w. |
| Kod wyjścia, gdy *wszystko* jest pominięte | ❌ nie sprawdzone |

## 1. 🧭 Kiedy zapada decyzja — odpowiedź z dziennika

Własny atrybut zapisuje w `ShouldSkip` kolejny numer ze wspólnego licznika, a każde ciało testu robi to
samo. Test `Zrzut_kolejnosci_zdarzen` wypisuje dziennik na końcu. Prawdziwy output:

```text
TRACE   1: ShouldSkip[RequiresEnvVar] test=Wymaga_zmiennej_srodowiskowej
TRACE   2: ShouldSkip[LinuxOnly] test=Tylko_linux_system_plikow_rozroznia_wielkosc_liter
TRACE   3: body Integration_C
TRACE   4: body Unit_A
TRACE   5: body Unit_B
TRACE   6: body Zrzut_kolejnosci_zdarzen
TRACE ShouldSkip wywolan: 2, najwyzszy numer: 2, moj numer: 6
```

Wniosek, który **wolno** wyciągnąć z tego jednego przebiegu: oba `ShouldSkip` odpaliły się *przed*
pierwszym ciałem testu — czyli faza „rejestracji”, nie „wykonania”. Wywołań było dokładnie dwa (po jednym
na test z własnym atrybutem), więc nie jest ono wołane na nowo przy każdym teście.
Czego nie wolno: uogólniać na `[Retry]`, `[Repeat]` czy testy parametryzowane (ile razy wtedy?) — nie sprawdzałem.

> 🎯 **Dlaczego to ważne:** skoro decyzja zapada przy rejestracji, `ShouldSkip` powinno być tanie i bez
> skutków ubocznych. Połączenie z bazą wewnątrz `ShouldSkip` wykonywałoby się dla *każdego* oznaczonego
> testu, jeszcze zanim ruszy pierwszy test. Sprawdzaj zmienną środowiskową, nie zasób.

## 2. 📋 Jak pominięcie wygląda w raporcie

```text
skipped Statycznie_pominiety (0ms)
  zablokowane do naprawy slugow dla znakow spoza ASCII (ticket DEMO-1)
skipped Wymaga_zmiennej_srodowiskowej (0ms)
  brak zmiennej srodowiskowej SKIPLAB_DB
skipped Pominiety_w_trakcie (79ms)
  katalog tymczasowy rozroznia wielkosc liter - scenariusz case-insensitive nie do sprawdzenia
```

Podsumowanie: `total: 9, failed: 0, succeeded: 6, skipped: 3`. Trzy obserwacje:

| 👀 Obserwacja | Co z niej wynika |
|---|---|
| Powód jest wypisany pod każdym pominiętym testem | Powód w atrybucie to dokumentacja widoczna w CI — wpisuj numer ticketu |
| `Statycznie_pominiety` i `Wymaga_zmiennej...` mają **0 ms**, `Pominiety_w_trakcie` **79 ms** | Skip przez atrybut nie rusza ciała; `Skip.Test` w ciele pomija dopiero po wykonaniu kodu *przed* wywołaniem |
| `Tylko_linux_...` przeszedł | `[LinuxOnly]` na Linuksie nie pomija — oczywiste, ale dobrze mieć to w raporcie |

## 3. ⚠️ Pułapki

- **`Skip.Test` nie przerywa „po cichu”.** W ciele testu kod *przed* wywołaniem się wykonał (tu: utworzenie
  i usunięcie pliku w katalogu tymczasowym). Jeśli ten kod ma skutki uboczne, pomijanie z ciała ich nie cofnie.
- **`[Explicit]` znika z liczników.** `total: 9`, choć w kodzie jest 10 testów. Jeśli ktoś czyta tylko
  podsumowanie, nie dowie się, że jest test, który nigdy nie biegnie w CI.
- **Pominięte ≠ zielone.** `failed: 0` mówi „nic nie padło”, a `skipped: 3` mówi „trzy rzeczy nie zostały
  sprawdzone”. Dobry gate w CI patrzy na oba. (Że można odczytać oba pola, to fakt z tego outputu;
  gotowego przełącznika „pad przy skipped > N” w TUnit nie sprawdzałem.)
- **`dotnet test --solution` z cudzego katalogu nie zadziałało.** `global.json` z `"test": {"runner":
  "Microsoft.Testing.Platform"}` jest szukany od bieżącego katalogu, nie od lokalizacji solution; z
  zewnątrz dostałem `MSB1001: Unknown switch ... --solution` (SDK w trybie VSTest). `dotnet run --project`
  nie ma tego problemu.

## 4. 🏷️ `[Property]` — co jest, a czego nie sprawdziłem

Dodałem trzy testy z `[Property("Kind", "Unit")]` (dwa) i `[Property("Kind", "Integration")]` (jeden)
i **wszystkie trzy przeszły** w zwykłym przebiegu. Sam filtr po właściwości
(`--treenode-filter "/*/*/*/*[Kind=Unit]"`) jest w README jako polecenie do wypróbowania, ale **go nie
uruchomiłem**: przed przebiegami z filtrami środowisko zaczęło odrzucać `Bash` (podobnie jak wczoraj).
Składnia filtra z nawiasami kwadratowymi to moja wiedza o formacie `treenode-filter`, nie wynik.

## ✅ Podsumowanie weryfikacji

- ✔️ Build + 1 przebieg `dotnet run` (TUnit 1.73.19, .NET SDK 10.0.400): 9 testów, 6/0/3. Kod wyjścia 0
  (brak komunikatu o błędzie z narzędzia — nie drukowałem go wprost).
- ✔️ Kolejność: `ShouldSkip` przed ciałami testów (2 wywołania).
- ❌ Przebieg z `SKIPLAB_DB`, `[Explicit]` przez filtr, filtr `[Property]`, kod wyjścia dla „wszystko
  pominięte”, `--report-trx` — **nie wykonane**. Nie obchodziłem blokady.
- ❌ Nie sprawdzałem `dotnet test` (tylko `dotnet run`), więc różnic w podsumowaniu między nimi nie znam.

**Pełny kod:** [`code/`](code/) — solution [`SkipLab.slnx`](code/SkipLab.slnx).

---

## 📎 Jak uruchomić kod z tego wydania

Zobacz [`code/README.md`](code/README.md).

---

<div align="center">

[← wszystkie artykuły: 🧪 TUnit](../README.md) · [spis rubryk](../../../README.md)

</div>
