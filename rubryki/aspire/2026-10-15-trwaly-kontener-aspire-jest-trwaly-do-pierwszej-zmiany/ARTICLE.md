<div align="center">

# 📰 TECH PRASÓWKA
### Wydanie #22 — 15 października 2026

![.NET Aspire](https://img.shields.io/badge/.NET_Aspire-512BD4?style=for-the-badge)
![Docker](https://img.shields.io/badge/Docker-2496ED?style=for-the-badge)
![Poziom](https://img.shields.io/badge/poziom-zaawansowany-red?style=for-the-badge)

## "Trwały" kontener Aspire jest trwały do pierwszej zmiany konfiguracji. Zmień jedną zmienną środowiskową i Redis wstaje od zera

</div>

---

> _"W #15 udowodniliśmy, że dane przeżywają `kill -9` AppHosta. Dziś sprawdzamy, co je zabija: edycja
> jednej linijki w AppHoście i `WithDataVolume`, który wcale nie chronił tego, co myślałeś."_

W #15 zostawiliśmy trzy otwarte pytania: co się dzieje z trwałym kontenerem, gdy zmienisz jego
konfigurację, czy `Persistent` + `WithDataVolume` to dobre połączenie i skąd "trwałe" dane. Dziś
odpowiedzi, zmierzone na prawdziwym Dockerze: Docker Engine `29.1.3`, Aspire `13.5.2`,
.NET SDK `10.0.400`, Linux, Redis `8.6` (domyślny tag integracji) i `7-alpine`.

**Dlaczego to ważne:** `ContainerLifetime.Persistent` kupuje szybki restart AppHosta. Ale to, że
kontener "zostaje", nie znaczy, że zostają w nim Twoje dane. Są dwa niezależne sposoby, żeby je
stracić, i oba wyglądają jak normalne, niewinne czynności developera.

---

### 1. Metoda

AppHost jest sterowany argumentami (`Mark=`, `RedisTag=`, `VolumeName=`, `Persistence=`), a
`Reconfig.Probe` uruchamia kolejne **procesy potomne**, każdy z nowym AppHostem, który zapisuje
albo czyta jeden klucz przez `CacheApi`. Po każdym kroku rodzic robi `docker inspect` kontenera
`cache-*`: ID, status, obraz, czas startu, zmienna `LAB_MARK`, woluminy, opcje `--save`.

Jedyna zmiana w kodzie względem #15 to dwie linijki sterowane konfiguracją:

```csharp
var cache = builder.AddRedis("cache")
    .WithEnvironment("LAB_MARK", cfg["Mark"] ?? "m0")   // "niewinna" zmiana konfiguracji
    .WithLifetime(ContainerLifetime.Persistent);
if (!string.IsNullOrEmpty(cfg["RedisTag"]))   cache.WithImageTag(cfg["RedisTag"]!);
if (!string.IsNullOrEmpty(cfg["VolumeName"])) cache.WithDataVolume(cfg["VolumeName"]!);
```

### 2. Wynik A: zmiana konfiguracji = nowy kontener, dane przepadają

Trzy pełne przebiegi probe'a dały te same wnioski. Skrót trzeciego (identyczny kształt w
pierwszych dwóch):

```
C1 write v1, Mark=m1        cache-3297b9ab id=879894eb9016 LAB_MARK=m1 redis:8.6
C2 read,  Mark=m1           ten sam id=879894eb9016, startedAt bez zmian; wartość v1 odczytana
C3 read,  Mark=m2           id=ea751fc7631c (NOWY), LAB_MARK=m2, ta sama nazwa; read: MISSING (404)
C4 read,  Mark=m2 + tag     id=9a7d7b7df50f (NOWY), image=redis:7-alpine; read: MISSING (404)
```

Wnioski, wprost z `docker inspect`:

- **Ta sama konfiguracja: ten sam kontener** (C2), zgodnie z #15.
- **Zmieniona zmienna środowiskowa lub tag obrazu: Aspire tworzy kontener od nowa.** ID i czas
  startu się zmieniają, **nazwa `cache-3297b9ab` zostaje** (stabilna nazwa nie jest dowodem
  ciągłości!). W kontenerze jest nowy `LAB_MARK`, więc zmiana naprawdę doszła, a dane z poprzedniego
  kontenera zniknęły.
- To zamyka haczyk #3 z #15: tam mówiliśmy "nie wiemy, czy przebuduje, czy zignoruje". Dziś wiemy:
  przebuduje (dla env i dla obrazu). **Nie zmierzyliśmy**, które dokładnie zmiany w konfiguracji
  wywołują przebudowę (np. porty, argumenty, volume mounts), ani jak Aspire to wykrywa.

Ciekawostka z C4: obraz `redis:7-alpine` deklaruje `VOLUME /data`, więc Docker utworzył
**anonimowy wolumin** (`volumes=[13e68f80...]`), a `redis:8.6` takiego nie ma (`volumes=[]`).
Zmiana taga potrafi więc po cichu zostawić po sobie osierocony wolumin. Sprzątnięcie go to Twoja
sprawa (probe robi to teraz sam).

### 3. Wynik B: `WithDataVolume` samo nie wystarczy, żeby dane przeżyły `docker rm`

Tu była niespodzianka. Intuicyjnie: `Persistent` + `WithDataVolume` = dane bezpieczne nawet po
usunięciu kontenera. Zmierzone:

| scenariusz | usunięcie kontenera | odczyt z nowego AppHosta (ten sam wolumin) |
|---|---|---|
| D1 `WithDataVolume`, zapis | `docker stop` + `docker rm` | **MISSING (404)** |
| D2 `WithDataVolume`, zapis | `docker rm -f` zaraz po zapisie | **MISSING (404)** |
| D4/D5 + `WithPersistence()` | j.w. (stop+rm / rm -f) | **MISSING (404)** w obu |
| D6 `WithDataVolume`, zapis, **75 s czekania** | `docker rm -f` | **`{"value":"v6-..."}` — dane są** |
| D3 kontrola, bez woluminu | `docker stop` + `docker rm` | MISSING (404) |

Wolumin był podmontowany we wszystkich wierszach (`volumes=[reconfig-lab-...]`). Dlaczego więc
D1 i D2 gubią dane? Z `docker inspect` (opcje) i pomiarów:

- `WithDataVolume` dla Redisa **sam włącza `--save 60 1`**: snapshot RDB co 60 s, jeśli zmieniono
  ≥ 1 klucz. Dodanie `WithPersistence()` nic nie zmieniło (te same opcje, ten sam wynik w D4/D5).
- Zapis klucza **nie jest** zapisem na wolumin. Dane trafiają do `/data` dopiero przy snapshocie
  (po 60 s) albo przy czystym zamknięciu Redisa. Zabijając kontener w ciągu minuty od zapisu,
  tracisz zapis (D2, D5). D6 to potwierdza: te same ustawienia, ale odczekane 75 s, i dane wracają
  z woluminu do **nowego kontenera**.
- Nawet `docker stop` nie ratuje danych (D1, D4). Zmierzone: `docker stop` trwa **10,4 s**,
  kod wyjścia kontenera to **137 (SIGKILL)**. Redis dostaje `SIGKILL`, nie ma szansy zapisać
  snapshotu przy zamknięciu. Z `docker inspect`: proces główny to `/bin/sh -c "redis-server ..."`.
  Hipoteza, **nie sprawdzona wprost**: `SIGTERM` nie dociera do `redis-server` przez powłokę
  (pomiar potwierdza tylko, że kontener nie zatrzymał się w reakcji na `SIGTERM` i został zabity).

W jednej linijce: dane są trwałe dopiero po upływie okna snapshotu, a "łagodne" zatrzymanie
kontenera Aspire's Redisa łagodne nie jest.

### 4. Co z tego wynika w praktyce

1. **Edytujesz AppHosta przy trwałym kontenerze, tracisz dane.** Każda zmiana env, obrazu itd. =
   zimny, pusty Redis. Jeśli to Ci przeszkadza, potrzebny jest wolumin i odczekanie snapshotu.
2. **`WithDataVolume` bez zrozumienia `--save` to złudzenie bezpieczeństwa.** Dla cache'a to
   nieistotne. Dla czegokolwiek, co chcesz zachować, albo dopisz własną politykę zapisu, albo
   użyj bazy z WAL (Postgres z #7 przeżył `StopAsync` z woluminem; jego zachowania przy
   `docker rm -f` tutaj nie mierzyliśmy).
3. **Sprzątanie rośnie:** trwały kontener, jego sieć (`aspire-persistent-network-<hash>-AppHost`)
   i woluminy (nazwane oraz anonimowe z obrazu) to wszystko Twoje do usunięcia. W tym wydaniu po
   wcześniejszych wersjach probe'a zostały mi sieć i trzy anonimowe woluminy; posprzątałem je
   dopiero po zauważeniu w `docker volume ls`, po czym probe nauczył się sprzątać też je.

---

### Czego dziś NIE sprawdziliśmy (uczciwie)

- **Dashboard Aspire** — nadal nieobejrzany wizualnie (brak przeglądarki).
- **Mechanizm wykrywania zmiany konfiguracji** (hash? porównanie pól?) i **które** zmiany
  powodują przebudowę. Zmierzono dokładnie dwie: zmienną środowiskową i tag obrazu.
- **Czy `SIGTERM` jest gubiony przez `/bin/sh -c`** — wniosek z czasu 10,4 s i kodu 137, nie z
  inspekcji sygnałów. Nie sprawdzono, czy `redis-server` zapisałby snapshot przy `SIGTERM`
  dostarczonym bezpośrednio.
- **Skąd stabilne hasło** trwałego kontenera / rola `UserSecretsId` (odczyt sekretów nie był
  potrzebny do tych pomiarów, nadal otwarte z #15).
- Inne zasoby niż Redis (Postgres/RabbitMQ), `SharedType.Keyed`, EF Core migracje, tryb `publish`,
  Windows/macOS/Podman. Jedna wersja każdego komponentu; trzy przebiegi probe'a spójne co do wniosków.

### Następny krok

Dashboard (wizualnie), `SharedType.Keyed` z kilkoma AppHostami, EF Core migracje na Postgresie z
woluminem (czy Postgres, w odróżnieniu od Redisa, naprawdę przeżywa `docker rm`), publish.

### Co dziś zostało na maszynie

Probe sprząta kontenery `cache-*`, nazwane i anonimowe woluminy tych kontenerów oraz sieć, które
pojawiły się po jego starcie. Po ostatnim przebiegu `docker ps -a` zawierał wyłącznie dwa cudze
kontenery sprzed testu, a lista woluminów i sieci była taka jak przed testem. Cudzych zasobów
Dockera nie ruszano.

---

## 📎 Jak uruchomić kod z tego wydania

Zobacz [`code/README.md`](code/README.md). Wymaga działającego Dockera; cały przebieg trwa
ok. 9 minut.

---

<div align="center">

[← wydanie #22 (wszystkie rubryki)](../README.md) · [spis wydań](../../../README.md)

</div>
