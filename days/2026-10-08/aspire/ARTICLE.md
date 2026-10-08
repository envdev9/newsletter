<div align="center">

# 📰 TECH PRASÓWKA
### Wydanie #15 — 8 października 2026

![.NET Aspire](https://img.shields.io/badge/.NET_Aspire-512BD4?style=for-the-badge)
![Docker](https://img.shields.io/badge/Docker-2496ED?style=for-the-badge)
![Poziom](https://img.shields.io/badge/poziom-zaawansowany-red?style=for-the-badge)

## Jedna linijka sprawiła, że Redis przeżył `kill -9` AppHosta — razem z danymi. Tylko że teraz to Ty go sprzątasz

</div>

---

> _"W #14 sprawdziliśmy, że domyślnie nic nie zostaje po zabitym hoście. Dziś prosimy Aspire o
> dokładnie odwrotność: kontener ma zostać."_

W #14 wyszło, że Aspire (a konkretnie jego orkiestrator DCP) sprząta kontenery nawet po `kill -9`.
Dla testów to cnota. Dla developera, który restartuje AppHosta kilkadziesiąt razy dziennie i za
każdym razem czeka na zimny start bazy, to kara. Odpowiedzią jest
`WithLifetime(ContainerLifetime.Persistent)`. Sprawdziliśmy go na prawdziwym AppHoście:
Docker Engine `29.1.3`, Aspire `13.5.2`, .NET SDK `10.0.400`, Linux.

**Dlaczego to ważne:** trwały kontener to szybszy cykl pracy (baza jest już gorąca, dane
zostają), ale też pierwszy zasób, który Aspire świadomie zostawia na Twojej maszynie. Warto wiedzieć,
co dokładnie zostaje, kiedy jest używany ponownie i kto go usuwa.

---

### 1. Zmiana w kodzie: jedna linijka

```csharp
var cache = builder.AddRedis("cache");
cache.WithLifetime(ContainerLifetime.Persistent);   // domyślnie: ContainerLifetime.Session
```

W repo ta linijka stoi za przełącznikiem konfiguracyjnym `Persistent` (domyślnie włączonym),
żeby probe mógł zmierzyć też wariant kontrolny. Reszta AppHosta jest ta sama co w #14: `CacheApi`
z `WithReference(cache)`, `WaitFor(cache)` i `/health`.

### 2. Metoda

`Persist.Probe` (rodzic plus procesy potomne, jak `Orphan.Probe` z #14) przechodzi dwa scenariusze.
Każdy krok to **nowy proces z nowym AppHostem**, który przez `CacheApi` zapisuje albo czyta klucz
`persist-key`, a potem umiera. Po 25 s od śmierci rodzic robi migawkę kontenera (`docker inspect`:
ID, status, czas startu):

| krok | co robi |
|---|---|
| A1 | zapis `v1`, host zamyka się czysto (`StopAsync` + `DisposeAsync`) |
| A2 | **nowy** AppHost, odczyt klucza |
| A3 | zapis `v2`, host zabity `kill -9` |
| A4 | **nowy** AppHost, odczyt klucza |
| B1, B2 | kontrola: to samo bez `Persistent` (domyślny `Session`) |

### 3. Wynik: ten sam kontener, te same dane, nawet po `kill -9`

Skrót prawdziwego wyjścia (drugi przebieg; pierwszy dał te same wnioski):

```
A1 write v1-234a04b3    kontener cache-4ab92b86: id=b3850491fd92 status=running startedAt=...59:14.7Z
   25 s po śmierci hosta (exit 0): ten sam id, status=running, ten sam startedAt
A2 read (nowy AppHost)  {"key":"persist-key","value":"v1-234a04b3"}   <- ten sam kontener
A3 write v2 + kill -9   25 s po zabiciu: ten sam id, status=running
A4 read (nowy AppHost)  {"key":"persist-key","value":"v2-234a04b3"}   <- dane sprzed kill -9

B1 write (Session)      kontener cache-pwddvwnv; po 25 s: (brak)
B2 read  (Session)      MISSING (404); nowy kontener cache-uvbbuqfx, też znika
```

Co z tego wynika:

- **Kontener nie jest zatrzymywany**: po czystym `StopAsync` i po `kill -9` dalej ma `status=running`
  i ten sam czas startu. Kolejny AppHost nie tworzy go na nowo, tylko **podpina się do
  istniejącego** (ID i `startedAt` identyczne w A1-A4).
- **Dane zostają**, bez żadnego `WithDataVolume`: klucz zapisany przed `kill -9` czytamy z nowego
  AppHosta. To pamięć działającego procesu Redisa, nie wolumin. Gdyby kontener padł, dane
  zniknęłyby (patrz haczyk 2).
- **`dcp` i `CacheApi` nadal znikają** (tego procesu nie ma w liście żywych po 25 s). Persistent
  dotyczy kontenera, nie projektów .NET: `CacheApi` startuje przy każdym AppHoście od nowa.
- **Kontrola `Session` zachowuje się jak w #14**: kontener znika, następny odczyt to 404.
- **Nazwa jest stabilna między przebiegami**: `cache-4ab92b86` wyszła identycznie w obu
  przebiegach (po tym, jak posprzątałem pierwszy), natomiast `Session` dostaje losowy sufiks
  (`cache-sefmrrgb`, `cache-pwddvwnv`, ...). Że sufiks `4ab92b86` jest hashem ścieżki projektu
  AppHosta — to przypuszczenie z kształtu nazwy, nie sprawdziłem w źródłach.

### 4. Haczyk #1: Aspire go nie sprząta — Ty tak

Po zakończeniu probe'a (przed własnym sprzątaniem) kontener `cache-4ab92b86` nadal działał. Ani
`StopAsync`, ani `DisposeAsync`, ani śmierć hosta go nie usuwają. Każdy projekt z `Persistent`
zostawia na maszynie żywy proces Redisa i opublikowany port, dopóki ktoś nie wykona
`docker rm -f`. Probe usuwa tylko to, co sam utworzył (migawka kontenerów przed i po).
Jeśli używasz `Persistent` w repozytorium zespołowym, dopisz sprzątanie do README.

### 5. Haczyk #2: "persistent" to nie "dane są bezpieczne"

Trwałość kontenera to **nie** trwałość danych. Dane przeżywają tylko tak długo, jak żyje ten jeden
kontener: `docker rm`, restart Dockera albo reboot maszyny je kasują. Jeśli chcesz mieć dane
po usunięciu kontenera, potrzebujesz osobno `WithDataVolume` (omówione w #7 dla Postgresa).
Ten związek (`Persistent` + `WithDataVolume`) w tym wydaniu **nie był mierzony**.

### 6. Haczyk #3: ponowne użycie kontenera to Twoja odpowiedzialność przy zmianie konfiguracji

Skoro nowy AppHost podpina się do starego kontenera, to **zmiana konfiguracji zasobu** w kodzie
(inny obraz, zmienne środowiskowe, hasło) może nie dotrzeć do działającego kontenera. Co dokładnie
Aspire robi w takiej sytuacji — nie sprawdzałem, więc nie twierdzę ani że przebudowuje, ani że
ignoruje. Zanim zaufasz `Persistent` przy zmianach obrazu, sprawdź to sam (`docker inspect`).

Powiązana zagadka z tego przebiegu: `AddRedis` generuje losowe hasło (#5), a mimo to nowy AppHost
połączył się z działającym kontenerem. Hasło musi więc być zachowywane między uruchomieniami; w
AppHoście ustawiłem `UserSecretsId`, ale **nie zweryfikowałem**, czy to właśnie tam trafia (odczyt
pliku sekretów poza katalogiem roboczym został w tej sesji zablokowany). Nie wiem też, co by się
stało bez `UserSecretsId`.

---

### Czego dziś NIE sprawdziliśmy (uczciwie)

- **Dashboard Aspire** — nadal nieobejrzany wizualnie (brak przeglądarki w tym środowisku).
- **Skąd bierze się stabilne hasło** trwałego kontenera i co się dzieje bez `UserSecretsId`.
- **Zmiana konfiguracji zasobu** przy działającym trwałym kontenerze (haczyk #3).
- **`Persistent` + `WithDataVolume`**, **stałe porty** (`WithHostPort`), EF Core migracje.
- Inne obrazy niż Redis (Postgres, RabbitMQ), `Persistent` dla `AddProject` / `AddExecutable`.
- Windows/macOS, Podman; jeden przebieg z jedną wersją każdego komponentu (dwa powtórzenia).
- Lista "procesów, które żyją" w wyjściu probe'a zawiera szum (procesy kontenera widoczne z hosta
  oraz cudze procesy maszyny); wniosek o `dcp`/`CacheApi` opiera się na ich braku na liście.

### Następny krok

Zmiana konfiguracji przy trwałym kontenerze, `Persistent` + `WithDataVolume`, `SharedType.Keyed`,
dashboard, EF Core migracje.

### Co dziś zostało na maszynie

Probe usunął własny kontener `cache-*` po scenariuszu A i B (potwierdzone `docker ps -a`: wyłącznie
dwa cudze kontenery sprzed testu, brak procesów `dcp`/`CacheApi`/`redis`, brak nowych sieci
i woluminów). Cudzych zasobów Dockera nie ruszano.

---

## 📎 Jak uruchomić kod z tego wydania

Zobacz [`code/README.md`](code/README.md). Wymaga działającego Dockera; cały przebieg trwa
ok. 5 minut.

---

<div align="center">

[← wydanie #15 (wszystkie rubryki)](../README.md) · [spis wydań](../../../README.md)

</div>
